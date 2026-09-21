# ##### BEGIN GPL LICENSE BLOCK #####
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
# ##### END GPL LICENSE BLOCK #####

"""Wrap normal / signed-distance AO baker. Blender 3.5+ public APIs only."""
import math
from array import array

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

_WRAP = "_wrapbaker_wrap_object"
_OWNER = "_wrapbaker_owner"
_MOD = "_wrapbaker_normal_modifier"
_COLOR = "_wrapbaker_ao_attribute"
_SESSIONS = set()
_EPS = 1.0e-8


def _alive(obj):
    try:
        return obj is not None and bpy.data.objects.get(obj.name) == obj
    except ReferenceError:
        return False


def _validate(context):
    obj = context.view_layer.objects.active
    if not obj or obj.type != 'MESH' or context.mode != 'OBJECT':
        raise ValueError("Select an editable mesh in Object Mode.")
    if obj.library or obj.data.library or obj.override_library or obj.data.override_library:
        raise ValueError("Linked/overridden meshes are not supported; make a local copy first.")
    if not obj.data.vertices or not obj.data.polygons:
        raise ValueError("The active mesh has no faces.")
    if abs(obj.matrix_world.determinant()) < _EPS:
        raise ValueError("The object transform is singular (zero scale).")
    return obj


def _poll(context):
    obj = context.active_object
    return (not _SESSIONS and context.mode == 'OBJECT' and obj is not None
            and obj.type == 'MESH' and not obj.library and not obj.data.library
            and not obj.override_library and not obj.data.override_library)


def _new_socket(group, name, direction):
    # NodeTree.inputs/outputs were removed in Blender 4.0.
    if hasattr(group, 'interface') and hasattr(group.interface, 'new_socket'):
        return group.interface.new_socket(name=name, in_out=direction,
                                          socket_type='NodeSocketGeometry')
    sockets = group.inputs if direction == 'INPUT' else group.outputs
    return sockets.new('NodeSocketGeometry', name)


def _select_voxel_amount(node):
    """Resolution mode is a node property before 5.2 and a menu socket after.

    Identifiers also differ: 'VOXEL_AMOUNT' (property) vs 'Amount' (menu).
    """
    if hasattr(node, 'resolution_mode'):
        node.resolution_mode = 'VOXEL_AMOUNT'
        return
    socket = node.inputs.get('Resolution Mode')
    if socket is None:
        return
    items = getattr(socket.bl_rna.properties.get('default_value'), 'enum_items', None)
    names = [item.identifier for item in items] if items else []
    for candidate in ('VOXEL_AMOUNT', 'Amount'):
        if candidate in names:
            socket.default_value = candidate
            return
    # Unknown future enum: keep Blender's own default rather than guessing.


def new_GeometryNodes_group():
    """Private per-wrap group: editing one preview cannot alter another object."""
    group = bpy.data.node_groups.new('GeometryNodes_VMV', 'GeometryNodeTree')
    try:
        _new_socket(group, 'Mesh', 'INPUT')
        _new_socket(group, 'Mesh', 'OUTPUT')
        input_node = group.nodes.new('NodeGroupInput')
        extrude = group.nodes.new('GeometryNodeExtrudeMesh')
        extrude.name = 'VMV_ExtrudeNode'
        extrude.mode = 'FACES'
        extrude.inputs['Offset Scale'].default_value = 0.5
        extrude.inputs['Individual'].default_value = False
        to_volume = group.nodes.new('GeometryNodeMeshToVolume')
        _select_voxel_amount(to_volume)
        to_volume.inputs['Voxel Amount'].default_value = 32.0
        to_mesh = group.nodes.new('GeometryNodeVolumeToMesh')
        output_node = group.nodes.new('NodeGroupOutput')
        output_node.is_active_output = True
        group.links.new(input_node.outputs['Mesh'], extrude.inputs['Mesh'])
        group.links.new(extrude.outputs['Mesh'], to_volume.inputs['Mesh'])
        group.links.new(to_volume.outputs['Volume'], to_mesh.inputs['Volume'])
        group.links.new(to_mesh.outputs['Mesh'], output_node.inputs['Mesh'])
        return group
    except Exception:
        bpy.data.node_groups.remove(group)
        raise


def _remove_mesh(mesh):
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def _remove_group(group):
    if group is not None and group.users == 0:
        bpy.data.node_groups.remove(group)


def _remove_wrap(obj):
    """Only call for a tracked temporary object or an owned, unused old shell."""
    if not _alive(obj):
        return
    mesh = obj.data
    groups = {mod.node_group for mod in obj.modifiers
              if mod.type == 'NODES' and mod.node_group is not None}
    bpy.data.objects.remove(obj, do_unlink=True)
    _remove_mesh(mesh)
    for group in groups:
        _remove_group(group)


