import bpy, bmesh
import math
from mathutils import Vector
from mathutils.interpolate import poly_3d_calc



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
    #sel = bpy.context.selected_objects
    #act = bpy.context.active_object

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

if __name__ == "__main__":
    BakeAOUsingWrapMesh()      



