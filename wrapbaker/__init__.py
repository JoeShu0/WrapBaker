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
    "blender": (3, 40, 0),
    "category": "Object",
}


if "bpy" in locals():
    import importlib
    importlib.reload(operators.BakeOps)
    importlib.reload(operators.ViewOps)

else:
    import bpy
    from .operators import BakeOps 
    from .operators import ViewOps 


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
class WRAPBAKER_PT_Panel(bpy.types.Panel):
    bl_idname      = "WRAPBAKER_PT_Panel"
    bl_label       = "WrapBaker"
    bl_category    = "WrapBaker"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_context     = "objectmode"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        wm = context.window_manager
        scene = context.scene

        view_option_column = layout.row()
        label = "VertNormalView ON" if scene.vert_normal_view else "VertNormalView OFF"
        view_option_column.prop(scene, 'vert_normal_view', text=label, toggle=True)
        label = "VertColorView ON" if scene.vert_color_view else "VertColorView OFF"
        view_option_column.prop(scene, 'vert_color_view', text=label, toggle=True)

        normal_bake_row= layout.row()
        normal_bake_row.operator("object.bake_wrap_normal_modal",text="Bake Selected Wrap Normal")
        AO_bake_row= layout.row()
        AO_bake_row.operator("object.bake_wrap_ao",text="Bake Selected Wrap SDF AO")

        #Testmodel= layout.row()
        #Testmodel.operator("object.test_modal_op",text="Test simple modal")

class WRAPBAKER_PT_VertPaintPanel(bpy.types.Panel):
    bl_idname      = "WRAPBAKER_PT_VertPaintPanel"
    bl_label       = "WrapBaker"
    bl_category    = "WrapBaker"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_context     = "vertexpaint"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        view_option_column = layout.row()
        label = "VertNormalView ON" if scene.vert_normal_view else "VertNormalView OFF"
        view_option_column.prop(scene, 'vert_normal_view', text=label, toggle=True)
        label = "VertColorView ON" if scene.vert_color_view else "VertColorView OFF"
        view_option_column.prop(scene, 'vert_color_view', text=label, toggle=True)


#Object 下拉菜单
def menu_func(self, context):
    self.layout.label(text="Wrap Baker")
    self.layout.operator(BakeOps.BakeWarpNomral.bl_idname)
    self.layout.operator(BakeOps.BakeWarpAO.bl_idname)

def register():
    bpy.utils.register_class(BakeOps.BakeWarpNomralModal)
    bpy.utils.register_class(BakeOps.BakeWarpAO)


    bpy.types.VIEW3D_MT_object.append(menu_func)
    bpy.utils.register_class(WRAPBAKER_PT_Panel)
    bpy.utils.register_class(WRAPBAKER_PT_VertPaintPanel)

def unregister():
    bpy.utils.unregister_class(BakeOps.BakeWarpNomralModal)
    bpy.utils.unregister_class(BakeOps.BakeWarpAO)


    bpy.types.VIEW3D_MT_object.remove(menu_func)
    bpy.utils.unregister_class(WRAPBAKER_PT_Panel)
    bpy.utils.unregister_class(WRAPBAKER_PT_VertPaintPanel)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()