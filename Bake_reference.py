import bpy
import time

#Operation Dict
#operation will  need to be divided in multiple steps

sleep = 1

def _00(): 
    print("f00")
    time.sleep(sleep)
    
def _01(): 
    print("f01")
    time.sleep(sleep)
    
def _02(): 
    print("f02")
    time.sleep(sleep)
    
def _03(): 
    print("f03")
    time.sleep(sleep)
    
def _04(): 
    print("f04")
    time.sleep(sleep)
     
Operations = {
    "First Step":_00,
    "Second Step":_01,
    "Running Stuff":_02,
    "Wait a minute":_03,
    "There's a problem":_04,    
    "ah no it's ok":_04,    
    "we are done":_04,    
    }

#Modal Operator

class EXAMPLE_OT_modal_operator(bpy.types.Operator): 
    
    bl_idname = "example.modal_operator"
    bl_label = "Modal Operator"
    
    def __init__(self):
        
        self.step = 0
        self.timer = None
        self.done = False
        self.max_step = None
        
        self.timer_count = 0 #timer count, need to let a little bit of space between updates otherwise gui will not have time to update
                
    def modal(self, context, event):
        
        global Operations
        
        #update progress bar
        if not self.done:
            print(f"Updating: {self.step+1}/{self.max_step}")
            #update progess bar
            context.object.progress = ((self.step+1)/(self.max_step))*100
            #update label
            context.object.progress_label = list(Operations.keys())[self.step]
            #send update signal
            context.area.tag_redraw()
            
            
        #by running a timer at the same time of our modal operator
        #we are guaranteed that update is done correctly in the interface
        
        if event.type == 'TIMER':
            
            #but wee need a little time off between timers to ensure that blender have time to breath, so we have updated inteface
            self.timer_count +=1
            if self.timer_count==10:
                self.timer_count=0
                
                if self.done:
                    
                    print("Finished")
                    self.step = 0
                    context.object.progress = 0
                    context.window_manager.event_timer_remove(self.timer)
                    context.area.tag_redraw()
                    
                    return {'FINISHED'}
            
                if self.step < self.max_step:
                        
                    #run step function
                    list(Operations.values())[self.step]()
                    
                    self.step += 1
                    if self.step==self.max_step:
                        self.done=True
                    
                    return {'RUNNING_MODAL'}
        
        return {'RUNNING_MODAL'}
            
    def invoke(self, context, event):
        
        print("")
        print("Invoke")
        
        #terermine max step
        global Operations
        if self.max_step == None:
            self.max_step = len(Operations.keys())        

        context.window_manager.modal_handler_add(self)
        
        #run timer 
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        
        return {'RUNNING_MODAL'}



#Panel

class EXAMPLE_PT_panel(bpy.types.Panel):

    bl_idname      = "EXAMPLE_PT_panel"
    bl_label       = "Example"
    bl_category    = "Example"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_context     = "objectmode"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        if obj.progress: 
            progress_bar = layout.row()
            progress_bar.prop(bpy.context.object,"progress")
            progress_lbl = layout.row()
            progress_lbl.active = False
            progress_lbl.label(text=bpy.context.object.progress_label)
        else:
            ope = layout.row()
            ope.operator_context = "INVOKE_DEFAULT"
            ope.operator("example.modal_operator",text="Run Modal Operator")
        
        return 
    

#Registering Stuff...

bpy.types.Object.progress = bpy.props.FloatProperty( name="Progress", subtype="PERCENTAGE",soft_min=0, soft_max=100, precision=0,)
bpy.types.Object.progress_label = bpy.props.StringProperty()
    
bpy.utils.register_class(EXAMPLE_PT_panel)
bpy.utils.register_class(EXAMPLE_OT_modal_operator)


"""
import bpy
import time

wm = bpy.context.window_manager

# progress from [0 - 1000]
tot = 100
wm.progress_begin(0, tot)
for i in range(tot):
    wm.progress_update(i)
    time.sleep(0.05)
wm.progress_end()

"""

"""
#Apply transforms
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.object.editmode_toggle()
bpy.ops.mesh.select_all(action='SELECT')
me = obj_original.data
bm = bmesh.from_edit_mesh(me)
bm.verts.ensure_lookup_table()#update internal index table
#verts = [v.co for v in bm.verts]
vert0 = bm.verts[0]

print(vert0.co)


bpy.ops.object.editmode_toggle()
"""
"""
depsgraph = context.evaluated_depsgraph_get()
depsgraph.update()  # just in case
#obj = bpy.data.objects['Cube'].evaluated_get(depsgraph)

# Cast a ray
ray_origin = Vector((0, 0, 7))
ray_direction = Vector((0, 0, 10))
for i in range(100000):
    success, location, normal, poly_index = obj_original.ray_cast(ray_origin, ray_direction)



print(success)
print(location)
print(normal)
print(poly_index)
"""
"""
bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='ONLY_FACE')
    me = Sphere.data
    bm = bmesh.from_edit_mesh(me)
    #update internal index table
    bm.verts.ensure_lookup_table()
"""

"""
#print(RCDirs[0:3])
#def rayCastObjectforPoint
mesh = bpy.context.active_object.data

currentVertIndex = 10
bpy.ops.object.mode_set(mode = 'VERTEX_PAINT')
for vertindex in range(len(mesh.vertices)):
    for polygon in mesh.polygons:
        for i, index in enumerate(polygon.vertices):
            if vertindex == index:
                loop_index = polygon.loop_indices[i]
                r = vertindex/len(mesh.vertices)-0.5
                mesh.vertex_colors.active.data[loop_index].color = [r,0,0,1.0]
bpy.ops.object.mode_set(mode = 'EDIT')
"""