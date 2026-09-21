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
    "description": "Wrap normal and AO baker for stylized Art",
    "author": "Joe Shu",
    "version": (0, 3, 0),
    "blender": (3, 5, 0),
    "category": "Object",
}


if "bpy" in locals():
    # 必须先用旧类和旧回调卸载，再重载子模块。
    unregister()
    import importlib
    importlib.reload(BakeOps)
    importlib.reload(ViewOps)
else:
    import bpy
    from .operators import BakeOps, ViewOps

import traceback
import warnings


def _draw_bake_buttons(layout, context):
    layout.label(text="仅处理活动网格（Active Mesh），非批量选择")
    column = layout.column()
    obj = context.active_object
    column.enabled = obj is not None and obj.type == 'MESH' and context.mode == 'OBJECT'
    column.operator_context = 'INVOKE_DEFAULT'
    column.operator(BakeOps.BakeWarpNomralModal.bl_idname, text="烘焙活动网格 Wrap Normal")
    column.operator(BakeOps.BakeWarpAO.bl_idname, text="烘焙活动网格 Wrap SDF AO")


def _draw_view_options(layout, scene):
    row = layout.row()
    label = "VertNormalView ON" if scene.vert_normal_view else "VertNormalView OFF"
    row.prop(scene, 'vert_normal_view', text=label, toggle=True)
    label = "VertColorView ON" if scene.vert_color_view else "VertColorView OFF"
    row.prop(scene, 'vert_color_view', text=label, toggle=True)


class WrapBakerMenu(bpy.types.Panel):
    """保留旧面板标识；实际注册下方两个 3D 视图面板。"""
    bl_label = "Wrap Normal AO Baker"
    bl_idname = "object.wrap_baker"

    def draw(self, context):
        _draw_bake_buttons(self.layout, context)


class WRAPBAKER_PT_Panel(bpy.types.Panel):
    bl_idname = "WRAPBAKER_PT_Panel"
    bl_label = "WrapBaker"
    bl_category = "WrapBaker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_context = "objectmode"

    def draw(self, context):
        _draw_view_options(self.layout, context.scene)
        _draw_bake_buttons(self.layout, context)


class WRAPBAKER_PT_VertPaintPanel(bpy.types.Panel):
    bl_idname = "WRAPBAKER_PT_VertPaintPanel"
    bl_label = "WrapBaker"
    bl_category = "WrapBaker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_context = "vertexpaint"

    def draw(self, context):
        _draw_view_options(self.layout, context.scene)


def menu_func(self, context):
    self.layout.separator()
    self.layout.label(text="Wrap Baker")
    _draw_bake_buttons(self.layout, context)


_classes = (
    BakeOps.BakeWarpNomral,
    BakeOps.BakeWarpNomralModal,
    BakeOps.BakeWarpAO,
    WRAPBAKER_PT_Panel,
    WRAPBAKER_PT_VertPaintPanel,
)
_menu_registered = False


def register():
    global _menu_registered
    complete = False
    try:
        ViewOps.register()
        for cls in _classes:
            if not cls.is_registered:
                bpy.utils.register_class(cls)
        if not _menu_registered:
            bpy.types.VIEW3D_MT_object.append(menu_func)
            _menu_registered = True
        complete = True
    finally:
        if not complete:
            # Roll back a partial registration without masking the real cause.
            try:
                unregister()
            except Exception:
                traceback.print_exc()


def unregister():
    global _menu_registered
    # BakeOps 必须在移除操作器类之前终止会话、释放资源并恢复上下文。
    cancel_sessions = getattr(BakeOps, "cancel_all_sessions", None)
    if cancel_sessions is not None:
        cancel_sessions()
    elif any(cls.is_registered for cls in _classes):
        warnings.warn(
            "WrapBaker: BakeOps 缺少 cancel_all_sessions()；"
            "无法保证活动模态会话已清理，请先结束烘焙。",
            RuntimeWarning,
            stacklevel=2,
        )

    if _menu_registered:
        bpy.types.VIEW3D_MT_object.remove(menu_func)
        _menu_registered = False
    for cls in reversed(_classes):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
    ViewOps.unregister()


if __name__ == "__main__":
    register()
