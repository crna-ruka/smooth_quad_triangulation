# SPDX-FileCopyrightText: 2025 Crna Ruka
# SPDX-License-Identifier: MIT

bl_info = {
    'name' : 'Smooth Quad Triangulation',
    'author' : 'Crna Ruka',
    'version' : (1, 0, 0),
    'blender' : (2, 93, 0),
    'location' : '3D Viewport > Mesh Edit Mode > Face Menu',
    'description' : 'Triangulates quad faces smoothly',
    'support' : 'COMMUNITY',
    'category' : 'Mesh'
}

import bpy
import time
from collections import defaultdict
from enum import Enum

def select(context, obj):
    context.view_layer.objects.active = obj
    for o in context.scene.objects:
        o.select_set(False)
    obj.select_set(True)

def ensure_op(op_func, **kwargs):
    op_name = op_func.idname_py()
    result = op_func(**kwargs)
    if result != {'FINISHED'}:
        raise Exception("Operator '" + op_name + "' failed unexpectedly: " + str(result))

def get_unique_vertices(faces, quad_index, is_alter):
    verts = faces[quad_index].vertices
    return {verts[0], verts[2]} if is_alter else {verts[1], verts[3]}

def signed_angle(normal1, normal2, position1, position2):
    distance = (position1 - position2).length
    offset = distance * 0.2
    new_distance = ((position1 + normal1 * offset) - (position2 + normal2 * offset)).length
    sign = 1 if new_distance >= distance else -1
    return sign * normal1.angle(normal2)

def opposing_faces_angle(normals, verts):
    return signed_angle(normals[0][1], normals[1][1], verts[normals[0][0]].co, verts[normals[1][0]].co)

def get_adjacent_gap(faces, adj_face_ids, sub_face_ids):
    comparison_source = []
    comparison_targets = []
    for i in adj_face_ids:
        (comparison_source if i in sub_face_ids else comparison_targets).append(i)
    if len(comparison_source) != 1:
        raise Exception('Unexpected behavior detected.')
    src_normal = faces[comparison_source[0]].normal
    adjacent_gap = 0.0
    for i in comparison_targets:
        adjacent_gap += src_normal.angle(faces[i].normal)
    return adjacent_gap

class TriangulationOrder(Enum):
    BEAUTY = 1
    FIXED = 2
    ALTERNATE = 3


