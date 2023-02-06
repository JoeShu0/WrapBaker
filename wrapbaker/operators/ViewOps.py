import bpy




def ToggleNormalView():
    print("Toggle normal view~")

class ToggleNormalView(bpy.types.Operator):
    """Toggle the view bewteen shaded and Normal view"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "view.toggle_normal_view"        # Unique identifier for buttons and menu items to reference.
    bl_label = "NormalView"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        #WrapSelectedObjectTranferNormal()
        print("Toggle normal view~")
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class ToggleVertexColorView(bpy.types.Operator):
    """Toggle the view bewteen shaded and VertexColor view"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.toggle_VertColor_view"        # Unique identifier for buttons and menu items to reference.
    bl_label = "VertColView"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        #WrapSelectedObjectTranferNormal()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.


NormalView = bpy.props.BoolProperty(default = False, update = ToggleNormalView)
VertColView = False