import bpy
import math
from mathutils import Vector
from mathutils.interpolate import poly_3d_calc

#*********Bake WrapNormal**********
#*****
def new_GeometryNodes_group():
    ''' Create a new empty node group that can be used in a GeometryNodes modifier.
    '''
    node_group = bpy.data.node_groups.new('GeometryNodes_VMV', 'GeometryNodeTree')
    inNode = node_group.nodes.new('NodeGroupInput')
    ##inNode.outputs.new('NodeSocketGeometry', 'Mesh')

    #node_group.outputs.new()
    
    M2Vnode = node_group.nodes.new('GeometryNodeMeshToVolume')
    M2Vnode.inputs['Voxel Amount'].default_value = 32 #Voxel Amount
    #M2Vnode.update()
    node_group.links.new(inNode.outputs[0], M2Vnode.inputs['Mesh'])
    
    V2Mnode = node_group.nodes.new('GeometryNodeVolumeToMesh')
    node_group.links.new(M2Vnode.outputs['Volume'], V2Mnode.inputs['Volume'])
    
    outNode = node_group.nodes.new('NodeGroupOutput')
    #outNode.inputs.new('NodeSocketGeometry', 'Mesh')
    node_group.links.new(V2Mnode.outputs['Mesh'], outNode.inputs[0])
    
    #inNode.location = Vector((0, 0))
    #outNode.location = Vector((3*outNode.width, 0))
    return node_group

def WrapSelectedObjectTranferNormal():
    context = bpy.context
    #sel = bpy.context.selected_objects
    #act = bpy.context.active_object

    global obj_original, obj_mod
    """
    for obj in bpy.data.objects:
        if(obj.name == "Suzanne"):
            print(obj.name)
            obj_original = obj"""
    obj_original = bpy.context.view_layer.objects.active

    if not obj_original:
        print("Nothing Active!!")

    #Select Target mesh
    obj_original.select_set(True)

    #Apply transforms
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    #Duplicate & selected mesh
    WrapMeshName = obj_original.name+"_WrapMesh"

    for obj in bpy.data.objects:
        if(obj.name == WrapMeshName):
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.object.duplicate(linked=False)
    obj_mod = bpy.context.active_object
    obj_mod.select_set(True)
    obj_mod.name = obj_original.name+"_WrapMesh"

    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_faces_move(TRANSFORM_OT_shrink_fatten={"value":0.5})
    bpy.ops.object.editmode_toggle()

    #Add Geometry node modifier
    bpy.ops.object.modifier_add(type='NODES') 
    #Define node group internals

    # In 3.2 Adding the modifier no longer automatically creates a node group.
    # This test could be done with versioning, but this approach is more general
    # in case a later version of Blender goes back to including a node group.
    if obj_mod.modifiers[-1].node_group:
        node_group = obj_mod.modifiers[-1].node_group    
    else:
        node_group = new_GeometryNodes_group()
        obj_mod.modifiers[-1].node_group = node_group
    nodes = node_group.nodes
    #Apply MVM geometry node
    mod_MVM = obj_mod.modifiers[-1]
    bpy.ops.object.modifier_apply(modifier=mod_MVM.name)

    #Add Smooth modifier & apply
    bpy.ops.object.modifier_add(type='SMOOTH')
    mod_smooth = obj_mod.modifiers[-1]
    mod_smooth.name = 'Post_S'
    mod_smooth.iterations = 25
    bpy.ops.object.modifier_apply(modifier=mod_smooth.name)

    #Deselected ALL
    bpy.ops.object.select_all(action='DESELECT')

    #Select Original mesh
    bpy.context.view_layer.objects.active = obj_original
    obj_original.select_set(True)

    #Add Data transfer modifier & apply
    obj_original.data.use_auto_smooth = True
    bpy.ops.object.modifier_add(type='DATA_TRANSFER')
    mod_datatrans = obj_original.modifiers[-1]
    mod_datatrans.name = 'Post_datatrans'
    mod_datatrans.use_loop_data = True
    mod_datatrans.data_types_loops = {'CUSTOM_NORMAL'}
    mod_datatrans.object = obj_mod
    bpy.ops.object.modifier_apply(modifier=mod_datatrans.name)


    #Hide modified mesh
    obj_mod.hide_viewport = True

    #me = mesh.data
    #bm = bmesh.from_edit_mesh(me)



