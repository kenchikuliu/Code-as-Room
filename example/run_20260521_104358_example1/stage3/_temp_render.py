
import bpy
import sys
import math
import mathutils
import json as _json

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except:
    try:
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    except:
        bpy.context.scene.render.engine = 'CYCLES'

code_text = open("/Users/yangyixuan/Code-as-Room_github/agent_utils/pipeline_output/run_20260521_104358_example1/stage3/_temp_code.py").read()

# Inject missing helper stubs so exec() doesn't fail on undefined functions
if 'def create_collection' not in code_text:
    def create_collection(name):
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
        return coll

exec(code_text)

import re
main_func_match = re.search(r'def (run_layout_engine|main|create_scene|build_scene)\s*\(', code_text)
if main_func_match:
    func_name = main_func_match.group(1)
    exec(f"{func_name}()")

print(f"Objects: {len(bpy.data.objects)}")

_ARCH_EXACT = {'floor'}
_ARCH_PREFIX = ('wall_', 's_wall', 'e_wall', 's_window', 'e_glass')
_SKIP_NAMES = {'\u7acb\u65b9\u4f53', '\u5706\u9525', '\u5706\u67f1', '\u7403\u4f53'}
def _is_furniture(name):
    nl = name.lower()
    if nl in _ARCH_EXACT or name in _SKIP_NAMES:
        return False
    if any(nl.startswith(p) for p in _ARCH_PREFIX):
        return False
    if nl.startswith('cone') or '.' in name:
        return False
    try:
        name.encode('ascii')
    except UnicodeEncodeError:
        return False
    return True

# --- Extract layout from live scene (reliable, handles vars/expressions) ---
_layout = []
for _obj in bpy.data.objects:
    if _obj.type != 'MESH':
        continue
    if not _is_furniture(_obj.name):
        continue
    if max(_obj.dimensions) < 0.15:
        continue
    _layout.append({
        "name": _obj.name,
        "x": round(_obj.location.x, 2),
        "y": round(_obj.location.y, 2),
        "z": round(_obj.location.z, 2),
        "width": round(_obj.dimensions.x, 2),
        "depth": round(_obj.dimensions.y, 2),
        "height": round(_obj.dimensions.z, 2),
    })
with open("/Users/yangyixuan/Code-as-Room_github/agent_utils/pipeline_output/run_20260521_104358_example1/stage3/_layout.json", "w") as _f:
    _json.dump(_layout, _f, indent=2)
print(f"Layout JSON: {len(_layout)} furniture objects")

# --- Camera ---
for obj in list(bpy.data.objects):
    if obj.type == 'CAMERA':
        bpy.data.objects.remove(obj)

min_x, max_x = float('inf'), float('-inf')
min_y, max_y = float('inf'), float('-inf')
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        for v in obj.bound_box:
            try:
                world_v = obj.matrix_world @ mathutils.Vector(v)
            except:
                world_v = v
            wx = world_v.x if hasattr(world_v, 'x') else world_v[0]
            wy = world_v.y if hasattr(world_v, 'y') else world_v[1]
            min_x, max_x = min(min_x, wx), max(max_x, wx)
            min_y, max_y = min(min_y, wy), max(max_y, wy)

if min_x != float('inf'):
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    scene_width = max_x - min_x
    scene_height = max_y - min_y
    ortho_scale = max(scene_width, scene_height) * 1.2
else:
    center_x, center_y = 0, 0
    ortho_scale = 12

bpy.ops.object.camera_add(location=(center_x, center_y, 15))
cam = bpy.context.active_object
cam.rotation_euler = (0, 0, 0)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = ortho_scale
bpy.context.scene.camera = cam

# --- Lighting ---
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj)

bpy.ops.object.light_add(type='SUN', location=(center_x, center_y, 10))
sun = bpy.context.active_object
sun.data.energy = 2.5
sun.rotation_euler = (0, 0, 0)
sun.data.use_shadow = False

bpy.ops.object.light_add(type='AREA', location=(center_x, center_y, 8))
area = bpy.context.active_object
area.data.energy = 50
area.data.size = ortho_scale
area.data.use_shadow = False

if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
world_nodes = bpy.context.scene.world.node_tree.nodes
bg_node = world_nodes.get('Background')
if bg_node:
    bg_node.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    bg_node.inputs['Strength'].default_value = 0.5

# --- Labels (furniture only, skip architecture) ---
_RENDER_LABELS = True
_text_size = ortho_scale * 0.022
_label_objs = []
_label_mat = bpy.data.materials.new(name="_LabelMat")
_label_mat.use_nodes = True
_lb = _label_mat.node_tree.nodes.get('Principled BSDF')
if _lb:
    _lb.inputs['Base Color'].default_value = (0.05, 0.02, 0.02, 1)

if _RENDER_LABELS:
    for _obj in list(bpy.data.objects):
        if _obj.type != 'MESH':
            continue
        if not _is_furniture(_obj.name):
            continue
        if max(_obj.dimensions) < 0.15:
            continue
        _tz = _obj.location.z + _obj.dimensions.z / 2 + 0.15
        bpy.ops.object.text_add(location=(_obj.location.x, _obj.location.y, _tz))
        _t = bpy.context.active_object
        _t.data.body = _obj.name
        _t.data.size = _text_size
        _t.data.align_x = 'CENTER'
        _t.data.align_y = 'CENTER'
        _t.name = f"_lbl_{_obj.name}"
        _t.data.materials.append(_label_mat)
        _label_objs.append(_t)
print(f"Labels: {len(_label_objs)} (furniture only)")

# --- Render settings ---
if hasattr(bpy.context.scene, 'eevee'):
    bpy.context.scene.eevee.taa_render_samples = 64
    if hasattr(bpy.context.scene.eevee, 'use_gtao'):
        bpy.context.scene.eevee.use_gtao = False
    if hasattr(bpy.context.scene.eevee, 'use_soft_shadows'):
        bpy.context.scene.eevee.use_soft_shadows = False
    if hasattr(bpy.context.scene.eevee, 'use_shadows'):
        bpy.context.scene.eevee.use_shadows = False

bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = "/Users/yangyixuan/Code-as-Room_github/agent_utils/pipeline_output/run_20260521_104358_example1/stage3/render_topdown.png"
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.film_transparent = False
bpy.context.scene.view_layers[0].use_pass_combined = True

bpy.ops.render.render(write_still=True)

# --- Cleanup: remove all label objects ---
for _t in _label_objs:
    bpy.data.objects.remove(_t, do_unlink=True)
print("Labels removed, render done!")
