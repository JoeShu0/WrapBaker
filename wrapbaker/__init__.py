# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


bl_info = {
    "name": "Wrap Normal AO Baker",
    "blender": (3, 20, 0),
    "category": "Object",
}


if "bpy" in locals():
    import importlib
    importlib.reload(WrapNormal)
    importlib.reload(WarpAO)
else:
    import bpy
    from . import WrapNormal 
    from . import WarpAO

class BakeWarpNomral(bpy.types.Operator):
    """Generate Wrap mesh for selected mesh and transfer normal to mesh"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.bake_wrap_normal"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Bake Wrap Normal"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        WrapNormal.WrapSelectedObjectTranferNormal()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class BakeWarpAO(bpy.types.Operator):
    """Bake Wrap AO to selected mesh using wrap mesh"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.bake_wrap_ao"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Bake Wrap AO"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.
    def execute(self, context):        # execute() is called when running the operator.
        # The original script
        WarpAO.BakeAOUsingWrapMesh()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

#Object Menu
class WrapBakerMenu(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Wrap Normal AO Baker"
    bl_idname = "object.wrap_baker"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("object.bake_wrap_normal")

        row = layout.row()
        row.operator("object.bake_wrap_ao")

#3D视图右侧工具面板
class WrapBakerPanel(bpy.types.Panel):
    bl_idname      = "WrapBaker_panel"
    bl_label       = "WrapBaker"
    bl_category    = "WrapBaker"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_context     = "objectmode"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        normal_bake_row= layout.row()
        normal_bake_row.operator("object.bake_wrap_normal",text="Bake Selected Wrap Normal")
        AO_bake_row= layout.row()
        AO_bake_row.operator("object.bake_wrap_ao",text="Bake Selected Wrap SDF AO")


#Object 下拉菜单
def menu_func(self, context):
    self.layout.label(text="Wrap Baker")
    self.layout.operator(BakeWarpNomral.bl_idname)
    self.layout.operator(BakeWarpAO.bl_idname)
    #self.layout.menu(WrapBakerMenu.bl_idname)

def register():
    #
    #bpy.types.Object.aobake_progress = bpy.props.FloatProperty( name="AO Bake Progress", subtype="PERCENTAGE",soft_min=0, soft_max=100, precision=0,)
    #bpy.types.Object.aobake_progress_label = bpy.props.StringProperty()

    bpy.utils.register_class(BakeWarpNomral)
    bpy.utils.register_class(BakeWarpAO)
    bpy.types.VIEW3D_MT_object.append(menu_func)
    #bpy.types.VIEW3D_MT_object.append(menu_func)  # Adds the new operator to an existing menu.
    #bpy.utils.register_class(WrapBakerMenu)
    bpy.utils.register_class(WrapBakerPanel)


def unregister():
    bpy.utils.unregister_class(BakeWarpNomral)
    bpy.utils.unregister_class(BakeWarpAO)
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    #bpy.utils.unregister_class(WrapBakerMenu)
    bpy.utils.unregister_class(WrapBakerPanel)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()