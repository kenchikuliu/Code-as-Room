#!/usr/bin/env python3
"""Audit a Code-as-Room run directory with Blender.

This is a local, model-free quality gate. It checks that stage artifacts exist,
the final Blender script compiles, Blender can execute it, and the resulting
scene has the expected render-critical pieces: camera, lights, materials, and
loaded texture images.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import py_compile
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


STAGE_ARTIFACTS = {
    "stage1": ["stage1_output.json"],
    "stage2": ["stage2_output.json", "stage2_skeleton.json"],
    "stage3": ["stage3_output.py"],
    "stage4": ["stage4_output.py"],
    "stage5_describe": ["describe_output.json"],
    "stage6_geometry": ["geometry_output.py"],
    "stage7_small_objects": ["small_objects_output.py", "small_objects.json"],
    "stage10_material": ["material_output.py", "material_config.json"],
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _choose_stage12(run_dir: Path, requested: str | None) -> Path:
    if requested:
        path = Path(requested)
        if not path.is_absolute():
            path = run_dir / path
        return path
    for name in ("stage12_render_apimart", "stage12_render"):
        candidate = run_dir / name
        if (candidate / "render_output.py").is_file():
            return candidate
    return run_dir / "stage12_render"


def _stage_summary(run_dir: Path, stage12_dir: Path) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    for stage, files in STAGE_ARTIFACTS.items():
        stage_path = run_dir / stage
        present = [f for f in files if (stage_path / f).is_file()]
        stages[stage] = {
            "exists": stage_path.is_dir(),
            "required": files,
            "present": present,
            "ok": len(present) == len(files),
        }

    for stage in ("stage11_texture_apimart", "stage11_texture"):
        stage_path = run_dir / stage
        if stage_path.is_dir():
            stages[stage] = {
                "exists": True,
                "required": ["texture_output.py", "texture_manifest.json"],
                "present": [
                    f for f in ("texture_output.py", "texture_manifest.json")
                    if (stage_path / f).is_file()
                ],
                "image_count": len(list((stage_path / "images").glob("*"))) if (stage_path / "images").is_dir() else 0,
            }

    stages[stage12_dir.name] = {
        "exists": stage12_dir.is_dir(),
        "required": ["render_output.py", "render_lighting.json"],
        "present": [
            f for f in ("render_output.py", "render_lighting.json")
            if (stage12_dir / f).is_file()
        ],
        "final_render_count": len(list(stage12_dir.glob("final_render*.png"))),
    }
    return stages


def _compile_python(path: Path) -> dict[str, Any]:
    try:
        py_compile.compile(str(path), doraise=True)
        return {"ok": True}
    except py_compile.PyCompileError as exc:
        return {"ok": False, "error": str(exc)}


def _write_blender_probe(audit_dir: Path) -> Path:
    probe = audit_dir / "blender_probe.py"
    probe.write_text(
        r'''
import json
import math
import os
import traceback

import bpy
import mathutils


def _bounds_for_objects(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH" or not obj.bound_box:
            continue
        world = obj.matrix_world
        for corner in obj.bound_box:
            points.append(world @ mathutils.Vector(corner))
    if not points:
        return None
    mins = [min(p[i] for p in points) for i in range(3)]
    maxs = [max(p[i] for p in points) for i in range(3)]
    return {
        "min": [round(v, 4) for v in mins],
        "max": [round(v, 4) for v in maxs],
        "size": [round(maxs[i] - mins[i], 4) for i in range(3)],
    }


def _object_bounds(obj):
    if obj.type != "MESH" or not obj.bound_box:
        return None
    world = obj.matrix_world
    points = [world @ mathutils.Vector(corner) for corner in obj.bound_box]
    mins = [min(p[i] for p in points) for i in range(3)]
    maxs = [max(p[i] for p in points) for i in range(3)]
    return {"min": mins, "max": maxs, "size": [maxs[i] - mins[i] for i in range(3)]}


def _round_bounds(bounds):
    if not bounds:
        return None
    return {
        "min": [round(v, 4) for v in bounds["min"]],
        "max": [round(v, 4) for v in bounds["max"]],
        "size": [round(v, 4) for v in bounds["size"]],
    }


def _merge_bounds(a, b):
    if not a:
        return {"min": list(b["min"]), "max": list(b["max"]), "size": list(b["size"])}
    mins = [min(a["min"][i], b["min"][i]) for i in range(3)]
    maxs = [max(a["max"][i], b["max"][i]) for i in range(3)]
    return {"min": mins, "max": maxs, "size": [maxs[i] - mins[i] for i in range(3)]}


def _semantic_group_name(obj, empty_names):
    name = obj.name
    if "__" in name:
        return name.split("__", 1)[0]
    for empty in empty_names:
        if name.startswith(empty + "_"):
            return empty
    return name.split(".", 1)[0]


def _semantic_group_bounds():
    empty_names = sorted(
        [obj.name for obj in bpy.data.objects if obj.type == "EMPTY"],
        key=len,
        reverse=True,
    )
    groups = {}
    for obj in bpy.data.objects:
        bounds = _object_bounds(obj)
        if not bounds:
            continue
        group_name = _semantic_group_name(obj, empty_names)
        row = groups.setdefault(
            group_name,
            {"name": group_name, "bounds": None, "member_count": 0, "sample_members": []},
        )
        row["bounds"] = _merge_bounds(row["bounds"], bounds)
        row["member_count"] += 1
        if len(row["sample_members"]) < 5:
            row["sample_members"].append(obj.name)
    out = []
    for row in groups.values():
        row["bounds"] = _round_bounds(row["bounds"])
        out.append(row)
    return sorted(out, key=lambda row: row["name"].lower())


def _is_structural_group(name):
    lower = name.lower()
    if lower in {"floor", "ceiling"}:
        return True
    return any(
        token in lower
        for token in (
            "wall", "partition", "window", "glass", "curtain", "door",
            "portal", "panel", "vent",
        )
    )


def _is_collision_exempt(name):
    lower = name.lower()
    if _is_structural_group(name):
        return True
    return any(
        token in lower
        for token in (
            "rug", "runner", "carpet", "bedding", "pillow", "lamp", "decor",
            "accessory", "clothes", "plant", "mirror", "item",
        )
    )


def _xy_area(bounds):
    return max(0.0, bounds["size"][0]) * max(0.0, bounds["size"][1])


def _interval_overlap(a_min, a_max, b_min, b_max):
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def _find_floor_bounds(groups):
    for group in groups:
        if group["name"].lower() == "floor":
            return group["bounds"]
    flat = []
    for group in groups:
        bounds = group["bounds"]
        if not bounds:
            continue
        if bounds["size"][2] <= 0.12 and bounds["max"][2] <= 0.25:
            flat.append((_xy_area(bounds), bounds))
    if not flat:
        return None
    return sorted(flat, key=lambda row: row[0], reverse=True)[0][1]


def _geometry_diagnostics():
    groups = _semantic_group_bounds()
    floor_bounds = _find_floor_bounds(groups)
    floor_margin = 0.15
    below_floor = []
    out_of_floor = []
    anomalous_dimensions = []

    for group in groups:
        name = group["name"]
        bounds = group["bounds"]
        if not bounds:
            continue
        size = bounds["size"]
        if floor_bounds and not _is_structural_group(name):
            if bounds["min"][2] < floor_bounds["min"][2] - 0.05:
                below_floor.append({
                    "name": name,
                    "min_z": round(bounds["min"][2], 4),
                    "floor_min_z": round(floor_bounds["min"][2], 4),
                })
            if (
                bounds["min"][0] < floor_bounds["min"][0] - floor_margin
                or bounds["max"][0] > floor_bounds["max"][0] + floor_margin
                or bounds["min"][1] < floor_bounds["min"][1] - floor_margin
                or bounds["max"][1] > floor_bounds["max"][1] + floor_margin
            ):
                out_of_floor.append({"name": name, "bounds": bounds})
        if floor_bounds:
            if size[0] > floor_bounds["size"][0] * 1.25 or size[1] > floor_bounds["size"][1] * 1.25:
                anomalous_dimensions.append({"name": name, "reason": "larger than floor span", "bounds": bounds})
        if size[2] > 4.0:
            anomalous_dimensions.append({"name": name, "reason": "unusually tall", "bounds": bounds})

    collision_groups = [
        group for group in groups
        if group["bounds"]
        and not _is_collision_exempt(group["name"])
        and _xy_area(group["bounds"]) >= 0.12
        and group["bounds"]["size"][2] >= 0.12
    ]
    collisions = []
    for i, a in enumerate(collision_groups):
        ab = a["bounds"]
        for b in collision_groups[i + 1:]:
            bb = b["bounds"]
            x_overlap = _interval_overlap(ab["min"][0], ab["max"][0], bb["min"][0], bb["max"][0])
            y_overlap = _interval_overlap(ab["min"][1], ab["max"][1], bb["min"][1], bb["max"][1])
            z_overlap = _interval_overlap(ab["min"][2], ab["max"][2], bb["min"][2], bb["max"][2])
            if x_overlap <= 0 or y_overlap <= 0 or z_overlap <= 0:
                continue
            overlap_area = x_overlap * y_overlap
            min_area = min(_xy_area(ab), _xy_area(bb))
            if min_area <= 0:
                continue
            overlap_ratio = overlap_area / min_area
            if overlap_ratio >= 0.25:
                collisions.append({
                    "a": a["name"],
                    "b": b["name"],
                    "xy_overlap_m2": round(overlap_area, 4),
                    "z_overlap_m": round(z_overlap, 4),
                    "overlap_ratio_of_smaller": round(overlap_ratio, 4),
                })
    collisions = sorted(
        collisions,
        key=lambda row: (row["overlap_ratio_of_smaller"], row["xy_overlap_m2"]),
        reverse=True,
    )

    return {
        "floor_bounds": floor_bounds,
        "semantic_group_count": len(groups),
        "below_floor": below_floor[:30],
        "below_floor_count": len(below_floor),
        "out_of_floor": out_of_floor[:30],
        "out_of_floor_count": len(out_of_floor),
        "collision_candidates": collisions[:30],
        "collision_candidate_count": len(collisions),
        "anomalous_dimensions": anomalous_dimensions[:30],
        "anomalous_dimension_count": len(anomalous_dimensions),
    }


def _image_paths():
    out = []
    for img in bpy.data.images:
        out.append({
            "name": img.name,
            "filepath": bpy.path.abspath(img.filepath) if img.filepath else "",
            "size": list(img.size) if hasattr(img, "size") else [],
            "packed": bool(img.packed_file),
        })
    return out


def _material_image_names():
    names = set()
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeTexImage" and getattr(node, "image", None):
                names.add(node.image.name)
    return sorted(names)


def _object_sample(limit=25):
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name)[:limit]:
        rows.append({
            "name": obj.name,
            "type": obj.type,
            "location": [round(float(v), 4) for v in obj.location],
        })
    return rows


def _warnings(data):
    warnings = []
    cam = data.get("camera") or {}
    if not cam:
        warnings.append("No active scene camera.")
    elif cam.get("type") != "ORTHO":
        warnings.append("Active camera is not orthographic.")
    if data["counts"]["lights"] == 0:
        warnings.append("No lights in final scene.")
    if data["counts"]["materials"] < 5:
        warnings.append("Very few materials loaded.")
    if data["counts"]["images"] == 0:
        warnings.append("No texture images loaded.")
    names = " ".join(img["name"].lower() for img in data.get("images", []))
    for expected in ("floor", "wall"):
        if expected not in names:
            warnings.append("Expected texture image not loaded: " + expected)
    if "rug" not in names:
        warnings.append("No rug texture image loaded.")
    diagnostics = data.get("geometry_diagnostics") or {}
    if diagnostics.get("below_floor_count", 0) > 0:
        warnings.append(str(diagnostics["below_floor_count"]) + " semantic groups dip below the floor.")
    if diagnostics.get("out_of_floor_count", 0) > 0:
        warnings.append(str(diagnostics["out_of_floor_count"]) + " semantic groups extend outside the floor bounds.")
    if diagnostics.get("collision_candidate_count", 0) > 0:
        warnings.append(str(diagnostics["collision_candidate_count"]) + " coarse AABB collision candidates found.")
    return warnings


try:
    render_path = os.environ.get("AUDIT_RENDER_PATH")
    blend_path = os.environ.get("AUDIT_BLEND_PATH")
    if render_path:
        bpy.context.scene.render.filepath = render_path
        bpy.ops.render.render(write_still=True)
    if blend_path:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    cam = bpy.context.scene.camera
    data = {
        "ok": True,
        "blender_version": bpy.app.version_string,
        "render_engine": bpy.context.scene.render.engine,
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len([o for o in bpy.data.objects if o.type == "MESH"]),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "lights": len([o for o in bpy.data.objects if o.type == "LIGHT"]),
            "cameras": len([o for o in bpy.data.objects if o.type == "CAMERA"]),
            "collections": len(bpy.data.collections),
        },
        "camera": None,
        "lights": [
            {
                "name": o.name,
                "type": o.data.type,
                "energy": round(float(getattr(o.data, "energy", 0.0)), 4),
                "location": [round(float(v), 4) for v in o.location],
            }
            for o in bpy.data.objects if o.type == "LIGHT"
        ],
        "images": _image_paths(),
        "material_images": _material_image_names(),
        "scene_bounds": _bounds_for_objects(bpy.data.objects),
        "geometry_diagnostics": _geometry_diagnostics(),
        "object_sample": _object_sample(),
    }
    if cam:
        data["camera"] = {
            "name": cam.name,
            "type": cam.data.type,
            "ortho_scale": round(float(getattr(cam.data, "ortho_scale", 0.0)), 4),
            "location": [round(float(v), 4) for v in cam.location],
            "rotation_euler": [round(float(v), 4) for v in cam.rotation_euler],
        }
    data["warnings"] = _warnings(data)
except Exception as exc:
    data = {
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

with open(os.environ["AUDIT_BLENDER_JSON"], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
'''.lstrip(),
        encoding="utf-8",
    )
    return probe


def _run_blender(
    blender: Path,
    render_script: Path,
    audit_dir: Path,
    *,
    render: bool,
    save_blend: bool,
    timeout: int,
) -> dict[str, Any]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    probe_path = _write_blender_probe(audit_dir)
    blender_json = audit_dir / "blender_scene.json"
    stdout_path = audit_dir / "blender_stdout.log"
    stderr_path = audit_dir / "blender_stderr.log"
    env = os.environ.copy()
    env["AUDIT_BLENDER_JSON"] = str(blender_json)
    if render:
        env["AUDIT_RENDER_PATH"] = str(audit_dir / "audit_render.png")
    if save_blend:
        env["AUDIT_BLEND_PATH"] = str(audit_dir / "audit_scene.blend")

    cmd = [
        str(blender),
        "-b",
        "--python",
        str(render_script),
        "--python",
        str(probe_path),
    ]

    started = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr:
        proc = subprocess.run(
            cmd,
            cwd=str(render_script.parent),
            env=env,
            stdout=stdout,
            stderr=stderr,
            text=True,
            timeout=timeout,
        )
    elapsed = round(time.perf_counter() - started, 3)

    result: dict[str, Any] = {
        "command": cmd,
        "returncode": proc.returncode,
        "elapsed_sec": elapsed,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "json_path": str(blender_json),
    }
    if blender_json.is_file():
        try:
            result["scene"] = json.loads(blender_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result["scene"] = {"ok": False, "error": "invalid blender json: " + str(exc)}
    else:
        result["scene"] = {"ok": False, "error": "Blender probe did not write JSON"}

    if render:
        result["audit_render"] = str(audit_dir / "audit_render.png")
    if save_blend:
        result["audit_blend"] = str(audit_dir / "audit_scene.blend")
    return result


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}


def _score(report: dict[str, Any]) -> dict[str, Any]:
    diagnostics = report.get("blender", {}).get("scene", {}).get("geometry_diagnostics", {})
    checks = {
        "render_script_exists": bool(report.get("render_script_exists")),
        "render_script_compiles": bool(report.get("compile", {}).get("ok")),
        "blender_executed": report.get("blender", {}).get("returncode") == 0,
        "scene_probe_ok": bool(report.get("blender", {}).get("scene", {}).get("ok")),
        "has_camera": bool(report.get("blender", {}).get("scene", {}).get("camera")),
        "has_lights": report.get("blender", {}).get("scene", {}).get("counts", {}).get("lights", 0) > 0,
        "has_textures": report.get("blender", {}).get("scene", {}).get("counts", {}).get("images", 0) > 0,
    }
    checks["camera_orthographic"] = (
        report.get("blender", {}).get("scene", {}).get("camera", {}).get("type") == "ORTHO"
    )
    checks["enough_geometry"] = report.get("blender", {}).get("scene", {}).get("counts", {}).get("mesh_objects", 0) >= 50
    checks["geometry_has_floor_bounds"] = bool(diagnostics.get("floor_bounds"))
    checks["geometry_no_below_floor"] = diagnostics.get("below_floor_count", 0) == 0
    checks["geometry_no_out_of_floor"] = diagnostics.get("out_of_floor_count", 0) == 0
    checks["geometry_no_coarse_collisions"] = diagnostics.get("collision_candidate_count", 0) == 0
    checks["geometry_no_dimension_anomalies"] = diagnostics.get("anomalous_dimension_count", 0) == 0
    ok_count = sum(1 for ok in checks.values() if ok)
    return {
        "ok": all(checks.values()),
        "passed": ok_count,
        "total": len(checks),
        "checks": checks,
    }


def _write_html(report: dict[str, Any], path: Path) -> None:
    score = report["score"]
    scene = report.get("blender", {}).get("scene", {})
    counts = scene.get("counts", {})
    camera = scene.get("camera") or {}
    warnings = scene.get("warnings", [])
    images = scene.get("images", [])
    diagnostics = scene.get("geometry_diagnostics") or {}
    rows = []
    for key, value in score["checks"].items():
        rows.append(
            f"<tr><td>{html.escape(key)}</td><td>{'PASS' if value else 'FAIL'}</td></tr>"
        )
    image_rows = []
    for img in images:
        image_rows.append(
            "<tr>"
            f"<td>{html.escape(str(img.get('name', '')))}</td>"
            f"<td>{html.escape(str(img.get('size', '')))}</td>"
            f"<td>{html.escape(str(img.get('filepath', '')))}</td>"
            "</tr>"
        )
    geometry_rows = []
    for key in (
        "semantic_group_count",
        "below_floor_count",
        "out_of_floor_count",
        "collision_candidate_count",
        "anomalous_dimension_count",
    ):
        geometry_rows.append(
            f"<tr><td>{html.escape(key)}</td><td>{html.escape(str(diagnostics.get(key, '')))}</td></tr>"
        )
    warnings_html = "".join(f"<li>{html.escape(w)}</li>" for w in warnings) or "<li>None</li>"
    html_text = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Code-as-Room Audit</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    td, th {{ border: 1px solid #d5d9df; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f7; }}
    .ok {{ color: #087f5b; font-weight: 700; }}
    .bad {{ color: #c92a2a; font-weight: 700; }}
    code {{ background: #f3f5f7; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Code-as-Room Audit</h1>
  <p>Status: <span class="{'ok' if score['ok'] else 'bad'}">{'PASS' if score['ok'] else 'FAIL'}</span>
  ({score['passed']}/{score['total']} checks)</p>
  <p>Run dir: <code>{html.escape(report['run_dir'])}</code></p>
  <p>Stage 12: <code>{html.escape(report['stage12_dir'])}</code></p>

  <h2>Scene Summary</h2>
  <table>
    <tr><th>Objects</th><th>Mesh</th><th>Materials</th><th>Images</th><th>Lights</th><th>Cameras</th><th>Engine</th></tr>
    <tr>
      <td>{counts.get('objects', '')}</td>
      <td>{counts.get('mesh_objects', '')}</td>
      <td>{counts.get('materials', '')}</td>
      <td>{counts.get('images', '')}</td>
      <td>{counts.get('lights', '')}</td>
      <td>{counts.get('cameras', '')}</td>
      <td>{html.escape(str(scene.get('render_engine', '')))}</td>
    </tr>
  </table>

  <h2>Camera</h2>
  <pre>{html.escape(json.dumps(camera, indent=2, ensure_ascii=False))}</pre>

  <h2>Checks</h2>
  <table><tr><th>Check</th><th>Result</th></tr>{''.join(rows)}</table>

  <h2>Geometry Diagnostics</h2>
  <table><tr><th>Metric</th><th>Value</th></tr>{''.join(geometry_rows)}</table>
  <p>Floor bounds:</p>
  <pre>{html.escape(json.dumps(diagnostics.get('floor_bounds'), indent=2, ensure_ascii=False))}</pre>

  <h2>Warnings</h2>
  <ul>{warnings_html}</ul>

  <h2>Loaded Images</h2>
  <table><tr><th>Name</th><th>Size</th><th>Path</th></tr>{''.join(image_rows)}</table>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def audit(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    stage12_dir = _choose_stage12(run_dir, args.stage12_dir).resolve()
    render_script = stage12_dir / "render_output.py"
    audit_dir = run_dir / "audit"
    blender = Path(args.blender or os.environ.get("BLENDER", "")).resolve()

    report: dict[str, Any] = {
        "generated_at": _now(),
        "run_dir": str(run_dir),
        "stage12_dir": str(stage12_dir),
        "render_script": str(render_script),
        "blender": {"path": str(blender)},
        "stages": _stage_summary(run_dir, stage12_dir),
        "render_script_exists": render_script.is_file(),
    }

    config_path = run_dir / "run_config.json"
    if config_path.is_file():
        config = _load_json(config_path)
        if isinstance(config, dict):
            report["run_config"] = {
                k: v for k, v in config.items()
                if "key" not in k.lower() and "token" not in k.lower()
            }

    if not run_dir.is_dir():
        report["fatal"] = "run_dir does not exist"
    elif not report["render_script_exists"]:
        report["fatal"] = "render_output.py does not exist"
    elif not blender.is_file():
        report["fatal"] = "Blender executable does not exist"
    else:
        report["compile"] = _compile_python(render_script)
        if report["compile"].get("ok"):
            try:
                report["blender"] = {
                    **report["blender"],
                    **_run_blender(
                        blender,
                        render_script,
                        audit_dir,
                        render=args.render,
                        save_blend=args.save_blend,
                        timeout=args.timeout,
                    ),
                }
            except subprocess.TimeoutExpired:
                report["blender"] = {
                    **report["blender"],
                    "returncode": None,
                    "scene": {"ok": False, "error": "Blender audit timed out"},
                }
        else:
            report["blender"]["scene"] = {"ok": False, "error": "Skipped because compile failed"}

    report["score"] = _score(report)
    report_path = run_dir / "audit_report.json"
    html_path = run_dir / "audit_report.html"
    report["report_json"] = str(report_path)
    report["report_html"] = str(html_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_html(report, html_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a Code-as-Room run directory.")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory.")
    parser.add_argument("--blender", default=os.environ.get("BLENDER"), help="Path to blender executable.")
    parser.add_argument("--stage12-dir", help="Stage 12 directory name or absolute path.")
    parser.add_argument("--render", action="store_true", help="Render an audit still image.")
    parser.add_argument("--save-blend", action="store_true", help="Save an audit .blend file.")
    parser.add_argument("--timeout", type=int, default=300, help="Blender timeout in seconds.")
    args = parser.parse_args(argv)

    report = audit(args)
    score = report["score"]
    scene = report.get("blender", {}).get("scene", {})
    counts = scene.get("counts", {})
    print(f"Audit {'PASS' if score['ok'] else 'FAIL'} ({score['passed']}/{score['total']} checks)")
    if counts:
        print(
            "Scene: "
            f"{counts.get('objects', 0)} objects, "
            f"{counts.get('materials', 0)} materials, "
            f"{counts.get('images', 0)} images, "
            f"{counts.get('lights', 0)} lights"
        )
    if scene.get("warnings"):
        print("Warnings:")
        for warning in scene["warnings"]:
            print(f"  - {warning}")
    print(f"JSON: {report['report_json']}")
    print(f"HTML: {report['report_html']}")
    return 0 if score["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
