"""
Stage Geometry Output - Integrated Scene with Detailed Geometry
===============================================================
Generated: 2026-05-21 11:16:16
Base scene: None
Objects with detailed geometry: 19
Total detailed parts: 192

This file integrates detailed geometry into the original scene.
Objects with detailed geometry are replaced, others remain as simple bbox.
"""

import bpy
import math
import mathutils

# === HELPER FUNCTIONS ===
def clear_scene():
    """Clear all objects and collections."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for coll in bpy.data.collections:
        if coll.name != "Scene Collection":
            bpy.data.collections.remove(coll)

def create_material(name, color, alpha=1.0):
    """Create material with Blender 4.0+ compatibility."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    # Clear and recreate nodes for reliability
    for node in list(nodes):
        nodes.remove(node)
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_bsdf.inputs['Base Color'].default_value = color
    node_bsdf.inputs['Roughness'].default_value = 0.5
    if alpha < 1.0:
        node_bsdf.inputs['Alpha'].default_value = alpha
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    return mat

def create_box(name, location, dimensions, rotation=(0,0,0), material=None, collection=None, show_direction=False):
    """Create a box primitive with optional red arrow direction indicator."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dimensions
    
    if material:
        obj.data.materials.append(material)
    
    if collection:
        old_colls = list(obj.users_collection)
        collection.objects.link(obj)
        for c in old_colls:
            c.objects.unlink(obj)
    
    # Add red arrow on top of object pointing to -Y (front)
    if show_direction and dimensions[0] > 0.3 and dimensions[1] > 0.3:
        pass
    return obj
def create_cylinder(name, location, dimensions, rotation=(0,0,0), material=None, collection=None):
    """Create a cylinder primitive."""
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dimensions
    if material:
        obj.data.materials.append(material)
    if collection:
        old_colls = list(obj.users_collection)
        collection.objects.link(obj)
        for c in old_colls:
            c.objects.unlink(obj)
    return obj

def create_collection(name):
    """Create and return a collection."""
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


# ==============================================================================
# DETAILED GEOMETRY DATA (Auto-generated)
# ==============================================================================

import bmesh

DETAILED_GEOMETRY = {
    "Armchair_North": {
        "center": [-2.75, 1.0, 0.45],
        "rotation": [0.0, 0.0, 0.7853981633974483],
        "parts": [
            {"type": "box", "name": "plush_seat_cushion", "loc": [0.0, -0.11, -0.2], "dim": [0.54, 0.54, 0.18], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_square_arm", "loc": [-0.33, -0.03, -0.105], "dim": [0.14, 0.68, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_square_arm", "loc": [0.33, -0.03, -0.105], "dim": [0.14, 0.68, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "tall_padded_back_panel", "loc": [0.0, 0.32, 0.09], "dim": [0.8, 0.16, 0.72], "rot": [0, 0, 0]},
            {"type": "box", "name": "inner_back_cushion", "loc": [0.0, 0.215, 0.04], "dim": [0.54, 0.1, 0.54], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_lower_apron", "loc": [0.0, -0.34, -0.305], "dim": [0.54, 0.08, 0.15], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_front_leg", "loc": [-0.27, -0.28, -0.405], "dim": [0.08, 0.08, 0.09], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_front_leg", "loc": [0.27, -0.28, -0.405], "dim": [0.08, 0.08, 0.09], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_rear_leg", "loc": [-0.27, 0.24, -0.405], "dim": [0.08, 0.08, 0.09], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_rear_leg", "loc": [0.27, 0.24, -0.405], "dim": [0.08, 0.08, 0.09], "rot": [0, 0, 0]},
        ]
    },
    "Armchair_South": {
        "center": [-2.75, -1.0, 0.45],
        "rotation": [0.0, 0.0, 2.356194490192345],
        "parts": [
            {"type": "box", "name": "plush_seat_base", "loc": [0.0, -0.05, -0.28], "dim": [0.72, 0.62, 0.18], "rot": [0, 0, 0]},
            {"type": "box", "name": "soft_seat_cushion", "loc": [0.0, -0.1, -0.13], "dim": [0.56, 0.52, 0.14], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_padded_arm", "loc": [-0.34, -0.02, -0.16], "dim": [0.12, 0.74, 0.42], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_padded_arm", "loc": [0.34, -0.02, -0.16], "dim": [0.12, 0.74, 0.42], "rot": [0, 0, 0]},
            {"type": "box", "name": "tall_square_backrest", "loc": [0.0, 0.33, 0.04], "dim": [0.8, 0.14, 0.82], "rot": [0, 0, 0]},
            {"type": "box", "name": "inner_back_cushion", "loc": [0.0, 0.235, 0.1], "dim": [0.58, 0.07, 0.56], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_plush_apron", "loc": [0.0, -0.36, -0.25], "dim": [0.72, 0.08, 0.24], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_left_short_leg", "loc": [-0.27, -0.28, -0.41], "dim": [0.08, 0.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_right_short_leg", "loc": [0.27, -0.28, -0.41], "dim": [0.08, 0.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "rear_left_short_leg", "loc": [-0.27, 0.26, -0.41], "dim": [0.08, 0.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "rear_right_short_leg", "loc": [0.27, 0.26, -0.41], "dim": [0.08, 0.08, 0.08], "rot": [0, 0, 0]},
        ]
    },
    "Side_Table": {
        "center": [-2.75, 0.0, 0.25],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "square_tabletop_slab", "loc": [0, 0, 0.225], "dim": [0.5, 0.5, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_left_leg", "loc": [-0.2, -0.2, -0.025], "dim": [0.05, 0.05, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_right_leg", "loc": [0.2, -0.2, -0.025], "dim": [0.05, 0.05, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_left_leg", "loc": [-0.2, 0.2, -0.025], "dim": [0.05, 0.05, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_right_leg", "loc": [0.2, 0.2, -0.025], "dim": [0.05, 0.05, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_apron", "loc": [0, -0.225, 0.165], "dim": [0.4, 0.03, 0.07], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_apron", "loc": [0, 0.225, 0.165], "dim": [0.4, 0.03, 0.07], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_side_apron", "loc": [-0.225, 0, 0.165], "dim": [0.03, 0.4, 0.07], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_apron", "loc": [0.225, 0, 0.165], "dim": [0.03, 0.4, 0.07], "rot": [0, 0, 0]},
        ]
    },
    "Floor_Lamp": {
        "center": [-3.45, 2.2, 0.8],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "cylinder", "name": "round_brass_base", "loc": [0, 0, -0.78], "dim": [0.32, 0.32, 0.04], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "slender_brass_pole", "loc": [0, 0, -0.14], "dim": [0.035, 0.035, 1.24], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "lower_brass_shade_ring", "loc": [0, 0, 0.49], "dim": [0.36, 0.36, 0.025], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "warm_white_glass_cylindrical_shade", "loc": [0, 0, 0.64], "dim": [0.34, 0.34, 0.3], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "inner_glowing_glass_diffuser", "loc": [0, 0, 0.64], "dim": [0.24, 0.24, 0.26], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "upper_brass_shade_ring", "loc": [0, 0, 0.79], "dim": [0.36, 0.36, 0.02], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "small_brass_top_finial", "loc": [0, 0, 0.78], "dim": [0.04, 0.04, 0.04], "rot": [0, 0, 0]},
        ]
    },
    "Bed": {
        "center": [0.0, 1.45, 0.3],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "light_beige_upholstered_headboard", "loc": [0, 0.99, 0], "dim": [1.8, 0.12, 0.6], "rot": [0, 0, 0]},
            {"type": "box", "name": "bed_base_platform", "loc": [0, -0.08, -0.24], "dim": [1.72, 1.9, 0.12], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_side_rail", "loc": [-0.87, -0.08, -0.14], "dim": [0.06, 1.92, 0.2], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_rail", "loc": [0.87, -0.08, -0.14], "dim": [0.06, 1.92, 0.2], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_foot_rail", "loc": [0, -1.01, -0.14], "dim": [1.78, 0.08, 0.2], "rot": [0, 0, 0]},
            {"type": "box", "name": "white_mattress", "loc": [0, -0.08, -0.07], "dim": [1.66, 1.82, 0.22], "rot": [0, 0, 0]},
            {"type": "box", "name": "white_top_linen_duvet", "loc": [0, -0.15, 0.065], "dim": [1.72, 1.62, 0.07], "rot": [0, 0, 0]},
            {"type": "box", "name": "taupe_folded_throw_blanket_at_foot", "loc": [0, -0.76, 0.115], "dim": [1.72, 0.36, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_taupe_pillow", "loc": [-0.43, 0.55, 0.14], "dim": [0.56, 0.32, 0.12], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_taupe_pillow", "loc": [0.43, 0.55, 0.14], "dim": [0.56, 0.32, 0.12], "rot": [0, 0, 0]},
            {"type": "box", "name": "center_white_pillow", "loc": [0, 0.72, 0.12], "dim": [0.62, 0.26, 0.1], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "front_left_short_bed_leg", "loc": [-0.72, -0.88, -0.27], "dim": [0.08, 0.08, 0.06], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "front_right_short_bed_leg", "loc": [0.72, -0.88, -0.27], "dim": [0.08, 0.08, 0.06], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "back_left_short_bed_leg", "loc": [-0.72, 0.72, -0.27], "dim": [0.08, 0.08, 0.06], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "back_right_short_bed_leg", "loc": [0.72, 0.72, -0.27], "dim": [0.08, 0.08, 0.06], "rot": [0, 0, 0]},
        ]
    },
    "Nightstand_North": {
        "center": [-1.2, 2.3, 0.25],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "top_surface_slab", "loc": [0, 0, 0.225], "dim": [0.5, 0.4, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "main_wood_cabinet_body", "loc": [0, 0.01, -0.025], "dim": [0.46, 0.36, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "upper_drawer_front", "loc": [0, -0.19, 0.085], "dim": [0.42, 0.02, 0.13], "rot": [0, 0, 0]},
            {"type": "box", "name": "lower_drawer_front", "loc": [0, -0.19, -0.085], "dim": [0.42, 0.02, 0.13], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "upper_drawer_handle", "loc": [0, -0.191, 0.085], "dim": [0.018, 0.018, 0.22], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "lower_drawer_handle", "loc": [0, -0.191, -0.085], "dim": [0.018, 0.018, 0.22], "rot": [0, 1.5708, 0]},
            {"type": "box", "name": "recessed_toe_kick", "loc": [0, -0.08, -0.225], "dim": [0.36, 0.16, 0.05], "rot": [0, 0, 0]},
        ]
    },
    "Nightstand_South": {
        "center": [1.2, 2.3, 0.25],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "top_worktop_slab", "loc": [0, 0, 0.225], "dim": [0.5, 0.4, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_side_panel", "loc": [-0.235, 0, -0.025], "dim": [0.03, 0.38, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_panel", "loc": [0.235, 0, -0.025], "dim": [0.03, 0.38, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_panel", "loc": [0, 0.185, -0.025], "dim": [0.47, 0.03, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_panel", "loc": [0, 0, -0.235], "dim": [0.47, 0.38, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "upper_drawer_front", "loc": [0, -0.1875, 0.08], "dim": [0.43, 0.025, 0.18], "rot": [0, 0, 0]},
            {"type": "box", "name": "lower_drawer_front", "loc": [0, -0.1875, -0.12], "dim": [0.43, 0.025, 0.2], "rot": [0, 0, 0]},
            {"type": "box", "name": "center_drawer_gap", "loc": [0, -0.199, -0.01], "dim": [0.43, 0.006, 0.015], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "upper_drawer_handle", "loc": [0, -0.194, 0.08], "dim": [0.012, 0.012, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "lower_drawer_handle", "loc": [0, -0.194, -0.12], "dim": [0.012, 0.012, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "box", "name": "front_toe_kick", "loc": [0, -0.16, -0.225], "dim": [0.38, 0.04, 0.05], "rot": [0, 0, 0]},
        ]
    },
    "Bench": {
        "center": [0.0, 0.1999999999999999, 0.225],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "upholstered_seat_cushion", "loc": [0, 0, 0.185], "dim": [1.2, 0.4, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "upholstered_base_panel", "loc": [0, 0, -0.01], "dim": [1.08, 0.32, 0.31], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_apron", "loc": [0, -0.185, 0.035], "dim": [1.12, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_apron", "loc": [0, 0.185, 0.035], "dim": [1.12, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_apron", "loc": [-0.565, 0, 0.035], "dim": [0.03, 0.34, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_apron", "loc": [0.565, 0, 0.035], "dim": [0.03, 0.34, 0.16], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "front_left_short_leg", "loc": [-0.48, -0.14, -0.145], "dim": [0.07, 0.07, 0.16], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "front_right_short_leg", "loc": [0.48, -0.14, -0.145], "dim": [0.07, 0.07, 0.16], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "back_left_short_leg", "loc": [-0.48, 0.14, -0.145], "dim": [0.07, 0.07, 0.16], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "back_right_short_leg", "loc": [0.48, 0.14, -0.145], "dim": [0.07, 0.07, 0.16], "rot": [0, 0, 0]},
        ]
    },
    "Media_Console": {
        "center": [0.0, -2.275, 0.25],
        "rotation": [0.0, 0.0, 3.141592653589793],
        "parts": [
            {"type": "box", "name": "top_worktop_slab", "loc": [0, 0, 0.225], "dim": [1.8, 0.45, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "main_wood_console_body", "loc": [0, 0, -0.025], "dim": [1.76, 0.41, 0.45], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_left_door_panel", "loc": [-0.66, -0.215, -0.035], "dim": [0.4, 0.02, 0.34], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_mid_left_drawer_panel", "loc": [-0.22, -0.215, -0.035], "dim": [0.4, 0.02, 0.34], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_mid_right_drawer_panel", "loc": [0.22, -0.215, -0.035], "dim": [0.4, 0.02, 0.34], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_right_door_panel", "loc": [0.66, -0.215, -0.035], "dim": [0.4, 0.02, 0.34], "rot": [0, 0, 0]},
            {"type": "box", "name": "thin_shadow_gap_between_front_panels_1", "loc": [-0.44, -0.226, -0.035], "dim": [0.015, 0.008, 0.35], "rot": [0, 0, 0]},
            {"type": "box", "name": "thin_shadow_gap_between_front_panels_2", "loc": [0, -0.226, -0.035], "dim": [0.015, 0.008, 0.35], "rot": [0, 0, 0]},
            {"type": "box", "name": "thin_shadow_gap_between_front_panels_3", "loc": [0.44, -0.226, -0.035], "dim": [0.015, 0.008, 0.35], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "left_panel_handle", "loc": [-0.66, -0.216, 0.055], "dim": [0.018, 0.018, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "mid_left_panel_handle", "loc": [-0.22, -0.216, 0.055], "dim": [0.018, 0.018, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "mid_right_panel_handle", "loc": [0.22, -0.216, 0.055], "dim": [0.018, 0.018, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "right_panel_handle", "loc": [0.66, -0.216, 0.055], "dim": [0.018, 0.018, 0.18], "rot": [0, 1.5708, 0]},
            {"type": "box", "name": "recessed_toe_kick", "loc": [0, -0.12, -0.225], "dim": [1.55, 0.2, 0.05], "rot": [0, 0, 0]},
        ]
    },
    "Plant": {
        "center": [-1.45, -2.2, 0.4],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "cylinder", "name": "dark_grey_circular_planter_body", "loc": [0, 0, -0.27], "dim": [0.34, 0.34, 0.26], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "dark_grey_planter_top_rim", "loc": [0, 0, -0.12], "dim": [0.38, 0.38, 0.04], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "dark_soil_surface", "loc": [0, 0, -0.09], "dim": [0.3, 0.3, 0.025], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "central_plant_stem", "loc": [0, 0, 0.035], "dim": [0.035, 0.035, 0.25], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "left_plant_stem", "loc": [-0.07, 0.02, 0.015], "dim": [0.022, 0.022, 0.2], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "right_plant_stem", "loc": [0.07, -0.015, 0.015], "dim": [0.022, 0.022, 0.2], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "central_bushy_green_leaves", "loc": [0, 0, 0.18], "dim": [0.3, 0.3, 0.3], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "top_bushy_green_leaves", "loc": [0.01, 0.01, 0.28], "dim": [0.24, 0.24, 0.24], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "left_bushy_green_leaves", "loc": [-0.11, 0.015, 0.13], "dim": [0.25, 0.25, 0.25], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "right_bushy_green_leaves", "loc": [0.11, -0.01, 0.14], "dim": [0.25, 0.25, 0.25], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "front_bushy_green_leaves", "loc": [0, -0.11, 0.14], "dim": [0.24, 0.24, 0.24], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "back_bushy_green_leaves", "loc": [0.005, 0.11, 0.13], "dim": [0.24, 0.24, 0.24], "rot": [0, 0, 0]},
        ]
    },
    "Wardrobe_East": {
        "center": [3.45, 0.9, 1.2],
        "rotation": [0.0, 0.0, -1.5707963267948966],
        "parts": [
            {"type": "box", "name": "left_side_panel", "loc": [-0.98, 0, 0], "dim": [0.04, 0.6, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_panel", "loc": [0.98, 0, 0], "dim": [0.04, 0.6, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_panel", "loc": [0, 0.28, 0], "dim": [2.0, 0.04, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_panel", "loc": [0, 0, 1.18], "dim": [2.0, 0.6, 0.04], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_panel", "loc": [0, 0, -1.18], "dim": [2.0, 0.6, 0.04], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_vertical_divider", "loc": [-0.34, 0, 0], "dim": [0.04, 0.56, 2.32], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_vertical_divider", "loc": [0.46, 0, 0], "dim": [0.04, 0.56, 2.32], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_shelf_1", "loc": [-0.66, -0.005, -0.55], "dim": [0.56, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_shelf_2", "loc": [-0.66, -0.005, 0.05], "dim": [0.56, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_shelf_3", "loc": [-0.66, -0.005, 0.65], "dim": [0.56, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_shelf_1", "loc": [0.72, -0.005, -0.55], "dim": [0.44, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_shelf_2", "loc": [0.72, -0.005, 0.05], "dim": [0.44, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_shelf_3", "loc": [0.72, -0.005, 0.65], "dim": [0.44, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "box", "name": "hanging_bay_upper_shelf", "loc": [0.06, -0.005, 0.95], "dim": [0.72, 0.54, 0.03], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "hanging_rail", "loc": [0.06, -0.08, 0.72], "dim": [0.035, 0.035, 0.68], "rot": [0, 1.5708, 0]},
            {"type": "box", "name": "hanging_clothing_left", "loc": [-0.16, -0.1, 0.32], "dim": [0.18, 0.06, 0.72], "rot": [0, 0, 0]},
            {"type": "box", "name": "hanging_clothing_center", "loc": [0.06, -0.1, 0.27], "dim": [0.2, 0.06, 0.82], "rot": [0, 0, 0]},
            {"type": "box", "name": "hanging_clothing_right", "loc": [0.28, -0.1, 0.34], "dim": [0.17, 0.06, 0.68], "rot": [0, 0, 0]},
        ]
    },
    "Wardrobe_North": {
        "center": [3.0, 2.2, 1.2],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "left_side_panel", "loc": [-0.73, 0, 0], "dim": [0.04, 0.6, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_panel", "loc": [0.73, 0, 0], "dim": [0.04, 0.6, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_panel", "loc": [0, 0.285, 0], "dim": [1.5, 0.03, 2.4], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_panel", "loc": [0, 0, 1.18], "dim": [1.5, 0.6, 0.04], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_panel", "loc": [0, 0, -1.18], "dim": [1.5, 0.6, 0.04], "rot": [0, 0, 0]},
            {"type": "box", "name": "upper_shelf", "loc": [0, 0, 0.82], "dim": [1.42, 0.54, 0.035], "rot": [0, 0, 0]},
            {"type": "box", "name": "lower_shelf", "loc": [0, 0, -0.82], "dim": [1.42, 0.54, 0.035], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "hanging_clothes_rail", "loc": [0, -0.03, 0.55], "dim": [0.035, 0.035, 1.3], "rot": [0, 1.5708, 0]},
            {"type": "box", "name": "left_front_stile", "loc": [-0.73, -0.285, 0], "dim": [0.055, 0.03, 2.32], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_front_stile", "loc": [0.73, -0.285, 0], "dim": [0.055, 0.03, 2.32], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_front_rail", "loc": [0, -0.285, 1.13], "dim": [1.46, 0.03, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_front_rail", "loc": [0, -0.285, -1.13], "dim": [1.46, 0.03, 0.08], "rot": [0, 0, 0]},
        ]
    },
    "Closet_Bench": {
        "center": [2.75, 0.0, 0.225],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "wooden_bench_top_slab", "loc": [0, 0, 0.195], "dim": [0.4, 1.2, 0.06], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_left_leg", "loc": [-0.15, -0.51, -0.03], "dim": [0.06, 0.06, 0.39], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_right_leg", "loc": [0.15, -0.51, -0.03], "dim": [0.06, 0.06, 0.39], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_left_leg", "loc": [-0.15, 0.51, -0.03], "dim": [0.06, 0.06, 0.39], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_right_leg", "loc": [0.15, 0.51, -0.03], "dim": [0.06, 0.06, 0.39], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_side_support_apron", "loc": [-0.18, 0, 0.11], "dim": [0.04, 1.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_side_support_apron", "loc": [0.18, 0, 0.11], "dim": [0.04, 1.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_end_support_apron", "loc": [0, -0.56, 0.11], "dim": [0.32, 0.04, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_end_support_apron", "loc": [0, 0.56, 0.11], "dim": [0.32, 0.04, 0.08], "rot": [0, 0, 0]},
        ]
    },
    "Dresser": {
        "center": [3.5, -0.8, 0.45],
        "rotation": [0.0, 0.0, -1.5707963267948966],
        "parts": [
            {"type": "box", "name": "dresser_main_carcass", "loc": [0, 0.015, -0.035], "dim": [1.16, 0.46, 0.79], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_surface_slab", "loc": [0, 0, 0.42], "dim": [1.2, 0.5, 0.06], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_plinth_base", "loc": [0, 0.03, -0.425], "dim": [1.12, 0.38, 0.05], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_drawer_top", "loc": [0, -0.235, 0.255], "dim": [1.08, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_drawer_upper_middle", "loc": [0, -0.235, 0.065], "dim": [1.08, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_drawer_lower_middle", "loc": [0, -0.235, -0.125], "dim": [1.08, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_drawer_bottom", "loc": [0, -0.235, -0.315], "dim": [1.08, 0.03, 0.16], "rot": [0, 0, 0]},
            {"type": "box", "name": "drawer_gap_horizontal_1", "loc": [0, -0.252, 0.16], "dim": [1.1, 0.01, 0.015], "rot": [0, 0, 0]},
            {"type": "box", "name": "drawer_gap_horizontal_2", "loc": [0, -0.252, -0.03], "dim": [1.1, 0.01, 0.015], "rot": [0, 0, 0]},
            {"type": "box", "name": "drawer_gap_horizontal_3", "loc": [0, -0.252, -0.22], "dim": [1.1, 0.01, 0.015], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "top_drawer_handle", "loc": [0, -0.248, 0.255], "dim": [0.025, 0.025, 0.32], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "upper_middle_drawer_handle", "loc": [0, -0.248, 0.065], "dim": [0.025, 0.025, 0.32], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "lower_middle_drawer_handle", "loc": [0, -0.248, -0.125], "dim": [0.025, 0.025, 0.32], "rot": [0, 1.5708, 0]},
            {"type": "cylinder", "name": "bottom_drawer_handle", "loc": [0, -0.248, -0.315], "dim": [0.025, 0.025, 0.32], "rot": [0, 1.5708, 0]},
        ]
    },
    "Floor_Mirror": {
        "center": [3.25, -2.0, 0.9],
        "rotation": [0.0, 0.0, -1.5707963267948966],
        "parts": [
            {"type": "box", "name": "left_wood_frame", "loc": [-0.37, 0, 0], "dim": [0.06, 0.08, 1.8], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_wood_frame", "loc": [0.37, 0, 0], "dim": [0.06, 0.08, 1.8], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_wood_frame", "loc": [0, 0, 0.86], "dim": [0.8, 0.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_wood_frame", "loc": [0, 0, -0.86], "dim": [0.8, 0.08, 0.08], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_glass_mirror_panel", "loc": [0, -0.046, 0], "dim": [0.68, 0.008, 1.64], "rot": [0, 0, 0]},
            {"type": "box", "name": "thin_backing_panel", "loc": [0, 0.043, 0], "dim": [0.72, 0.01, 1.68], "rot": [0, 0, 0]},
        ]
    },
    "Orphan_obj_004_Book": {
        "center": [-2.75, -0.08999999999999998, 0.55],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "box", "name": "page_block", "loc": [0.005, 0, 0], "dim": [0.205, 0.145, 0.076], "rot": [0, 0, 0]},
            {"type": "box", "name": "top_cover", "loc": [0, 0, 0.044], "dim": [0.22, 0.16, 0.012], "rot": [0, 0, 0]},
            {"type": "box", "name": "bottom_cover", "loc": [0, 0, -0.044], "dim": [0.22, 0.16, 0.012], "rot": [0, 0, 0]},
            {"type": "box", "name": "spine_binding", "loc": [-0.105, 0, 0], "dim": [0.01, 0.16, 0.1], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_page_edge", "loc": [0.109, 0, 0], "dim": [0.002, 0.14, 0.07], "rot": [0, 0, 0]},
        ]
    },
    "Orphan_obj_009_Table_Lamp_North": {
        "center": [-1.2, 2.2474999999999996, 0.55],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "cylinder", "name": "gold_metal_round_base", "loc": [0, 0, -0.044], "dim": [0.09, 0.07, 0.012], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "gold_metal_stem", "loc": [0, 0, -0.017], "dim": [0.014, 0.014, 0.045], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "warm_glowing_glass_bulb", "loc": [0, 0, 0.011], "dim": [0.04, 0.04, 0.04], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "warm_yellow_glass_lampshade", "loc": [0, 0, 0.0225], "dim": [0.18, 0.13, 0.055], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "gold_metal_lower_shade_rim", "loc": [0, 0, -0.004], "dim": [0.185, 0.135, 0.006], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "gold_metal_upper_shade_rim", "loc": [0, 0, 0.047], "dim": [0.16, 0.115, 0.006], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "gold_metal_top_finial", "loc": [0, 0, 0.041], "dim": [0.018, 0.018, 0.018], "rot": [0, 0, 0]},
        ]
    },
    "Orphan_obj_012_Table_Lamp_South": {
        "center": [1.2, 2.2474999999999996, 0.55],
        "rotation": [0.0, 0.0, 0.0],
        "parts": [
            {"type": "cylinder", "name": "gold_metal_base", "loc": [0, 0, -0.044], "dim": [0.085, 0.065, 0.012], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "slender_gold_stem", "loc": [0, 0, -0.017], "dim": [0.018, 0.018, 0.055], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "warm_glowing_bulb", "loc": [0, 0, 0.006], "dim": [0.04, 0.04, 0.04], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "warm_yellow_glass_lampshade", "loc": [0, 0, 0.018], "dim": [0.18, 0.13, 0.05], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "small_gold_finial", "loc": [0, 0, 0.047], "dim": [0.012, 0.012, 0.012], "rot": [0, 0, 0]},
        ]
    },
    "Orphan_obj_017_Decor_Item_Console": {
        "center": [0.592, -2.20375, 0.55],
        "rotation": [0.0, 0.0, 3.141592653589793],
        "parts": [
            {"type": "box", "name": "shallow_rectangular_display_tray_base", "loc": [0, 0, -0.045], "dim": [0.2, 0.14, 0.01], "rot": [0, 0, 0]},
            {"type": "box", "name": "front_tray_lip", "loc": [0, -0.066, -0.037], "dim": [0.2, 0.008, 0.016], "rot": [0, 0, 0]},
            {"type": "box", "name": "back_tray_lip", "loc": [0, 0.066, -0.037], "dim": [0.2, 0.008, 0.016], "rot": [0, 0, 0]},
            {"type": "box", "name": "left_tray_lip", "loc": [-0.096, 0, -0.037], "dim": [0.008, 0.14, 0.016], "rot": [0, 0, 0]},
            {"type": "box", "name": "right_tray_lip", "loc": [0.096, 0, -0.037], "dim": [0.008, 0.14, 0.016], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "rounded_ceramic_vase_body", "loc": [-0.05, -0.005, -0.0125], "dim": [0.06, 0.06, 0.055], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "narrow_ceramic_vase_neck", "loc": [-0.05, -0.005, 0.0325], "dim": [0.026, 0.026, 0.035], "rot": [0, 0, 0]},
            {"type": "cylinder", "name": "short_metal_candle_holder", "loc": [0.035, 0.025, -0.012], "dim": [0.038, 0.038, 0.056], "rot": [0, 0, 0]},
            {"type": "sphere", "name": "small_rounded_decor_orb", "loc": [0.072, -0.028, -0.018], "dim": [0.042, 0.042, 0.042], "rot": [0, 0, 0]},
            {"type": "cone", "name": "small_tapered_metal_finial", "loc": [0.035, 0.025, 0.029], "dim": [0.026, 0.026, 0.026], "rot": [0, 0, 0]},
        ]
    },
}

def create_detailed_object(name, location=None, rotation=None, material=None, collection=None):
    """Create an object with detailed geometry instead of simple bbox.
    
    Args:
        name: Object name (must exist in DETAILED_GEOMETRY)
        location: Override position (x, y, z). If None, uses DETAILED_GEOMETRY center.
        rotation: Override rotation (rx, ry, rz). If None, uses DETAILED_GEOMETRY rotation.
        material: Material to apply to all parts.
        collection: Collection to link the object to.
    """
    if name not in DETAILED_GEOMETRY:
        return None
    
    data = DETAILED_GEOMETRY[name]
    center = location if location is not None else data["center"]
    base_rot = rotation if rotation is not None else data["rotation"]
    parts = data["parts"]
    
    # Create parent empty at the object center
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.empty_display_size = 0.1
    parent.location = center
    parent.rotation_euler = base_rot
    
    if collection:
        collection.objects.link(parent)
    else:
        bpy.context.scene.collection.objects.link(parent)
    
    # Create each part
    for part in parts:
        ptype = part["type"]
        pname = f"{name}_{part['name']}"
        ploc = part["loc"]
        pdim = part["dim"]
        prot = part["rot"]
        
        mesh = bpy.data.meshes.new(pname + "_mesh")
        bm = bmesh.new()
        
        if ptype == "box":
            bmesh.ops.create_cube(bm, size=1.0)
        elif ptype == "cylinder":
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.5, radius2=0.5, depth=1.0)
        elif ptype == "sphere":
            bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.5)
        elif ptype == "cone":
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.5, radius2=0.0, depth=1.0)
        else:
            bmesh.ops.create_cube(bm, size=1.0)
        
        bm.to_mesh(mesh)
        bm.free()
        
        obj = bpy.data.objects.new(pname, mesh)
        obj.location = ploc
        obj.dimensions = pdim
        obj.rotation_euler = [r * 3.14159265 / 180 if abs(r) > 6.3 else r for r in prot]
        obj.parent = parent
        
        if material:
            obj.data.materials.append(material)
        
        if collection:
            collection.objects.link(obj)
        else:
            bpy.context.scene.collection.objects.link(obj)
    
    return parent


# === MAIN LAYOUT ENGINE ===
def run_layout_engine():
    clear_scene()
    
    # 1. Scene Setup
    SCENE_W = 7.5
    SCENE_D = 5.0
    WALL_H = 2.8
    WALL_T = 0.15
    PARTITION_T = 0.1
    
    # 2. Materials
    mat_wall = create_material("WallMat", (0.95, 0.95, 0.95, 1.0))
    mat_floor = create_material("FloorMat", (0.6, 0.4, 0.2, 1.0))
    mat_fabric = create_material("FabricMat", (0.85, 0.8, 0.75, 1.0))
    mat_wood = create_material("WoodMat", (0.4, 0.25, 0.15, 1.0))
    mat_glass = create_material("GlassMat", (0.7, 0.8, 0.9, 0.3), alpha=0.3)
    mat_mirror = create_material("MirrorMat", (0.9, 0.9, 0.9, 1.0))
    
    # 3. Architectural Shell
    coll_arch = create_collection("Architecture")
    
    # Floor
    create_box("Floor", (0, 0, -0.05), (SCENE_W, SCENE_D, 0.1), material=mat_floor, collection=coll_arch, show_direction=False)
    
    # Boundary Walls
    create_box("Wall_North", (0, SCENE_D/2 + WALL_T/2, WALL_H/2), (SCENE_W + WALL_T*2, WALL_T, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    create_box("Wall_South", (0, -SCENE_D/2 - WALL_T/2, WALL_H/2), (SCENE_W + WALL_T*2, WALL_T, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    create_box("Wall_West", (-SCENE_W/2 - WALL_T/2, 0, WALL_H/2), (WALL_T, SCENE_D, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    create_box("Wall_East", (SCENE_W/2 + WALL_T/2, 0, WALL_H/2), (WALL_T, SCENE_D, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    
    # Window on West Wall
    create_box("Window_West", (-SCENE_W/2 - WALL_T/2, 0, 1.4), (WALL_T + 0.05, 2.0, 2.0), material=mat_glass, collection=coll_arch, show_direction=False)
    
    # Interior Partitions
    # Left Partition (Between Lounge and Bedroom) at x = -1.75
    part1_x = -1.75
    create_box("Partition_Lounge_North", (part1_x, 1.65, WALL_H/2), (PARTITION_T, 1.7, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    create_box("Partition_Lounge_South", (part1_x, -1.65, WALL_H/2), (PARTITION_T, 1.7, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    # Header above the wide opening (gap from y=-0.8 to 0.8)
    create_box("Partition_Lounge_Header", (part1_x, 0, 2.65), (PARTITION_T, 1.6, 0.3), material=mat_wall, collection=coll_arch, show_direction=False)
    
    # Right Partition (Between Bedroom and Closet) at x = 1.75
    part2_x = 1.75
    create_box("Partition_Closet_Main", (part2_x, 0.6, WALL_H/2), (PARTITION_T, 3.8, WALL_H), material=mat_wall, collection=coll_arch, show_direction=False)
    # Header above the closet doorway (gap from y=-2.5 to -1.3)
    create_box("Partition_Closet_Header", (part2_x, -1.9, 2.45), (PARTITION_T, 1.2, 0.7), material=mat_wall, collection=coll_arch, show_direction=False)
    
    # 4. Zone 01: Lounge Area (West)
    coll_zone1 = create_collection("Zone_01_Lounge")
    
    # Armchair North (Faces SE)
    create_detailed_object("Armchair_North", location=(-2.75, 1.0, 0.45), rotation=(0, 0, math.pi/4), material=mat_fabric, collection=coll_zone1)
    
    # Armchair South (Faces NE)
    create_detailed_object("Armchair_South", location=(-2.75, -1.0, 0.45), rotation=(0, 0, 3*math.pi/4), material=mat_fabric, collection=coll_zone1)
    
    # Side Table (Between armchairs)
    create_detailed_object("Side_Table", location=(-2.75, 0.0, 0.25), material=mat_wood, collection=coll_zone1)
    
    # Floor Lamp (Top left corner of lounge)
    create_detailed_object("Floor_Lamp", location=(-3.45, 2.2, 0.8), material=mat_wood, collection=coll_zone1)
    
    # 5. Zone 02: Main Bedroom Area (Center)
    coll_zone2 = create_collection("Zone_02_Bedroom")
    
    # Bed (Against North Wall)
    bed_w, bed_d, bed_h = 1.8, 2.1, 0.6
    bed_y = SCENE_D/2 - bed_d/2
    create_detailed_object("Bed", location=(0.0, bed_y, bed_h/2), rotation=(0, 0, 0), material=mat_fabric, collection=coll_zone2)
    
    # Nightstands (Against North Wall)
    ns_w, ns_d, ns_h = 0.5, 0.4, 0.5
    ns_y = SCENE_D/2 - ns_d/2
    create_detailed_object("Nightstand_North", location=(-1.2, ns_y, ns_h/2), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone2)
    create_detailed_object("Nightstand_South", location=(1.2, ns_y, ns_h/2), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone2)
    
    # Bench (Foot of the bed)
    bench_w, bench_d, bench_h = 1.2, 0.4, 0.45
    bench_y = bed_y - bed_d/2 - bench_d/2
    create_detailed_object("Bench", location=(0.0, bench_y, bench_h/2), rotation=(0, 0, 0), material=mat_fabric, collection=coll_zone2)
    
    # Media Console (Against South Wall)
    mc_w, mc_d, mc_h = 1.8, 0.45, 0.5
    mc_y = -SCENE_D/2 + mc_d/2
    create_detailed_object("Media_Console", location=(0.0, mc_y, mc_h/2), rotation=(0, 0, math.pi), material=mat_wood, collection=coll_zone2)
    
    # Plant (Bottom left corner of bedroom)
    create_detailed_object("Plant", location=(-1.45, -2.2, 0.4), material=mat_fabric, collection=coll_zone2)
    
    # 6. Zone 03: Walk-in Closet / Dressing Area (East)
    coll_zone3 = create_collection("Zone_03_Closet")
    
    # Built-in Wardrobe L-Shape (Constructed from two boxes)
    # Part 1: Along East Wall
    w1_w, w1_d, w1_h = 2.0, 0.6, 2.4
    w1_x = SCENE_W/2 - w1_d/2
    w1_y = 0.9
    create_detailed_object("Wardrobe_East", location=(w1_x, w1_y, w1_h/2), rotation=(0, 0, -math.pi/2), material=mat_wood, collection=coll_zone3)
    
    # Part 2: Along North Wall
    w2_w, w2_d, w2_h = 1.5, 0.6, 2.4
    w2_x = 3.0
    w2_y = SCENE_D/2 - w2_d/2
    create_detailed_object("Wardrobe_North", location=(w2_x, w2_y, w2_h/2), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone3)
    
    # Closet Bench/Island (Center of closet)
    cb_w, cb_d, cb_h = 0.4, 1.2, 0.45
    create_detailed_object("Closet_Bench", location=(2.75, 0.0, cb_h/2), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone3)
    
    # Dresser (Against East Wall)
    dr_w, dr_d, dr_h = 1.2, 0.5, 0.9
    dr_x = SCENE_W/2 - dr_d/2
    dr_y = -0.8
    create_detailed_object("Dresser", location=(dr_x, dr_y, dr_h/2), rotation=(0, 0, -math.pi/2), material=mat_wood, collection=coll_zone3)
    
    # Floor Mirror (Against East Wall)
    fm_w, fm_d, fm_h = 0.8, 0.1, 1.8
    fm_x = 3.25
    fm_y = -2.0
    create_detailed_object("Floor_Mirror", location=(fm_x, fm_y, fm_h/2), rotation=(0, 0, -math.pi/2), material=mat_mirror, collection=coll_zone3)

    # 7. Wall Decorations
    coll_decor = create_collection("Wall_Decorations")
    mat_art = create_material("ArtMat", (0.2, 0.6, 0.8, 1.0))
    
    # Wall Art (South) - Above Media Console
    # Inner face of South Wall is at y = -2.5. Art thickness = 0.05. Center y = -2.475
    create_box("Wall_Art_South", (0.0, -2.475, 1.5), (1.2, 0.05, 0.8), rotation=(0, 0, 0), material=mat_art, collection=coll_decor, show_direction=False)
    
    # Wall Mirror (East) - Above Dresser
    # Inner face of East Wall is at x = 3.75. Mirror thickness = 0.05. Center x = 3.725
    create_box("Wall_Mirror_East", (3.725, -0.8, 1.5), (0.05, 0.8, 1.0), rotation=(0, 0, 0), material=mat_mirror, collection=coll_decor, show_direction=False)


    # Stage 7 semantic inventory orphans promoted into Stage 8 geometry
    create_detailed_object("Orphan_obj_004_Book", location=(-2.75, -0.08999999999999998, 0.55), material=None, collection=None)
    create_detailed_object("Orphan_obj_009_Table_Lamp_North", location=(-1.2, 2.2474999999999996, 0.55), material=None, collection=None)
    create_detailed_object("Orphan_obj_012_Table_Lamp_South", location=(1.2, 2.2474999999999996, 0.55), material=None, collection=None)
    create_detailed_object("Orphan_obj_017_Decor_Item_Console", location=(0.592, -2.20375, 0.55), rotation=(0.0, 0.0, 3.141592653589793), material=None, collection=None)

if __name__ == "__main__":
    run_layout_engine()