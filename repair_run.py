#!/usr/bin/env python3
"""Deterministically repair a Code-as-Room run in Blender.

This pass is model-free. It executes the final generated Blender script, applies
conservative geometry repairs, and exports a repaired scene package.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from optimize_run import _choose_stage12, _load_json, _validate_glb_import, _zip_package


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _copy_file(src: Path, dst: Path) -> str | None:
    if not src.is_file():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def _write_repair_script(output_dir: Path) -> Path:
    script = output_dir / "repair_blender_scene.py"
    script.write_text(
        r'''
import json
import os
import traceback

import bpy
import mathutils


EPS = 1e-5


def _object_bounds(obj):
    if obj.type != "MESH" or not obj.bound_box:
        return None
    points = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
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
    if not b:
        return a
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


def _root_for_mesh(obj):
    if obj.parent is not None:
        return obj.parent
    return obj


def _group_rows():
    empty_names = sorted(
        [obj.name for obj in bpy.data.objects if obj.type == "EMPTY"],
        key=len,
        reverse=True,
    )
    rows = {}
    for obj in bpy.data.objects:
        bounds = _object_bounds(obj)
        if not bounds:
            continue
        group = _semantic_group_name(obj, empty_names)
        row = rows.setdefault(
            group,
            {
                "name": group,
                "bounds": None,
                "member_count": 0,
                "sample_members": [],
                "root_names": set(),
            },
        )
        row["bounds"] = _merge_bounds(row["bounds"], bounds)
        row["member_count"] += 1
        row["root_names"].add(_root_for_mesh(obj).name)
        if len(row["sample_members"]) < 8:
            row["sample_members"].append(obj.name)

    out = []
    for row in rows.values():
        row["root_names"] = sorted(row["root_names"])
        out.append(row)
    return sorted(out, key=lambda item: item["name"].lower())


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


def _collision_candidates(groups):
    candidates = [
        group for group in groups
        if group["bounds"]
        and not _is_collision_exempt(group["name"])
        and _xy_area(group["bounds"]) >= 0.12
        and group["bounds"]["size"][2] >= 0.12
    ]
    collisions = []
    for i, a in enumerate(candidates):
        ab = a["bounds"]
        for b in candidates[i + 1:]:
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
                    "xy_overlap_m2": overlap_area,
                    "z_overlap_m": z_overlap,
                    "overlap_ratio_of_smaller": overlap_ratio,
                })
    return sorted(
        collisions,
        key=lambda row: (row["overlap_ratio_of_smaller"], row["xy_overlap_m2"]),
        reverse=True,
    )


def _diagnostics():
    groups = _group_rows()
    floor_bounds = _find_floor_bounds(groups)
    below_floor = []
    out_of_floor = []
    anomalous = []
    floor_margin = 0.15

    for group in groups:
        bounds = group["bounds"]
        name = group["name"]
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
                out_of_floor.append({"name": name, "bounds": _round_bounds(bounds)})
        if floor_bounds:
            if size[0] > floor_bounds["size"][0] * 1.25 or size[1] > floor_bounds["size"][1] * 1.25:
                anomalous.append({"name": name, "reason": "larger than floor span", "bounds": _round_bounds(bounds)})
        if size[2] > 4.0:
            anomalous.append({"name": name, "reason": "unusually tall", "bounds": _round_bounds(bounds)})

    collisions = _collision_candidates(groups)
    return {
        "floor_bounds": _round_bounds(floor_bounds),
        "semantic_group_count": len(groups),
        "below_floor": below_floor[:50],
        "below_floor_count": len(below_floor),
        "out_of_floor": out_of_floor[:50],
        "out_of_floor_count": len(out_of_floor),
        "collision_candidates": [
            {
                "a": row["a"],
                "b": row["b"],
                "xy_overlap_m2": round(row["xy_overlap_m2"], 4),
                "z_overlap_m": round(row["z_overlap_m"], 4),
                "overlap_ratio_of_smaller": round(row["overlap_ratio_of_smaller"], 4),
            }
            for row in collisions[:50]
        ],
        "collision_candidate_count": len(collisions),
        "anomalous_dimensions": anomalous[:50],
        "anomalous_dimension_count": len(anomalous),
    }


def _move_group(group, delta, reason, repairs):
    dx, dy, dz = delta
    if abs(dx) < EPS and abs(dy) < EPS and abs(dz) < EPS:
        return False
    moved_roots = []
    for root_name in group["root_names"]:
        obj = bpy.data.objects.get(root_name)
        if obj is None:
            continue
        obj.location.x += dx
        obj.location.y += dy
        obj.location.z += dz
        moved_roots.append(root_name)
    bpy.context.view_layer.update()
    repairs.append({
        "group": group["name"],
        "reason": reason,
        "delta": [round(dx, 4), round(dy, 4), round(dz, 4)],
        "moved_roots": moved_roots,
    })
    return True


def _clamp_delta_to_floor(bounds, floor_bounds, inner_margin, outer_margin=0.15):
    dx = 0.0
    dy = 0.0
    target_min_x = floor_bounds["min"][0] + inner_margin
    target_max_x = floor_bounds["max"][0] - inner_margin
    target_min_y = floor_bounds["min"][1] + inner_margin
    target_max_y = floor_bounds["max"][1] - inner_margin
    allowed_min_x = floor_bounds["min"][0] - outer_margin
    allowed_max_x = floor_bounds["max"][0] + outer_margin
    allowed_min_y = floor_bounds["min"][1] - outer_margin
    allowed_max_y = floor_bounds["max"][1] + outer_margin
    span_x = target_max_x - target_min_x
    span_y = target_max_y - target_min_y

    if bounds["size"][0] <= span_x:
        if bounds["min"][0] < allowed_min_x:
            dx = target_min_x - bounds["min"][0]
        elif bounds["max"][0] > allowed_max_x:
            dx = target_max_x - bounds["max"][0]
    else:
        if bounds["min"][0] < allowed_min_x or bounds["max"][0] > allowed_max_x:
            dx = ((target_min_x + target_max_x) / 2.0) - ((bounds["min"][0] + bounds["max"][0]) / 2.0)

    if bounds["size"][1] <= span_y:
        if bounds["min"][1] < allowed_min_y:
            dy = target_min_y - bounds["min"][1]
        elif bounds["max"][1] > allowed_max_y:
            dy = target_max_y - bounds["max"][1]
    else:
        if bounds["min"][1] < allowed_min_y or bounds["max"][1] > allowed_max_y:
            dy = ((target_min_y + target_max_y) / 2.0) - ((bounds["min"][1] + bounds["max"][1]) / 2.0)

    return dx, dy


def _repair_floor_and_bounds(repairs):
    groups = _group_rows()
    floor_bounds = _find_floor_bounds(groups)
    if not floor_bounds:
        return
    inner_margin = float(os.environ.get("REPAIR_FLOOR_INNER_MARGIN", "0.02"))
    for group in groups:
        name = group["name"]
        bounds = group["bounds"]
        if not bounds or _is_structural_group(name):
            continue
        dz = 0.0
        if bounds["min"][2] < floor_bounds["min"][2] - 0.05:
            dz = floor_bounds["max"][2] - bounds["min"][2]
        dx, dy = _clamp_delta_to_floor(bounds, floor_bounds, inner_margin)
        _move_group(group, (dx, dy, dz), "floor_bounds", repairs)


def _repair_collisions(repairs):
    max_iter = int(os.environ.get("REPAIR_COLLISION_ITERATIONS", "8"))
    clearance = float(os.environ.get("REPAIR_COLLISION_CLEARANCE", "0.03"))

    def shifted_bounds(bounds, dx, dy):
        return {
            "min": [bounds["min"][0] + dx, bounds["min"][1] + dy, bounds["min"][2]],
            "max": [bounds["max"][0] + dx, bounds["max"][1] + dy, bounds["max"][2]],
            "size": list(bounds["size"]),
        }

    def floor_penalty(bounds, floor_bounds):
        if not floor_bounds:
            return 0.0
        margin = 0.15
        over = 0.0
        over += max(0.0, floor_bounds["min"][0] - margin - bounds["min"][0])
        over += max(0.0, bounds["max"][0] - (floor_bounds["max"][0] + margin))
        over += max(0.0, floor_bounds["min"][1] - margin - bounds["min"][1])
        over += max(0.0, bounds["max"][1] - (floor_bounds["max"][1] + margin))
        return over * 1000.0

    def collision_score(group_name, candidate_bounds, groups, floor_bounds):
        score = floor_penalty(candidate_bounds, floor_bounds)
        candidate_area = _xy_area(candidate_bounds)
        for other in groups:
            if other["name"] == group_name or _is_collision_exempt(other["name"]):
                continue
            other_bounds = other["bounds"]
            if not other_bounds:
                continue
            x_overlap = _interval_overlap(
                candidate_bounds["min"][0], candidate_bounds["max"][0],
                other_bounds["min"][0], other_bounds["max"][0],
            )
            y_overlap = _interval_overlap(
                candidate_bounds["min"][1], candidate_bounds["max"][1],
                other_bounds["min"][1], other_bounds["max"][1],
            )
            z_overlap = _interval_overlap(
                candidate_bounds["min"][2], candidate_bounds["max"][2],
                other_bounds["min"][2], other_bounds["max"][2],
            )
            if x_overlap <= 0 or y_overlap <= 0 or z_overlap <= 0:
                continue
            min_area = min(candidate_area, _xy_area(other_bounds))
            if min_area <= 0:
                continue
            ratio = (x_overlap * y_overlap) / min_area
            if ratio >= 0.25:
                score += ratio * 100.0 + (x_overlap * y_overlap)
        return score

    for iteration in range(max_iter):
        groups = _group_rows()
        floor_bounds = _find_floor_bounds(groups)
        by_name = {group["name"]: group for group in groups}
        collisions = _collision_candidates(groups)
        if not collisions:
            break
        moved = False
        for collision in collisions[:20]:
            a = by_name.get(collision["a"])
            b = by_name.get(collision["b"])
            if not a or not b:
                continue
            ab = a["bounds"]
            bb = b["bounds"]
            # Move the smaller footprint group; this keeps beds/cabinets more stable.
            moving = a if _xy_area(ab) <= _xy_area(bb) else b
            fixed = b if moving is a else a
            mb = moving["bounds"]
            fb = fixed["bounds"]
            x_overlap = _interval_overlap(mb["min"][0], mb["max"][0], fb["min"][0], fb["max"][0])
            y_overlap = _interval_overlap(mb["min"][1], mb["max"][1], fb["min"][1], fb["max"][1])
            if x_overlap <= 0 or y_overlap <= 0:
                continue
            moving_center_x = (mb["min"][0] + mb["max"][0]) / 2.0
            moving_center_y = (mb["min"][1] + mb["max"][1]) / 2.0
            fixed_center_x = (fb["min"][0] + fb["max"][0]) / 2.0
            fixed_center_y = (fb["min"][1] + fb["max"][1]) / 2.0

            # Try both members and both axes. Pick the candidate that minimizes
            # global coarse collisions after the move instead of only solving
            # the current pair.
            options = []
            for candidate, other in ((a, b), (b, a)):
                cb = candidate["bounds"]
                ob = other["bounds"]
                ccx = (cb["min"][0] + cb["max"][0]) / 2.0
                ccy = (cb["min"][1] + cb["max"][1]) / 2.0
                ocx = (ob["min"][0] + ob["max"][0]) / 2.0
                ocy = (ob["min"][1] + ob["max"][1]) / 2.0
                signs = [
                    (-1.0 if ccx <= ocx else 1.0, 0.0, x_overlap + clearance),
                    (1.0 if ccx <= ocx else -1.0, 0.0, x_overlap + clearance),
                    (0.0, -1.0 if ccy <= ocy else 1.0, y_overlap + clearance),
                    (0.0, 1.0 if ccy <= ocy else -1.0, y_overlap + clearance),
                ]
                for sx, sy, dist in signs:
                    dx = sx * dist
                    dy = sy * dist
                    shifted = shifted_bounds(cb, dx, dy)
                    if floor_bounds:
                        clamp_dx, clamp_dy = _clamp_delta_to_floor(shifted, floor_bounds, 0.02)
                        dx += clamp_dx
                        dy += clamp_dy
                        shifted = shifted_bounds(cb, dx, dy)
                    score = collision_score(candidate["name"], shifted, groups, floor_bounds)
                    options.append((score, abs(dx) + abs(dy), candidate, dx, dy, other["name"]))
            if not options:
                continue
            _score, _travel, moving, dx, dy, fixed_name = sorted(options, key=lambda item: (item[0], item[1]))[0]
            moved = _move_group(
                moving,
                (dx, dy, 0.0),
                "coarse_collision:" + fixed_name + ":iter" + str(iteration + 1),
                repairs,
            ) or moved
        if not moved:
            break


def _scene_counts():
    return {
        "objects": len(bpy.data.objects),
        "mesh_objects": len([o for o in bpy.data.objects if o.type == "MESH"]),
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "lights": len([o for o in bpy.data.objects if o.type == "LIGHT"]),
        "cameras": len([o for o in bpy.data.objects if o.type == "CAMERA"]),
    }


try:
    repairs = []
    initial = _diagnostics()
    _repair_floor_and_bounds(repairs)
    _repair_collisions(repairs)
    # Clamp again after collision pushes.
    _repair_floor_and_bounds(repairs)
    final = _diagnostics()

    preview_path = os.environ.get("REPAIR_PREVIEW_PATH")
    if preview_path:
        bpy.context.scene.render.filepath = preview_path
        bpy.ops.render.render(write_still=True)

    blend_path = os.environ.get("REPAIR_BLEND_PATH")
    if blend_path:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    glb_path = os.environ.get("REPAIR_GLB_PATH")
    glb_ok = False
    glb_error = ""
    if glb_path:
        try:
            bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB")
            glb_ok = True
        except Exception as exc:
            glb_error = str(exc)

    data = {
        "ok": True,
        "scene_counts": _scene_counts(),
        "initial_diagnostics": initial,
        "final_diagnostics": final,
        "repairs": repairs,
        "repair_count": len(repairs),
        "blend_path": blend_path,
        "glb_path": glb_path,
        "glb_ok": glb_ok,
        "glb_error": glb_error,
        "preview_path": preview_path,
    }
except Exception as exc:
    data = {
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

with open(os.environ["REPAIR_REPORT_JSON"], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
'''.lstrip(),
        encoding="utf-8",
    )
    return script


def _run_blender_repair(
    blender: Path,
    render_script: Path,
    output_dir: Path,
    *,
    render_preview: bool,
    export_glb: bool,
    timeout: int,
    collision_iterations: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    repair_script = _write_repair_script(output_dir)
    report_json = output_dir / "repair_report.json"
    stdout_path = output_dir / "repair_stdout.log"
    stderr_path = output_dir / "repair_stderr.log"

    env = os.environ.copy()
    env["REPAIR_REPORT_JSON"] = str(report_json)
    env["REPAIR_BLEND_PATH"] = str(output_dir / "repaired_scene.blend")
    env["REPAIR_COLLISION_ITERATIONS"] = str(collision_iterations)
    if export_glb:
        env["REPAIR_GLB_PATH"] = str(output_dir / "repaired_scene.glb")
    if render_preview:
        env["REPAIR_PREVIEW_PATH"] = str(output_dir / "repaired_preview.png")

    cmd = [
        str(blender),
        "-b",
        "--python",
        str(render_script),
        "--python",
        str(repair_script),
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

    result: dict[str, Any] = {
        "command": cmd,
        "returncode": proc.returncode,
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "repair_report": str(report_json),
        "blend": str(output_dir / "repaired_scene.blend"),
        "glb": str(output_dir / "repaired_scene.glb") if export_glb else None,
        "preview": str(output_dir / "repaired_preview.png") if render_preview else None,
    }
    if report_json.is_file():
        result["report"] = _load_json(report_json)
    else:
        result["report"] = {"ok": False, "error": "repair report was not written"}
    return result


def repair(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    stage12_dir = _choose_stage12(run_dir, args.stage12_dir).resolve()
    render_script = stage12_dir / "render_output.py"
    blender = Path(args.blender or os.environ.get("BLENDER", "")).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "repaired_scene"

    if not run_dir.is_dir():
        raise FileNotFoundError(f"run_dir does not exist: {run_dir}")
    if not render_script.is_file():
        raise FileNotFoundError(f"render script does not exist: {render_script}")
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable does not exist: {blender}")

    if output_dir.exists() and args.clean:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied = {
        "render_script": _copy_file(render_script, output_dir / "source" / "render_output.py"),
        "run_config": _copy_file(run_dir / "run_config.json", output_dir / "source" / "run_config.json"),
        "audit_report": _copy_file(run_dir / "audit_report.json", output_dir / "source" / "audit_report.json"),
    }

    repair_result = _run_blender_repair(
        blender,
        render_script,
        output_dir,
        render_preview=args.render_preview,
        export_glb=not args.no_glb,
        timeout=args.timeout,
        collision_iterations=args.collision_iterations,
    )

    glb_validation = None
    if args.validate_glb and not args.no_glb:
        glb_validation = _validate_glb_import(
            blender,
            output_dir / "repaired_scene.glb",
            output_dir,
            args.timeout,
        )

    report = repair_result.get("report", {})
    final_diag = report.get("final_diagnostics", {}) if isinstance(report, dict) else {}
    glb_validation_ok = None
    if glb_validation is not None:
        glb_validation_ok = (
            glb_validation.get("returncode") == 0
            and bool(glb_validation.get("validation", {}).get("ok"))
            and glb_validation.get("validation", {}).get("counts", {}).get("mesh_objects", 0) > 0
        )
    repair_ok = (
        repair_result.get("returncode") == 0
        and bool(report.get("ok"))
        and final_diag.get("below_floor_count", 0) == 0
        and final_diag.get("out_of_floor_count", 0) == 0
        and final_diag.get("collision_candidate_count", 0) == 0
    )
    if glb_validation_ok is not None:
        repair_ok = repair_ok and glb_validation_ok

    manifest = {
        "created_at": _now(),
        "source_run_dir": str(run_dir),
        "stage12_dir": str(stage12_dir),
        "output_dir": str(output_dir),
        "blender": str(blender),
        "copied_artifacts": copied,
        "repair": repair_result,
        "glb_validation": glb_validation,
        "summary": {
            "ok": repair_ok,
            "repair_count": report.get("repair_count", 0) if isinstance(report, dict) else 0,
            "scene_counts": report.get("scene_counts", {}) if isinstance(report, dict) else {},
            "initial": report.get("initial_diagnostics", {}) if isinstance(report, dict) else {},
            "final": final_diag,
            "glb_ok": bool(report.get("glb_ok")) if isinstance(report, dict) else False,
            "glb_import_ok": glb_validation_ok,
        },
    }
    manifest_path = output_dir / "repair_manifest.json"
    manifest["repair_manifest"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.zip:
        zip_path = _zip_package(output_dir)
        manifest["zip"] = str(zip_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair a generated Code-as-Room scene deterministically.")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory.")
    parser.add_argument("--blender", default=os.environ.get("BLENDER"), help="Path to Blender executable.")
    parser.add_argument("--stage12-dir", help="Stage 12 directory name or absolute path.")
    parser.add_argument("--output-dir", help="Repair package directory. Default: <run_dir>/repaired_scene.")
    parser.add_argument("--render-preview", action="store_true", help="Render repaired_preview.png.")
    parser.add_argument("--no-glb", action="store_true", help="Skip repaired GLB export.")
    parser.add_argument("--validate-glb", action="store_true", help="Re-import repaired_scene.glb after export.")
    parser.add_argument("--collision-iterations", type=int, default=8, help="Max coarse collision repair iterations.")
    parser.add_argument("--zip", action="store_true", help="Create repaired_scene.zip after repair.")
    parser.add_argument("--clean", action="store_true", help="Delete output dir before rebuilding it.")
    parser.add_argument("--timeout", type=int, default=300, help="Blender timeout in seconds.")
    args = parser.parse_args()

    manifest = repair(args)
    summary = manifest["summary"]
    final = summary.get("final", {})
    print(
        "Repair "
        f"{'PASS' if summary['ok'] else 'FAIL'}: "
        f"{summary.get('repair_count', 0)} repair move(s), "
        f"below_floor={final.get('below_floor_count')}, "
        f"out_of_floor={final.get('out_of_floor_count')}, "
        f"collisions={final.get('collision_candidate_count')}, "
        f"GLB import={summary.get('glb_import_ok')}"
    )
    print(f"Package: {manifest['output_dir']}")
    print(f"Manifest: {manifest['repair_manifest']}")
    if manifest.get("zip"):
        print(f"Zip: {manifest['zip']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
