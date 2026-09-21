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

import warnings

import bpy
from bpy.app.handlers import persistent


# 单独重载本模块时，也先释放旧回调和旧预览状态。
if globals().get("_registered", False):
    unregister()

_registered = False
_updating = False
_property_names = ("vert_normal_view", "vert_color_view")
# 只保留指针数值和着色快照，不长期持有可能失效的 RNA 对象引用。
_preview_states = {}


def _data_ready():
    """Blender restricts bpy.data while add-ons register (and during shutdown).

    Touching bpy.data then raises AttributeError on _RestrictData and aborts
    registration, so every data access below must be guarded.
    """
    return hasattr(bpy.data, "screens")


def _live_viewports():
    viewports = {}
    if not _data_ready():
        return viewports
    for screen in bpy.data.screens:
        for area in screen.areas:
            # 包括切换编辑器类型后暂时不活跃的 SpaceView3D，以便恢复。
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    viewports[space.as_pointer()] = (space, area)
    return viewports


def _preview_targets(scene, context):
    targets = {}
    wm = getattr(context, "window_manager", None)
    if wm is None:
        wm = getattr(bpy.context, "window_manager", None)
    for window in getattr(wm, "windows", ()):
        if window.scene != scene or window.screen is None:
            continue
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                targets[space.as_pointer()] = (space, area)

    # 支持合法的上下文覆盖；没有 VIEW_3D 上下文时无需调用任何操作器。
    area = getattr(context, "area", None)
    space = getattr(context, "space_data", None)
    if (getattr(context, "scene", None) == scene
            and area is not None and area.type == 'VIEW_3D'
            and space is not None and space.type == 'VIEW_3D'):
        targets[space.as_pointer()] = (space, area)
    return targets


def _snapshot(shading):
    return {
        "type": shading.type,
        "light": shading.light,
        "studio_light": shading.studio_light,
        "color_type": shading.color_type,
    }


def _set_studio_light(shading, name):
    if not name:
        return False
    try:
        shading.studio_light = name
    except (TypeError, ValueError) as error:
        # MatCap/Studio Light 文件可能在预览期间被移除；保留 Blender 可用默认值。
        warnings.warn(
            "WrapBaker: 无法设置 Studio Light {!r}: {}".format(name, error),
            RuntimeWarning,
            stacklevel=2,
        )
        return False
    return True


def _restore_shading(shading, state):
    shading.type = 'SOLID'
    shading.light = state["light"]
    _set_studio_light(shading, state["studio_light"])
    shading.color_type = state["color_type"]
    shading.type = state["type"]


def _restore_preview(key, viewports):
    _, state = _preview_states.pop(key)
    viewport = viewports.get(key)
    if viewport is not None:
        space, area = viewport
        try:
            _restore_shading(space.shading, state)
            area.tag_redraw()
        except ReferenceError:
            # 已销毁的视口无需恢复，也不应留下缓存。
            pass


def _restore_previews(scene_key=None):
    if not _data_ready():
        # Nothing can be restored without data access; keep the cache so a
        # later call (or the load handlers) can still clean up.
        return
    viewports = _live_viewports()
    scene_keys = {scene.as_pointer() for scene in bpy.data.scenes}
    for key, (owner, _) in tuple(_preview_states.items()):
        if key not in viewports:
            del _preview_states[key]
        elif scene_key is None or owner == scene_key or owner not in scene_keys:
            _restore_preview(key, viewports)


def _normal_matcap():
    preferences = getattr(bpy.context, "preferences", None)
    names = sorted(
        light.name for light in getattr(preferences, "studio_lights", ())
        if light.type == 'MATCAP' and "normal" in light.name.casefold()
    )
    for name in names:
        if name.casefold() == "check_normal+y.exr":
            return name
    return names[0] if names else None


def _sync_preview(scene, context):
    scene_key = scene.as_pointer()
    # 切换预览种类时先恢复原值，再重新快照，避免把上一种预览当作原始状态。
    _restore_previews(scene_key)
    if not (scene.vert_normal_view or scene.vert_color_view):
        return

    targets = _preview_targets(scene, context)
    matcap = _normal_matcap() if scene.vert_normal_view else None
    if targets and scene.vert_normal_view and matcap is None:
        warnings.warn(
            "WrapBaker: 未找到 normal 相关 MatCap；回退到 SOLID/STUDIO，"
            "此时不是法线颜色预览。",
            RuntimeWarning,
            stacklevel=2,
        )

    for key, (space, area) in targets.items():
        # 一个视口只保留一份原始设置；场景切换后不可继承其他场景的预览快照。
        if key in _preview_states:
            _restore_preview(key, targets)
        try:
            shading = space.shading
            _preview_states[key] = (scene_key, _snapshot(shading))
            shading.type = 'SOLID'
            if scene.vert_color_view:
                shading.light = 'FLAT'
                shading.color_type = 'VERTEX'
            elif matcap is not None:
                shading.light = 'MATCAP'
                if not _set_studio_light(shading, matcap):
                    shading.light = 'STUDIO'
            else:
                shading.light = 'STUDIO'
            area.tag_redraw()
        except ReferenceError:
            _preview_states.pop(key, None)


def _toggle_preview(scene, context, enabled_property, other_property):
    global _updating
    if _updating:
        return
    _updating = True
    try:
        if getattr(scene, enabled_property) and getattr(scene, other_property):
            setattr(scene, other_property, False)
        _sync_preview(scene, context)
    finally:
        _updating = False


def toggle_normal_view(self, context):
    _toggle_preview(self, context, "vert_normal_view", "vert_color_view")


def toggle_color_view(self, context):
    _toggle_preview(self, context, "vert_color_view", "vert_normal_view")


def _reset_scene_flags():
    global _updating
    if not _data_ready():
        return
    previous = _updating
    _updating = True
    try:
        for scene in bpy.data.scenes:
            for name in _property_names:
                if hasattr(bpy.types.Scene, name):
                    scene.property_unset(name)
    finally:
        _updating = previous


@persistent
def _load_pre(_dummy):
    _restore_previews()
    _reset_scene_flags()


@persistent
def _load_post(_dummy):
    # 新文件不能继承旧文件的视口指针或旧版保存的预览开关。
    _preview_states.clear()
    _reset_scene_flags()


def register():
    global _registered
    if _registered:
        return
    unregister()
    complete = False
    try:
        bpy.types.Scene.vert_normal_view = bpy.props.BoolProperty(
            default=False,
            options={'SKIP_SAVE'},
            update=toggle_normal_view,
        )
        bpy.types.Scene.vert_color_view = bpy.props.BoolProperty(
            default=False,
            options={'SKIP_SAVE'},
            update=toggle_color_view,
        )
        _reset_scene_flags()
        if _load_pre not in bpy.app.handlers.load_pre:
            bpy.app.handlers.load_pre.append(_load_pre)
        if _load_post not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_load_post)
        _registered = True
        complete = True
    finally:
        if not complete:
            unregister()


def unregister():
    global _registered
    _restore_previews()
    _reset_scene_flags()
    for handlers, callback in (
        (bpy.app.handlers.load_pre, _load_pre),
        (bpy.app.handlers.load_post, _load_post),
    ):
        if callback in handlers:
            handlers.remove(callback)
    for name in _property_names:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    _preview_states.clear()
    _registered = False
