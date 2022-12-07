import bpy, bmesh
from mathutils import Vector

def new_GeometryNodes_group():
    ''' Create a new empty node group that can be used in a GeometryNodes modifier.
    '''
    node_group = bpy.data.node_groups.new('GeometryNodes_VMV', 'GeometryNodeTree')
    inNode = node_group.nodes.new('NodeGroupInput')
    inNode.outputs.new('NodeSocketGeometry', 'Mesh')
    
    M2Vnode = node_group.nodes.new('GeometryNodeMeshToVolume')
    M2Vnode.inputs['Voxel Amount'].default_value = 32 #Voxel Amount
    #M2Vnode.update()
    node_group.links.new(inNode.outputs['Mesh'], M2Vnode.inputs['Mesh'])
    
    V2Mnode = node_group.nodes.new('GeometryNodeVolumeToMesh')
    node_group.links.new(M2Vnode.outputs['Volume'], V2Mnode.inputs['Volume'])
    
    outNode = node_group.nodes.new('NodeGroupOutput')
    outNode.inputs.new('NodeSocketGeometry', 'Mesh')
    node_group.links.new(V2Mnode.outputs['Mesh'], outNode.inputs['Mesh'])
    
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


if __name__ == "__main__":
    WrapSelectedObjectTranferNormal()