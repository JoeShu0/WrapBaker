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

#Basic View toggle options

import bpy

def toggle_normal_view(self, context):
    #self.vert_normal_view = not self.vert_normal_view
    if(self.vert_normal_view):
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        bpy.context.space_data.shading.type = 'SOLID'
        bpy.context.space_data.shading.light = 'MATCAP'
        bpy.context.space_data.shading.studio_light = 'check_normal+y.exr'
    else:
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        bpy.context.space_data.shading.light = 'STUDIO'
    #print("Toggle normal view~")

def toggle_color_view(self, context):
    #self.vert_normal_view = not self.vert_normal_view
    if(self.vert_color_view):
        bpy.context.space_data.shading.light = 'FLAT'
        bpy.ops.object.mode_set(mode="VERTEX_PAINT", toggle=False)
    else:
        bpy.context.space_data.shading.light = 'STUDIO'
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
    #print("Toggle normal view~")

#update function must be lowercase with underscroe
bpy.types.Scene.vert_normal_view = bpy.props.BoolProperty(default = False, update = toggle_normal_view)
bpy.types.Scene.vert_color_view = bpy.props.BoolProperty(default = False, update = toggle_color_view)