#*********Bake WrapAO**********
#*****
def getRayCastDirections():
    #Using an IsoSphere vertex to get the raycast directions for each point
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, enter_editmode=False, location=(0, 0, 0))
    Sphere = bpy.context.object
    Sphere.name = "RaycastSphere"
    
    raycastDirs = [vert.co for vert in Sphere.data.vertices]
    #Vector.normalize()
    #we are going to use the verts.co as raycast direction for 360 coverage
    bpy.data.objects.remove(Sphere, do_unlink=True)
    return raycastDirs
    #RCDirs = getRayCastDirections()
    
def raycastAllDirection(obj, vetPos, rcDirs, rcLength):
    # Cast  rays
    ray_origin = vetPos
    valueSignDist = 99999999
    for dir in rcDirs:
        success, location, normal, poly_index = obj.ray_cast(ray_origin, dir, distance = rcLength)
        if(success):
            value = (location-vetPos).length
            value = math.copysign(value,-Vector.dot(dir, normal))
            if(abs(value)<abs(valueSignDist)):
                valueSignDist = value
    return valueSignDist

def saveSDasVertexColor(obj, signDists, wm):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    mesh = obj.data
    bpy.ops.object.mode_set(mode = 'VERTEX_PAINT')
    for vertindex in range(len(signDists)):
        for polygon in mesh.polygons:
            for i, index in enumerate(polygon.vertices):
                if vertindex == index:
                    loop_index = polygon.loop_indices[i]
                    r = signDists[vertindex]
                    mesh.vertex_colors.active.data[loop_index].color = [r,r,r,1.0]
        wm.progress_update(int((vertindex/len(signDists)) * 45) + 55)
    bpy.ops.object.mode_set(mode = 'OBJECT')

def BakeAOUsingWrapMesh():
    context = bpy.context
    wm = bpy.context.window_manager
    wm.progress_begin(0, 100)

    obj_original = bpy.context.view_layer.objects.active
    # make sure in object mode
    bpy.ops.object.mode_set(mode = 'OBJECT')

    if not obj_original:
        print("Nothing Active!!")

    #Select Target mesh
    obj_original.select_set(True)

    WrapMeshName = obj_original.name+"_WrapMesh"
    try:
        obj_warpmesh = bpy.data.objects[WrapMeshName]
    except:
        raise TypeError("Active does not have a wrapmesh!!")

    #get all vertex position
    vetPoss = [vert.co for vert in obj_original.data.vertices]

    #get raycast directions for each vert
    rcDirs = getRayCastDirections()

    #raycastlength
    rcLength = max(max(obj_warpmesh.dimensions.x, obj_warpmesh.dimensions.y),obj_warpmesh.dimensions.z)
    
    #depsgraph = context.evaluated_depsgraph_get()
    #depsgraph.update()  # just in case
    #obj = obj_warpmesh.evaluated_get(depsgraph)
    obj_warpmesh.hide_viewport = False

    #get Sign distance for All vert using raycast(percent 0%~45%)
    signDist = []
    for i in range(len(vetPoss)):
        signDist.append(raycastAllDirection(obj_warpmesh, vetPoss[i], rcDirs, rcLength))
        wm.progress_update(int(i/len(vetPoss) * 45))

    #normalize SDF value to 0~1 (percent 45%~55%)
    obj_warpmesh.hide_viewport = True
    maxDist = max(signDist)
    minDist = min(signDist)
    for i in range(len(vetPoss)):
        signDist[i] = (signDist[i]-minDist)/(maxDist-minDist)
        signDist[i] = signDist[i]*signDist[i]
    wm.progress_update(55)
    
    #Save SDF AO to Vertex Color(percent 55%~100%)
    saveSDasVertexColor(obj_original, signDist, wm)

#**********Operators************
#**
class BakeWarpNomral(bpy.types.Operator):
    """Generate Wrap mesh for selected mesh and transfer normal to mesh"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.bake_wrap_normal"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Bake Wrap Normal"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        WrapSelectedObjectTranferNormal()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class BakeWarpAO(bpy.types.Operator):
    """Bake Wrap AO to selected mesh using wrap mesh"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.bake_wrap_ao"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Bake Wrap AO"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.
    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        BakeAOUsingWrapMesh()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.