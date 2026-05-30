#!/usr/bin/env python3
"""Create a delivery package from a Code-as-Room run.

The optimizer is deliberately model-free: it executes the final Blender script,
exports portable assets, and writes machine-readable manifests for downstream
viewers, editors, and benchmark tooling.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


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


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}


def _copy_file(src: Path, dst: Path) -> str | None:
    if not src.is_file():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def _copy_dir(src: Path, dst: Path) -> str | None:
    if not src.is_dir():
        return None
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return str(dst)


def _latest_existing(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.is_file()]
    if not existing:
        return None
    return sorted(existing, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _write_blender_export_script(package_dir: Path) -> Path:
    script = package_dir / "optimize_blender_export.py"
    script.write_text(
        r'''
import json
import os
import traceback

import bpy
import mathutils


def _object_bounds(obj):
    if obj.type != "MESH" or not obj.bound_box:
        return None
    points = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    mins = [min(p[i] for p in points) for i in range(3)]
    maxs = [max(p[i] for p in points) for i in range(3)]
    return {
        "min": [round(v, 4) for v in mins],
        "max": [round(v, 4) for v in maxs],
        "size": [round(maxs[i] - mins[i], 4) for i in range(3)],
    }


def _merge_bounds(a, b):
    if not b:
        return a
    if not a:
        return {"min": list(b["min"]), "max": list(b["max"]), "size": list(b["size"])}
    mins = [min(a["min"][i], b["min"][i]) for i in range(3)]
    maxs = [max(a["max"][i], b["max"][i]) for i in range(3)]
    return {
        "min": [round(v, 4) for v in mins],
        "max": [round(v, 4) for v in maxs],
        "size": [round(maxs[i] - mins[i], 4) for i in range(3)],
    }


def _semantic_group_name(obj, empty_names):
    name = obj.name
    if "__" in name:
        return name.split("__", 1)[0]
    for empty in empty_names:
        if name.startswith(empty + "_"):
            return empty
    return name.split(".", 1)[0]


def _material_names(obj):
    if not getattr(obj, "data", None) or not hasattr(obj.data, "materials"):
        return []
    return [slot.name for slot in obj.data.materials if slot]


def _material_image_names(mat):
    names = []
    if not mat or not mat.use_nodes or not mat.node_tree:
        return names
    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeTexImage" and getattr(node, "image", None):
            names.append(node.image.name)
    return sorted(set(names))


def _scene_manifest():
    empty_names = sorted(
        [obj.name for obj in bpy.data.objects if obj.type == "EMPTY"],
        key=len,
        reverse=True,
    )
    objects = []
    groups = {}
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        bounds = _object_bounds(obj)
        group = _semantic_group_name(obj, empty_names)
        object_row = {
            "name": obj.name,
            "type": obj.type,
            "semantic_group": group,
            "collection_names": [c.name for c in obj.users_collection],
            "location": [round(float(v), 4) for v in obj.location],
            "rotation_euler": [round(float(v), 4) for v in obj.rotation_euler],
            "scale": [round(float(v), 4) for v in obj.scale],
            "dimensions": [round(float(v), 4) for v in obj.dimensions],
            "bounds": bounds,
            "materials": _material_names(obj),
        }
        objects.append(object_row)
        group_row = groups.setdefault(
            group,
            {
                "name": group,
                "object_count": 0,
                "mesh_count": 0,
                "types": {},
                "bounds": None,
                "sample_objects": [],
            },
        )
        group_row["object_count"] += 1
        if obj.type == "MESH":
            group_row["mesh_count"] += 1
        group_row["types"][obj.type] = group_row["types"].get(obj.type, 0) + 1
        group_row["bounds"] = _merge_bounds(group_row["bounds"], bounds)
        if len(group_row["sample_objects"]) < 8:
            group_row["sample_objects"].append(obj.name)

    cam = bpy.context.scene.camera
    materials = []
    for mat in sorted(bpy.data.materials, key=lambda item: item.name):
        materials.append({
            "name": mat.name,
            "use_nodes": bool(mat.use_nodes),
            "image_names": _material_image_names(mat),
        })
    all_groups = sorted(groups.values(), key=lambda row: row["name"].lower())
    mesh_groups = [row for row in all_groups if row["mesh_count"] > 0 and row["bounds"]]

    return {
        "blender_version": bpy.app.version_string,
        "render_engine": bpy.context.scene.render.engine,
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len([o for o in bpy.data.objects if o.type == "MESH"]),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "lights": len([o for o in bpy.data.objects if o.type == "LIGHT"]),
            "cameras": len([o for o in bpy.data.objects if o.type == "CAMERA"]),
            "all_semantic_groups": len(all_groups),
            "mesh_semantic_groups": len(mesh_groups),
        },
        "camera": None if not cam else {
            "name": cam.name,
            "type": cam.data.type,
            "ortho_scale": round(float(getattr(cam.data, "ortho_scale", 0.0)), 4),
            "location": [round(float(v), 4) for v in cam.location],
            "rotation_euler": [round(float(v), 4) for v in cam.rotation_euler],
        },
        "lights": [
            {
                "name": o.name,
                "type": o.data.type,
                "energy": round(float(getattr(o.data, "energy", 0.0)), 4),
                "location": [round(float(v), 4) for v in o.location],
            }
            for o in sorted(bpy.data.objects, key=lambda item: item.name)
            if o.type == "LIGHT"
        ],
        "images": [
            {
                "name": img.name,
                "filepath": bpy.path.abspath(img.filepath) if img.filepath else "",
                "size": list(img.size) if hasattr(img, "size") else [],
                "packed": bool(img.packed_file),
            }
            for img in sorted(bpy.data.images, key=lambda item: item.name)
        ],
        "materials": materials,
        "semantic_groups": all_groups,
        "mesh_semantic_groups": mesh_groups,
        "objects": objects,
    }


try:
    if os.environ.get("OPTIMIZE_PURGE_ORPHANS") == "1":
        try:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        except Exception:
            pass

    if os.environ.get("OPTIMIZE_PACK_TEXTURES") == "1":
        bpy.ops.file.pack_all()

    preview_path = os.environ.get("OPTIMIZE_PREVIEW_PATH")
    if preview_path:
        bpy.context.scene.render.filepath = preview_path
        bpy.ops.render.render(write_still=True)

    blend_path = os.environ.get("OPTIMIZE_BLEND_PATH")
    if blend_path:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    glb_path = os.environ.get("OPTIMIZE_GLB_PATH")
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
        "blend_path": blend_path,
        "glb_path": glb_path,
        "glb_ok": glb_ok,
        "glb_error": glb_error,
        "preview_path": preview_path,
        "scene": _scene_manifest(),
    }
except Exception as exc:
    data = {
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

with open(os.environ["OPTIMIZE_SCENE_JSON"], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
'''.lstrip(),
        encoding="utf-8",
    )
    return script


def _run_blender_export(
    blender: Path,
    render_script: Path,
    package_dir: Path,
    *,
    render_preview: bool,
    export_glb: bool,
    pack_textures: bool,
    purge_orphans: bool,
    timeout: int,
) -> dict[str, Any]:
    package_dir.mkdir(parents=True, exist_ok=True)
    script = _write_blender_export_script(package_dir)
    scene_json = package_dir / "scene_manifest.json"
    stdout_path = package_dir / "blender_export_stdout.log"
    stderr_path = package_dir / "blender_export_stderr.log"
    env = os.environ.copy()
    env["OPTIMIZE_SCENE_JSON"] = str(scene_json)
    env["OPTIMIZE_BLEND_PATH"] = str(package_dir / "scene.blend")
    if export_glb:
        env["OPTIMIZE_GLB_PATH"] = str(package_dir / "scene.glb")
    if render_preview:
        env["OPTIMIZE_PREVIEW_PATH"] = str(package_dir / "preview.png")
    if pack_textures:
        env["OPTIMIZE_PACK_TEXTURES"] = "1"
    if purge_orphans:
        env["OPTIMIZE_PURGE_ORPHANS"] = "1"

    cmd = [
        str(blender),
        "-b",
        "--python",
        str(render_script),
        "--python",
        str(script),
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
        "scene_manifest": str(scene_json),
        "blend": str(package_dir / "scene.blend"),
        "glb": str(package_dir / "scene.glb") if export_glb else None,
        "preview": str(package_dir / "preview.png") if render_preview else None,
    }
    if scene_json.is_file():
        result["scene_export"] = _load_json(scene_json)
    return result


def _write_glb_validate_script(package_dir: Path) -> Path:
    script = package_dir / "validate_glb_import.py"
    script.write_text(
        r'''
import json
import os
import traceback

import bpy


try:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    glb_path = os.environ["VALIDATE_GLB_PATH"]
    bpy.ops.import_scene.gltf(filepath=glb_path)

    mesh_objects = [o for o in bpy.data.objects if o.type == "MESH"]
    textured_materials = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        if any(node.bl_idname == "ShaderNodeTexImage" for node in mat.node_tree.nodes):
            textured_materials += 1

    data = {
        "ok": True,
        "glb_path": glb_path,
        "blender_version": bpy.app.version_string,
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len(mesh_objects),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "textured_materials": textured_materials,
            "lights": len([o for o in bpy.data.objects if o.type == "LIGHT"]),
            "cameras": len([o for o in bpy.data.objects if o.type == "CAMERA"]),
        },
        "sample_objects": [
            {"name": o.name, "type": o.type}
            for o in sorted(bpy.data.objects, key=lambda item: item.name)[:30]
        ],
    }
except Exception as exc:
    data = {
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

with open(os.environ["VALIDATE_GLB_JSON"], "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
'''.lstrip(),
        encoding="utf-8",
    )
    return script


def _validate_glb_import(blender: Path, glb_path: Path, package_dir: Path, timeout: int) -> dict[str, Any]:
    script = _write_glb_validate_script(package_dir)
    validation_json = package_dir / "glb_validation.json"
    stdout_path = package_dir / "glb_validation_stdout.log"
    stderr_path = package_dir / "glb_validation_stderr.log"
    env = os.environ.copy()
    env["VALIDATE_GLB_PATH"] = str(glb_path)
    env["VALIDATE_GLB_JSON"] = str(validation_json)
    cmd = [str(blender), "-b", "--python", str(script)]

    started = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr:
        proc = subprocess.run(
            cmd,
            cwd=str(package_dir),
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
        "json": str(validation_json),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    if validation_json.is_file():
        result["validation"] = _load_json(validation_json)
    else:
        result["validation"] = {"ok": False, "error": "GLB validation did not write JSON"}
    return result


def _collect_static_artifacts(run_dir: Path, stage12_dir: Path, package_dir: Path) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    copied["run_config"] = _copy_file(run_dir / "run_config.json", package_dir / "source" / "run_config.json")
    copied["audit_report_json"] = _copy_file(run_dir / "audit_report.json", package_dir / "reports" / "audit_report.json")
    copied["audit_report_html"] = _copy_file(run_dir / "audit_report.html", package_dir / "reports" / "audit_report.html")
    copied["render_script"] = _copy_file(stage12_dir / "render_output.py", package_dir / "source" / "render_output.py")
    copied["render_lighting"] = _copy_file(stage12_dir / "render_lighting.json", package_dir / "source" / "render_lighting.json")

    preview_src = _latest_existing(
        sorted(stage12_dir.glob("final_render*.png"))
        + [
            run_dir / "audit" / "audit_render.png",
            run_dir / "stage12_render" / "final_render_patched.png",
            run_dir / "stage12_render" / "final_render_test.png",
        ]
    )
    if preview_src:
        copied["source_preview"] = _copy_file(preview_src, package_dir / "source" / "final_render.png")

    for stage in ("stage11_texture_apimart", "stage11_texture"):
        stage_dir = run_dir / stage
        if stage_dir.is_dir():
            copied[f"{stage}_manifest"] = _copy_file(
                stage_dir / "texture_manifest.json",
                package_dir / "source" / stage / "texture_manifest.json",
            )
            copied[f"{stage}_images"] = _copy_dir(
                stage_dir / "images",
                package_dir / "assets" / stage / "images",
            )
    return copied


def _zip_package(package_dir: Path) -> Path:
    zip_path = package_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_dir.parent))
    return zip_path


def optimize(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    stage12_dir = _choose_stage12(run_dir, args.stage12_dir).resolve()
    render_script = stage12_dir / "render_output.py"
    blender = Path(args.blender or os.environ.get("BLENDER", "")).resolve()
    package_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "optimized_scene"

    if not run_dir.is_dir():
        raise FileNotFoundError(f"run_dir does not exist: {run_dir}")
    if not render_script.is_file():
        raise FileNotFoundError(f"render script does not exist: {render_script}")
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable does not exist: {blender}")

    if package_dir.exists() and args.clean:
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    copied = _collect_static_artifacts(run_dir, stage12_dir, package_dir)
    blender_result = _run_blender_export(
        blender,
        render_script,
        package_dir,
        render_preview=args.render_preview,
        export_glb=not args.no_glb,
        pack_textures=args.pack_textures,
        purge_orphans=not args.no_purge_orphans,
        timeout=args.timeout,
    )
    glb_validation = None
    if args.validate_glb and not args.no_glb:
        glb_path = package_dir / "scene.glb"
        glb_validation = _validate_glb_import(blender, glb_path, package_dir, args.timeout)

    scene_export = blender_result.get("scene_export", {})
    scene = scene_export.get("scene", {}) if isinstance(scene_export, dict) else {}
    glb_validation_ok = None
    if glb_validation is not None:
        glb_validation_ok = (
            glb_validation.get("returncode") == 0
            and bool(glb_validation.get("validation", {}).get("ok"))
            and glb_validation.get("validation", {}).get("counts", {}).get("mesh_objects", 0) > 0
        )
    ok = blender_result.get("returncode") == 0 and bool(scene_export.get("ok"))
    if glb_validation_ok is not None:
        ok = ok and glb_validation_ok
    manifest = {
        "created_at": _now(),
        "package_dir": str(package_dir),
        "source_run_dir": str(run_dir),
        "stage12_dir": str(stage12_dir),
        "render_script": str(render_script),
        "blender": str(blender),
        "copied_artifacts": copied,
        "blender_export": blender_result,
        "glb_validation": glb_validation,
        "summary": {
            "ok": ok,
            "objects": scene.get("counts", {}).get("objects", 0),
            "mesh_objects": scene.get("counts", {}).get("mesh_objects", 0),
            "materials": scene.get("counts", {}).get("materials", 0),
            "images": scene.get("counts", {}).get("images", 0),
            "semantic_groups": scene.get("counts", {}).get("mesh_semantic_groups", 0),
            "all_semantic_groups": scene.get("counts", {}).get("all_semantic_groups", 0),
            "mesh_semantic_groups": scene.get("counts", {}).get("mesh_semantic_groups", 0),
            "glb_ok": bool(scene_export.get("glb_ok")) if isinstance(scene_export, dict) else False,
            "glb_import_ok": glb_validation_ok,
        },
    }
    manifest_path = package_dir / "package_manifest.json"
    manifest["package_manifest"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.zip:
        zip_path = _zip_package(package_dir)
        manifest["zip"] = str(zip_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize/package a Code-as-Room generated run.")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory.")
    parser.add_argument("--blender", default=os.environ.get("BLENDER"), help="Path to Blender executable.")
    parser.add_argument("--stage12-dir", help="Stage 12 directory name or absolute path.")
    parser.add_argument("--output-dir", help="Package directory. Default: <run_dir>/optimized_scene.")
    parser.add_argument("--render-preview", action="store_true", help="Render a fresh preview.png inside the package.")
    parser.add_argument("--no-glb", action="store_true", help="Skip GLB export.")
    parser.add_argument("--validate-glb", action="store_true", help="Re-import scene.glb in Blender after export.")
    parser.add_argument("--pack-textures", action="store_true", help="Pack external texture images into scene.blend.")
    parser.add_argument("--no-purge-orphans", action="store_true", help="Skip Blender orphan-data purge before export.")
    parser.add_argument("--zip", action="store_true", help="Create <optimized_scene>.zip after packaging.")
    parser.add_argument("--clean", action="store_true", help="Delete the package directory before rebuilding it.")
    parser.add_argument("--timeout", type=int, default=300, help="Blender export timeout in seconds.")
    args = parser.parse_args()

    manifest = optimize(args)
    summary = manifest["summary"]
    print(
        "Optimize "
        f"{'PASS' if summary['ok'] else 'FAIL'}: "
        f"{summary['objects']} objects, "
        f"{summary['materials']} materials, "
        f"{summary['images']} images, "
        f"{summary['semantic_groups']} semantic groups, "
        f"GLB={'yes' if summary['glb_ok'] else 'no'}, "
        f"GLB import={summary['glb_import_ok']}"
    )
    print(f"Package: {manifest['package_dir']}")
    print(f"Manifest: {manifest['package_manifest']}")
    if manifest.get("zip"):
        print(f"Zip: {manifest['zip']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