def _find_wrap(source):
    obj = source.get(_WRAP)
    if _alive(obj) and obj.type == 'MESH':
        return obj
    # Read-only compatibility with old .blend files: never delete/adopt by name.
    for mod in source.modifiers:
        if mod.type == 'DATA_TRANSFER' and mod.object is not None:
            if mod.name.startswith('Post_datatrans') and mod.object.type == 'MESH':
                return mod.object
    obj = bpy.data.objects.get(source.name + '_WrapMesh')
    if obj and obj.type == 'MESH':
        names = {m.name for m in obj.modifiers}
        if {'VMVPre_Solidify', 'VMV_GeoNode', 'VMVPost_Smooth'} <= names:
            return obj
    return None


def GenerateWrapMesh(context=None, source=None):
    context = context or bpy.context
    source = source or _validate(context)
    depsgraph = context.evaluated_depsgraph_get()
    context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph),
                                          depsgraph=depsgraph)
    obj = None
    group = None
    try:
        if not mesh.polygons:
            raise ValueError("The evaluated mesh is empty.")
        # Equivalent world-space shell dimensions to the old apply-transform
        # workflow, without changing source transforms or shared mesh data.
        mesh.transform(source.matrix_world)
        if source.matrix_world.determinant() < 0:
            mesh.flip_normals()
        mesh.update()
        obj = bpy.data.objects.new(source.name + '_WrapMesh', mesh)
        context.collection.objects.link(obj)
        obj[_OWNER] = source
        obj.hide_render = True
        obj.display_type = 'WIRE'
        obj.modifiers.new('VMVPre_Solidify', 'SOLIDIFY')
        nodes = obj.modifiers.new('VMV_GeoNode', 'NODES')
        group = new_GeometryNodes_group()
        nodes.node_group = group
        smooth = obj.modifiers.new('VMVPost_Smooth', 'SMOOTH')
        smooth.iterations = 25
        context.view_layer.update()
        return obj, group.nodes['VMV_ExtrudeNode']
    except Exception:
        if obj is not None:
            _remove_wrap(obj)
        else:
            _remove_mesh(mesh)
        # If group creation succeeded but assignment failed, it has no users.
        if group is not None and bpy.data.node_groups.get(group.name) == group:
            _remove_group(group)
        raise


def _retire_old_wrap(source, old):
    if not _alive(old) or old.get(_OWNER) != source:
        return
    # Keep shells referenced elsewhere, including by other tools/constraints.
    # user_map distinguishes collection links and our own source reference.
    users = bpy.data.user_map(subset={old}).get(old, set())
    for user in users:
        if isinstance(user, bpy.types.Collection):
            continue
        # user_map includes the scene's structural object membership as well
        # as collection membership. Do not mistake that for an external user.
        if isinstance(user, bpy.types.Scene):
            if user.camera == old or any(marker.camera == old for marker in user.timeline_markers):
                return
            if any(value == old for value in user.values()):
                return
            continue
        return
    _remove_wrap(old)


