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
    create_box("Armchair_North", (-2.75, 1.0, 0.45), (0.8, 0.8, 0.9), rotation=(0, 0, math.pi/4), material=mat_fabric, collection=coll_zone1)
    
    # Armchair South (Faces NE)
    create_box("Armchair_South", (-2.75, -1.0, 0.45), (0.8, 0.8, 0.9), rotation=(0, 0, 3*math.pi/4), material=mat_fabric, collection=coll_zone1)
    
    # Side Table (Between armchairs)
    create_box("Side_Table", (-2.75, 0.0, 0.25), (0.5, 0.5, 0.5), material=mat_wood, collection=coll_zone1)
    
    # Floor Lamp (Top left corner of lounge)
    create_cylinder("Floor_Lamp", (-3.45, 2.2, 0.8), (0.4, 0.4, 1.6), material=mat_wood, collection=coll_zone1)
    
    # 5. Zone 02: Main Bedroom Area (Center)
    coll_zone2 = create_collection("Zone_02_Bedroom")
    
    # Bed (Against North Wall)
    bed_w, bed_d, bed_h = 1.8, 2.1, 0.6
    bed_y = SCENE_D/2 - bed_d/2
    create_box("Bed", (0.0, bed_y, bed_h/2), (bed_w, bed_d, bed_h), rotation=(0, 0, 0), material=mat_fabric, collection=coll_zone2)
    
    # Nightstands (Against North Wall)
    ns_w, ns_d, ns_h = 0.5, 0.4, 0.5
    ns_y = SCENE_D/2 - ns_d/2
    create_box("Nightstand_North", (-1.2, ns_y, ns_h/2), (ns_w, ns_d, ns_h), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone2)
    create_box("Nightstand_South", (1.2, ns_y, ns_h/2), (ns_w, ns_d, ns_h), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone2)
    
    # Bench (Foot of the bed)
    bench_w, bench_d, bench_h = 1.2, 0.4, 0.45
    bench_y = bed_y - bed_d/2 - bench_d/2
    create_box("Bench", (0.0, bench_y, bench_h/2), (bench_w, bench_d, bench_h), rotation=(0, 0, 0), material=mat_fabric, collection=coll_zone2)
    
    # Media Console (Against South Wall)
    mc_w, mc_d, mc_h = 1.8, 0.45, 0.5
    mc_y = -SCENE_D/2 + mc_d/2
    create_box("Media_Console", (0.0, mc_y, mc_h/2), (mc_w, mc_d, mc_h), rotation=(0, 0, math.pi), material=mat_wood, collection=coll_zone2)
    
    # Plant (Bottom left corner of bedroom)
    create_cylinder("Plant", (-1.45, -2.2, 0.4), (0.5, 0.5, 0.8), material=mat_fabric, collection=coll_zone2)
    
    # 6. Zone 03: Walk-in Closet / Dressing Area (East)
    coll_zone3 = create_collection("Zone_03_Closet")
    
    # Built-in Wardrobe L-Shape (Constructed from two boxes)
    # Part 1: Along East Wall
    w1_w, w1_d, w1_h = 2.0, 0.6, 2.4
    w1_x = SCENE_W/2 - w1_d/2
    w1_y = 0.9
    create_box("Wardrobe_East", (w1_x, w1_y, w1_h/2), (w1_w, w1_d, w1_h), rotation=(0, 0, -math.pi/2), material=mat_wood, collection=coll_zone3)
    
    # Part 2: Along North Wall
    w2_w, w2_d, w2_h = 1.5, 0.6, 2.4
    w2_x = 3.0
    w2_y = SCENE_D/2 - w2_d/2
    create_box("Wardrobe_North", (w2_x, w2_y, w2_h/2), (w2_w, w2_d, w2_h), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone3)
    
    # Closet Bench/Island (Center of closet)
    cb_w, cb_d, cb_h = 0.4, 1.2, 0.45
    create_box("Closet_Bench", (2.75, 0.0, cb_h/2), (cb_w, cb_d, cb_h), rotation=(0, 0, 0), material=mat_wood, collection=coll_zone3)
    
    # Dresser (Against East Wall)
    dr_w, dr_d, dr_h = 1.2, 0.5, 0.9
    dr_x = SCENE_W/2 - dr_d/2
    dr_y = -0.8
    create_box("Dresser", (dr_x, dr_y, dr_h/2), (dr_w, dr_d, dr_h), rotation=(0, 0, -math.pi/2), material=mat_wood, collection=coll_zone3)
    
    # Floor Mirror (Against East Wall)
    fm_w, fm_d, fm_h = 0.8, 0.1, 1.8
    fm_x = 3.25
    fm_y = -2.0
    create_box("Floor_Mirror", (fm_x, fm_y, fm_h/2), (fm_w, fm_d, fm_h), rotation=(0, 0, -math.pi/2), material=mat_mirror, collection=coll_zone3, show_direction=False)

    # 7. Wall Decorations
    coll_decor = create_collection("Wall_Decorations")
    mat_art = create_material("ArtMat", (0.2, 0.6, 0.8, 1.0))
    
    # Wall Art (South) - Above Media Console
    # Inner face of South Wall is at y = -2.5. Art thickness = 0.05. Center y = -2.475
    create_box("Wall_Art_South", (0.0, -2.475, 1.5), (1.2, 0.05, 0.8), rotation=(0, 0, 0), material=mat_art, collection=coll_decor, show_direction=False)
    
    # Wall Mirror (East) - Above Dresser
    # Inner face of East Wall is at x = 3.75. Mirror thickness = 0.05. Center x = 3.725
    create_box("Wall_Mirror_East", (3.725, -0.8, 1.5), (0.05, 0.8, 1.0), rotation=(0, 0, 0), material=mat_mirror, collection=coll_decor, show_direction=False)

if __name__ == "__main__":
    run_layout_engine()