class CRNA_OT_smooth_quad_triangulation(bpy.types.Operator):
    bl_idname = 'crna.smooth_quad_triangulation'
    bl_label = 'Smooth Quad Triangulation'
    bl_description = 'Triangulates quad faces smoothly'
    bl_options = {'REGISTER', 'UNDO'}
    
    use_pose_shapekey: bpy.props.BoolProperty(name='Evaluate Current Pose and Shape Keys', default=True)
    
    ANGLE_DIFF_THRESHOLD = 0.22
    ADJACENT_GAP_RATIO = 0.5
    TEMP_OBJ_NAME_PREFIX = '[TEMP]'
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.alignment = 'RIGHT'
        row.prop(self, 'use_pose_shapekey')
    
    #def invoke(self, context, event):
    #    return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        self.time_started = time.time()
        self.untouched_ngon_count = 0
        
        initial_active_object = context.active_object
        initial_selected_objects = {o for o in context.scene.objects if o.select_get()}
        objects_to_be_edited = {o for o in context.selectable_objects if o.type == 'MESH' and o.data.is_editmode}
        
        if len(objects_to_be_edited) == 0:
            return {'CANCELLED'}
        
        initial_mesh_select_mode = tuple(context.tool_settings.mesh_select_mode)
        context.tool_settings.mesh_select_mode = (False, False, True)
        results = {self.triangulate_single_object(context, o) for o in objects_to_be_edited}
        context.tool_settings.mesh_select_mode = initial_mesh_select_mode
        
        if True not in results:
            return {'CANCELLED'}
        
        ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
        for o in context.scene.objects:
            o.select_set(o in objects_to_be_edited)
        context.view_layer.objects.active = initial_active_object if initial_active_object.visible_get() else objects_to_be_edited.pop()
        
        ensure_op(bpy.ops.object.mode_set, mode='EDIT')
        for o in context.scene.objects:
            o.select_set(o in initial_selected_objects)
        
        message_untouched_ngon = ''
        if self.untouched_ngon_count > 0:
            if self.untouched_ngon_count == 1:
                message_untouched_ngon = ' There is 1 N-gon'
            else:
                message_untouched_ngon = ' There are ' + str(self.untouched_ngon_count) + ' N-gons'
            message_untouched_ngon += ' left untouched.'
        
        processing_time = time.time() - self.time_started
        self.report({'INFO'}, 'Smooth Quad Triangulation completed in ' + f'{processing_time:.2f}' + ' seconds.' + message_untouched_ngon)
        return {'FINISHED'}
    
    def triangulate_single_object(self, context, target_object):
        # Excludes non-quad faces
        self.obj = target_object
        self.obj.update_from_editmode()
        
        faces = self.obj.data.polygons
        faces_count = len(faces)
        
        # Returns False if no valid quad is selected
        selected_face_indices = [f.index for f in faces if f.select]
        selected_quad_indices = [i for i in selected_face_indices if len(faces[i].vertices) == 4]
        if len(selected_quad_indices) == 0:
            return False
        
        selected_ngon_indices = [i for i in selected_face_indices if len(faces[i].vertices) > 4]
        self.untouched_ngon_count += len(selected_ngon_indices)
        
        # Detects faces that share multiple edges
        edge_to_face = defaultdict(list)
        for f in faces:
            for e in f.edge_keys:
                edge_to_face[e].append(f.index)
        
        face_to_adjacent_faces = defaultdict(set)
        for f in faces:
            for e in f.edge_keys:
                for g in edge_to_face[e]:
                    if g != f.index:
                        face_to_adjacent_faces[f.index].add(g)
        
        doublet_quad_to_unique_vert = {}
        for i in selected_quad_indices:
            verts = faces[i].vertices
            for a in face_to_adjacent_faces[i]:
                verts_in_adj_face = set(faces[a].vertices)
                if len(verts_in_adj_face) > 4:
                    continue
                common_verts = [v for v in verts if v in verts_in_adj_face]
                if len(common_verts) == 3:
                    unique_verts = [v for v in verts if v not in verts_in_adj_face]
                    if len(unique_verts) != 1:
                        raise Exception('Unexpected behavior detected.')
                    doublet_quad_to_unique_vert[i] = unique_verts[0]
                    break
        
        doublet_quad_indices = set(doublet_quad_to_unique_vert.keys())
        viable_selected_quad_indices_list = [i for i in selected_quad_indices if i not in doublet_quad_indices]
        viable_selected_quad_indices_set = set(viable_selected_quad_indices_list)
        selected_doublet_quad_indices = [i for i in selected_quad_indices if i in doublet_quad_indices]
        
        try:
            # Duplicates objects temporarily for calculations
            duplicate_pointers = set()
            
            ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
            select(context, self.obj)
            ensure_op(bpy.ops.object.duplicate)
            self.subsurfed = context.active_object
            if self.obj.as_pointer() == self.subsurfed.as_pointer():
                raise Exception('Failed to duplicate object for calculation.')
            duplicate_pointers.add(self.subsurfed.as_pointer())
            
            if self.use_pose_shapekey:
                if self.subsurfed.data.shape_keys != None and len(self.subsurfed.data.shape_keys.key_blocks) > 0:
                    if self.subsurfed.active_shape_key == None:
                        self.subsurfed.active_shape_key_index = 0
                    ensure_op(bpy.ops.object.shape_key_remove, all=True, apply_mix=True)
                for m in self.subsurfed.modifiers:
                    if m.type == 'ARMATURE':
                        ensure_op(bpy.ops.object.modifier_apply, modifier=m.name)
                    else:
                        self.subsurfed.modifiers.remove(m)
            else:
                self.subsurfed.shape_key_clear()
                self.subsurfed.modifiers.clear()
            
            ensure_op(bpy.ops.object.duplicate)
            self.tri_fixed = context.active_object
            duplicate_pointers.add(self.tri_fixed.as_pointer())
            
            ensure_op(bpy.ops.object.duplicate)
            self.tri_alter = context.active_object
            duplicate_pointers.add(self.tri_alter.as_pointer())
            
            object_pointers = duplicate_pointers.copy()
            object_pointers.add(self.obj.as_pointer())
            if len(object_pointers) != 4:
                raise Exception('Failed to duplicate object for calculation.')
            
            self.subsurfed.name = self.TEMP_OBJ_NAME_PREFIX + self.subsurfed.name
            self.tri_fixed.name = self.TEMP_OBJ_NAME_PREFIX + self.tri_fixed.name
            self.tri_alter.name = self.TEMP_OBJ_NAME_PREFIX + self.tri_alter.name
            
            select(context, self.subsurfed)
            subsurf_mod = self.subsurfed.modifiers.new(name='[TEMP]Subdivision', type='SUBSURF')
            subsurf_mod.use_limit_surface = False
            subsurf_mod.boundary_smooth = 'PRESERVE_CORNERS'
            ensure_op(bpy.ops.object.modifier_apply, modifier=subsurf_mod.name)
            
            select(context, self.tri_fixed)
            for f in self.tri_fixed.data.polygons:
                f.select = f.index in viable_selected_quad_indices_set
            ensure_op(bpy.ops.object.mode_set, mode='EDIT')
            ensure_op(bpy.ops.mesh.quads_convert_to_tris, quad_method='FIXED')
            ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
            
            select(context, self.tri_alter)
            for f in self.tri_alter.data.polygons:
                f.select = f.index in viable_selected_quad_indices_set
            ensure_op(bpy.ops.object.mode_set, mode='EDIT')
            ensure_op(bpy.ops.mesh.quads_convert_to_tris, quad_method='FIXED_ALTERNATE')
            ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
            
            remaining_faces_count = faces_count - len(viable_selected_quad_indices_set)
            expected_triangulated_faces_count = len(viable_selected_quad_indices_set) * 2 + remaining_faces_count
            
            if len(self.tri_fixed.data.polygons) != expected_triangulated_faces_count or len(self.tri_alter.data.polygons) != expected_triangulated_faces_count:
                raise Exception("Unsupported topology: The mesh '" + self.obj.name + "' appears to have irregular topology.")
            
            # Prepares data structures
            self.triangulated_face_index = {}
            j = 0
            for i in viable_selected_quad_indices_list:
                self.triangulated_face_index[i] = j + faces_count
                j += 1
            
            self.subsurfed_face_indices = defaultdict(set)
            j = 0
            for f in faces:
                for v in f.vertices:
                    self.subsurfed_face_indices[f.index].add(j)
                    j += 1
            
            original_vertex_count = len(self.obj.data.vertices)
            self.vertex_to_sub_face_indices = defaultdict(list)
            for f in self.subsurfed.data.polygons:
                for v in f.vertices:
                    if v < original_vertex_count:
                        self.vertex_to_sub_face_indices[v].append(f.index)
            
            # Determines triangulation order
            quad_indices_fixed = []
            quad_indices_alter = []
            quad_indices_beauty = []
            
            for i in viable_selected_quad_indices_list:
                method = self.determine_triangulation_method_per_single_quad(i)
                if method == TriangulationOrder.FIXED:
                    quad_indices_fixed.append(i)
                elif method == TriangulationOrder.ALTERNATE:
                    quad_indices_alter.append(i)
                else:
                    quad_indices_beauty.append(i)
        
        finally:
            # Cleans up duplicates
            for o in context.scene.objects:
                if o.as_pointer() != self.obj.as_pointer() and o.as_pointer() in duplicate_pointers:
                    bpy.data.objects.remove(o)
        
        # Determines triangulation order for faces sharing multiple edges
        for i in selected_doublet_quad_indices:
            if doublet_quad_to_unique_vert[i] in get_unique_vertices(self.obj.data.polygons, i, True):
                quad_indices_fixed.append(i)
            else:
                quad_indices_alter.append(i)
        
        # Actual triangulation
        select(context, self.obj)
        
        if len(self.obj.modifiers) > 0:
            modifier_visibility = [m.show_viewport for m in self.obj.modifiers]
            for m in self.obj.modifiers:
                m.show_viewport = False
        
        ensure_op(bpy.ops.object.mode_set, mode='EDIT')
        ensure_op(bpy.ops.mesh.select_all, action='DESELECT')
        ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
        
        for i in quad_indices_fixed:
            faces[i].select = True
        
        ensure_op(bpy.ops.object.mode_set, mode='EDIT')
        ensure_op(bpy.ops.mesh.quads_convert_to_tris, quad_method='FIXED')
        ensure_op(bpy.ops.mesh.select_all, action='DESELECT')
        ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
        
        for i in quad_indices_alter:
            faces[i].select = True
        
        ensure_op(bpy.ops.object.mode_set, mode='EDIT')
        ensure_op(bpy.ops.mesh.quads_convert_to_tris, quad_method='FIXED_ALTERNATE')
        ensure_op(bpy.ops.mesh.select_all, action='DESELECT')
        ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
        
        if len(quad_indices_beauty) > 0:
            for i in quad_indices_beauty:
                faces[i].select = True
            
            ensure_op(bpy.ops.object.mode_set, mode='EDIT')
            ensure_op(bpy.ops.mesh.quads_convert_to_tris, quad_method='BEAUTY')
            ensure_op(bpy.ops.mesh.select_all, action='DESELECT')
            ensure_op(bpy.ops.object.mode_set, mode='OBJECT')
        
        if len(self.obj.modifiers) > 0:
            for i in range(len(self.obj.modifiers)):
                self.obj.modifiers[i].show_viewport = modifier_visibility[i]
        
        return True
    
    def triangle_normals(self, quad_index, triangulated_faces, unique_indices):
        triangle_normals = []
        for i in [quad_index, self.triangulated_face_index[quad_index]]:
            f = triangulated_faces[i]
            for v in f.vertices:
                if v in unique_indices:
                    triangle_normals.append((v, f.normal))
        return triangle_normals
    
    def determine_triangulation_method_per_single_quad(self, quad_index):
        # Chooses triangulation order based on similarity to subsurfed opposing face angles
        unique_indices_fixed = get_unique_vertices(self.obj.data.polygons, quad_index, False)
        unique_indices_alter = get_unique_vertices(self.obj.data.polygons, quad_index, True)
        
        triangle_normals_fixed = self.triangle_normals(quad_index, self.tri_fixed.data.polygons, unique_indices_fixed)
        triangle_normals_alter = self.triangle_normals(quad_index, self.tri_alter.data.polygons, unique_indices_alter)
        
        opposing_faces_angle_fixed = opposing_faces_angle(triangle_normals_fixed, self.tri_fixed.data.vertices)
        opposing_faces_angle_alter = opposing_faces_angle(triangle_normals_alter, self.tri_alter.data.vertices)
        
        sub_normals_fixed = []
        sub_normals_alter = []
        
        sub_face_ids = self.subsurfed_face_indices[quad_index]
        for i in sub_face_ids:
            f = self.subsurfed.data.polygons[i]
            for v in f.vertices:
                if v in unique_indices_fixed:
                    sub_normals_fixed.append((v, f.normal))
                elif v in unique_indices_alter:
                    sub_normals_alter.append((v, f.normal))
        
        opposing_faces_angle_sub_fixed = opposing_faces_angle(sub_normals_fixed, self.subsurfed.data.vertices)
        opposing_faces_angle_sub_alter = opposing_faces_angle(sub_normals_alter, self.subsurfed.data.vertices)
        
        angle_diff_sum_fixed = abs(opposing_faces_angle_fixed - opposing_faces_angle_sub_fixed) + abs(opposing_faces_angle_sub_alter)
        angle_diff_sum_alter = abs(opposing_faces_angle_alter - opposing_faces_angle_sub_alter) + abs(opposing_faces_angle_sub_fixed)
        
        if abs(angle_diff_sum_fixed - angle_diff_sum_alter) > self.ANGLE_DIFF_THRESHOLD:
            return TriangulationOrder.FIXED if angle_diff_sum_fixed < angle_diff_sum_alter else TriangulationOrder.ALTERNATE
        
        # Processes flatter surface
        favor_in_fixed = angle_diff_sum_alter - angle_diff_sum_fixed
        
        adjacent_gap_fixed = 0
        adjacent_gap_alter = 0
        
        for i in range(2):
            adj_face_ids = self.vertex_to_sub_face_indices[triangle_normals_fixed[i][0]]
            adjacent_gap_fixed += get_adjacent_gap(self.subsurfed.data.polygons, adj_face_ids, sub_face_ids)
        
        for i in range(2):
            adj_face_ids = self.vertex_to_sub_face_indices[triangle_normals_alter[i][0]]
            adjacent_gap_alter += get_adjacent_gap(self.subsurfed.data.polygons, adj_face_ids, sub_face_ids)
        
        favor_in_fixed += self.ADJACENT_GAP_RATIO * (adjacent_gap_fixed - adjacent_gap_alter)
        return TriangulationOrder.BEAUTY if favor_in_fixed == 0.0 else TriangulationOrder.FIXED if favor_in_fixed > 0 else TriangulationOrder.ALTERNATE


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator(CRNA_OT_smooth_quad_triangulation.bl_idname)

def register():
    bpy.utils.register_class(CRNA_OT_smooth_quad_triangulation)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(menu_func)

def unregister():
    bpy.utils.unregister_class(CRNA_OT_smooth_quad_triangulation)
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(menu_func)

if __name__ == '__main__':
    register()