class WrapSession:
    """A transaction owning only new resources until confirm. No global undo."""
    def __init__(self, context):
        self.source = _validate(context)
        self.context = context
        self.area = context.area
        self.wrap = None
        self.node = None
        self.finished = False
        self.closed = False
        _SESSIONS.add(self)
        try:
            self.wrap, self.node = GenerateWrapMesh(context, self.source)
        except Exception:
            _SESSIONS.discard(self)
            raise

    def set_offset(self, value):
        if self.closed or not _alive(self.source) or not _alive(self.wrap):
            raise ValueError("The preview object is no longer available.")
        self.node.inputs['Offset Scale'].default_value = max(0.0, value)
        if self.area:
            self.area.tag_redraw()

    def confirm(self):
        if self.closed or not _alive(self.source) or not _alive(self.wrap):
            raise ValueError("The source or preview was removed.")
        context = self.context
        context.view_layer.update()
        graph = context.evaluated_depsgraph_get()
        baked = bpy.data.meshes.new_from_object(self.wrap.evaluated_get(graph), depsgraph=graph)
        if not baked.polygons:
            _remove_mesh(baked)
            raise ValueError("The wrap evaluated to an empty mesh; increase the offset.")
        group = self.node.id_data
        previous_mesh = self.wrap.data
        self.wrap.modifiers.clear()
        self.wrap.data = baked
        _remove_mesh(previous_mesh)
        _remove_group(group)
        self.node = None
        source = self.source
        old_wrap = _find_wrap(source)
        old_name = source.get(_MOD, '')
        old_modifier = source.modifiers.get(old_name) if old_name else None
        if old_modifier is not None and not (
            old_modifier.type == 'DATA_TRANSFER' and old_modifier.object == old_wrap
            and _alive(old_wrap) and old_wrap.get(_OWNER) == source
        ):
            old_modifier = None
        original_mesh = source.data
        isolated_mesh = None
        old_smooth = getattr(original_mesh, 'use_auto_smooth', None)
        modifier = None
        old_wrap_property = source.get(_WRAP)
        old_mod_property = source.get(_MOD)
        try:
            if old_smooth is not None:
                if source.data.users > 1:
                    isolated_mesh = source.data.copy()
                    source.data = isolated_mesh
                source.data.use_auto_smooth = True
            modifier = source.modifiers.new('Post_datatrans', 'DATA_TRANSFER')
            modifier.use_loop_data = True
            modifier.data_types_loops = {'CUSTOM_NORMAL'}
            modifier.loop_mapping = 'POLYINTERP_NEAREST'
            modifier.object = self.wrap
            modifier.use_object_transform = True
            self.wrap.hide_set(True)
            source[_WRAP] = self.wrap
            source[_MOD] = modifier.name
            context.view_layer.update()
        except Exception:
            if modifier is not None:
                source.modifiers.remove(modifier)
            for key, value in ((_WRAP, old_wrap_property), (_MOD, old_mod_property)):
                if value is None:
                    if key in source:
                        del source[key]
                else:
                    source[key] = value
            if isolated_mesh is not None:
                source.data = original_mesh
                _remove_mesh(isolated_mesh)
            elif old_smooth is not None:
                source.data.use_auto_smooth = old_smooth
            raise
        # Commit succeeded: only retire resources created by this plugin.
        if old_modifier is not None:
            source.modifiers.remove(old_modifier)
        self.finished = True
        self.close()
        _retire_old_wrap(source, old_wrap)
        return self.wrap

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if not self.finished:
                _remove_wrap(self.wrap)
        finally:
            _SESSIONS.discard(self)
            if self.area:
                try:
                    self.area.header_text_set(None)
                    self.area.tag_redraw()
                except ReferenceError:
                    pass


def cancel_all_sessions():
    for session in tuple(_SESSIONS):
        session.close()


def WrapSelectedObjectTranferNormal(context=None):
    session = WrapSession(context or bpy.context)
    try:
        return session.confirm()
    finally:
        session.close()


# Signed-distance AO: same sampling and squared min/max remap as the original.
def getRayCastDirections():
    bm = bmesh.new()
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        return [vert.co.copy().normalized() for vert in bm.verts]
    finally:
        bm.free()


def _world_bvh(context, obj):
    hidden = obj.hide_viewport
    hidden_layer = obj.hide_get()
    mesh = None
    try:
        obj.hide_viewport = False
        obj.hide_set(False)
        context.view_layer.update()
        graph = context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(poly.vertices) for poly in mesh.polygons]
        if not vertices or not polygons:
            raise ValueError("Wrap mesh has no evaluated faces.")
        if evaluated.matrix_world.determinant() < 0:
            polygons = [tuple(reversed(poly)) for poly in polygons]
        tree = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
        return tree, vertices
    finally:
        if mesh is not None:
            evaluated.to_mesh_clear()
        obj.hide_viewport = hidden
        obj.hide_set(hidden_layer)
        context.view_layer.update()


def raycastAllDirection(tree, position, directions, length):
    nearest = None
    for direction in directions:
        location, normal, index, distance = tree.ray_cast(position, direction, length)
        if location is not None:
            value = math.copysign(distance, -direction.dot(normal))
            if nearest is None or abs(value) < abs(nearest):
                nearest = value
    return nearest


def _normalize_distances(distances):
    if not distances:
        raise ValueError("The mesh has no vertices.")
    if any(value is None or not math.isfinite(value) for value in distances):
        missing = sum(value is None or not math.isfinite(value) for value in distances)
        raise ValueError("%d vertices missed the wrap. Increase the wrap offset; colors were not changed." % missing)
    lo, hi = min(distances), max(distances)
    span = hi - lo
    if span <= max(_EPS, max(abs(lo), abs(hi)) * 1.0e-6):
        # A constant field has no contrast: choose neutral unoccluded white.
        return [1.0] * len(distances)
    return [((value - lo) / span) ** 2 for value in distances]


def saveSDasVertexColor(obj, distances, wm=None):
    if len(distances) != len(obj.data.vertices):
        raise ValueError("AO vertex count does not match the source mesh.")
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in distances):
        raise ValueError("AO values must be finite and in [0, 1].")
    original = obj.data
    mesh = original.copy()
    try:
        attributes = mesh.color_attributes
        name = mesh.get(_COLOR, '')
        color = attributes.get(name) if name else None
        if color is None or color.domain != 'POINT' or color.data_type != 'FLOAT_COLOR':
            # Preserve pre-existing Color/Attribute (and arbitrary artist layers).
            name = 'Color' if mesh.attributes.get('Color') is None else 'WrapBaker_AO'
            color = attributes.new(name=name, type='FLOAT_COLOR', domain='POINT')
        values = array('f', (component for value in distances for component in (value, value, value, 1.0)))
        color.data.foreach_set('color', values)
        attributes.active_color = color
        attributes.render_color_index = attributes.find(color.name)
        mesh[_COLOR] = color.name
        mesh.update()
        obj.data = mesh
    except Exception:
        _remove_mesh(mesh)
        raise
    _remove_mesh(original)
    if wm:
        wm.progress_update(100)
    return color.name


def BakeAOUsingWrapMesh(context=None):
    context = context or bpy.context
    source = _validate(context)
    wm = context.window_manager
    wrap = _find_wrap(source)
    created = False
    wm.progress_begin(0, 100)
    try:
        if wrap is None:
            wrap, node = GenerateWrapMesh(context, source)
            created = True
        if context.view_layer.objects.get(wrap.name) != wrap:
            raise ValueError("The wrap is not in the active view layer.")
        tree, vertices = _world_bvh(context, wrap)
        positions = [source.matrix_world @ vert.co for vert in source.data.vertices]
        all_positions = vertices + positions
        low = Vector(tuple(min(p[i] for p in all_positions) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in all_positions) for i in range(3)))
        length = max((high - low).length * 2.0, _EPS)
        directions = getRayCastDirections()
        distances = []
        for index, position in enumerate(positions):
            distances.append(raycastAllDirection(tree, position, directions, length))
            wm.progress_update(55.0 * (index + 1) / len(positions))
        values = _normalize_distances(distances)
        name = saveSDasVertexColor(source, values, wm)
        if created:
            wrap.hide_set(True)
            source[_WRAP] = wrap
        return name
    except Exception:
        if created:
            _remove_wrap(wrap)
        raise
    finally:
        wm.progress_end()


class BakeWarpNomral(bpy.types.Operator):
    """Generate a wrap and transfer normals to the active mesh"""
    bl_idname = 'object.bake_wrap_normal'
    bl_label = 'Bake Wrap Normal'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll(context)

    def execute(self, context):
        try:
            WrapSelectedObjectTranferNormal(context)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class BakeWarpAO(bpy.types.Operator):
    """Bake signed-distance AO into a color attribute on the active mesh"""
    bl_idname = 'object.bake_wrap_ao'
    bl_label = 'Bake Wrap SDF AO'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll(context)

    def execute(self, context):
        try:
            name = BakeAOUsingWrapMesh(context)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'AO written to ' + name)
        return {'FINISHED'}


class BakeWarpNomralModal(bpy.types.Operator):
    """Move mouse to adjust the wrap; left click confirms, Esc/right click cancels"""
    bl_idname = 'object.bake_wrap_normal_modal'
    bl_label = 'Bake Wrap Normal'
    # No REGISTER: this interactive operation is not a redo-panel operation.
    bl_options = {'UNDO', 'BLOCKING'}

    # No custom __init__/__del__: Blender 4.4+ owns RNA construction.
    @classmethod
    def poll(cls, context):
        return _poll(context)

    def execute(self, context):
        # EXEC_DEFAULT is also valid for scripts/background smoke tests.
        try:
            WrapSelectedObjectTranferNormal(context)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        if not context.area or context.area.type != 'VIEW_3D' or not context.window:
            self.report({'ERROR'}, 'Start interactive wrapping in a 3D View.')
            return {'CANCELLED'}
        self._session = None
        self._initial_mouse_x = event.mouse_x
        self._initial_offset = 0.5
        try:
            self._session = WrapSession(context)
            context.area.header_text_set('WrapBaker: move mouse | Left click: confirm | Esc/right click: cancel')
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        except Exception as error:
            self.cancel(context)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def modal(self, context, event):
        if self._session is None or self._session.closed:
            return {'CANCELLED'}
        try:
            if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
                self.cancel(context)
                return {'CANCELLED'}
            if event.type == 'MOUSEMOVE':
                value = self._initial_offset + (event.mouse_x - self._initial_mouse_x) * 0.00125
                self._session.set_offset(value)
            elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                self._session.confirm()
                return {'FINISHED'}
        except Exception as error:
            self.cancel(context)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        session = getattr(self, '_session', None)
        if session:
            session.close()
