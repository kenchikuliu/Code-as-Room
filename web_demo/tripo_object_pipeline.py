#!/usr/bin/env python3
"""Generate high-fidelity single-object GLBs with Tripo3D.

This is the object-asset stage for the room pipeline: generate better furniture
meshes first, then place and optionally retexture them in the room scene.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


DEFAULT_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
DEFAULT_MODEL_VERSION = "v3.1-20260211"

ASSET_PRESETS: dict[str, dict[str, Any]] = {
    "platform_bed": {
        "category": "object_bedding",
        "target_size_m": [2.05, 2.25, 0.92],
        "prompt": (
            "High-end modern platform bed for an interior design scene, king size, "
            "soft ivory bedding, layered pillows, subtle quilt folds, warm walnut "
            "low frame and headboard, clean topology, realistic scale, single object, "
            "no room, no floor, no wall, no people."
        ),
    },
    "lounge_armchair": {
        "category": "object_upholstery",
        "target_size_m": [0.86, 0.88, 0.82],
        "prompt": (
            "Premium modern lounge armchair, rounded upholstered shell, greige boucle "
            "fabric, dark slim legs, realistic furniture proportions, detailed seams "
            "and cushion softness, single object, no room, no floor, no wall, no people."
        ),
    },
    "nightstand": {
        "category": "object_wood",
        "target_size_m": [0.52, 0.46, 0.55],
        "prompt": (
            "Modern walnut bedside nightstand with two drawers, recessed pulls, rounded "
            "edges, subtle wood grain, premium bedroom furniture, clean single object, "
            "no room, no floor, no wall, no people."
        ),
    },
    "media_console": {
        "category": "object_dark",
        "target_size_m": [1.85, 0.42, 0.48],
        "prompt": (
            "Low modern media console cabinet, dark stained oak, long horizontal body, "
            "slatted front panels, thin base, premium interior furniture, single object, "
            "no room, no floor, no wall, no people."
        ),
    },
    "dresser": {
        "category": "object_wood",
        "target_size_m": [1.35, 0.48, 0.88],
        "prompt": (
            "Premium walnut bedroom dresser with six drawers, soft rounded edges, "
            "minimal pulls, subtle wood veneer grain, realistic single furniture object, "
            "no room, no floor, no wall, no people."
        ),
    },
    "table_lamp": {
        "category": "object_ceramic",
        "target_size_m": [0.28, 0.28, 0.56],
        "prompt": (
            "Elegant modern bedside table lamp, matte warm white ceramic base, soft "
            "fabric drum shade, small brass detail, realistic scale, single object, "
            "no room, no floor, no wall, no people."
        ),
    },
}


class TripoError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", choices=sorted(ASSET_PRESETS), default="lounge_armchair")
    parser.add_argument("--prompt", help="Override the preset prompt.")
    parser.add_argument("--input-image", help="Local path or URL for image_to_model.")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "tripo_assets")
    parser.add_argument("--base-url", default=os.environ.get("TRIPO_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key-env", default="TRIPO_API_KEY")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--geometry-quality", choices=["standard", "detailed"], default="detailed")
    parser.add_argument("--texture-quality", choices=["standard", "detailed"], default="detailed")
    parser.add_argument("--face-limit", type=int, default=60000)
    parser.add_argument("--texture", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pbr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--auto-size", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--poll-interval", type=float, default=8.0)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def task_url(base_url: str, task_id: str | None = None) -> str:
    root = base_url.rstrip("/")
    return f"{root}/task/{task_id}" if task_id else f"{root}/task"


def upload_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/upload"


def request_json(
    method: str,
    url: str,
    *,
    api_key: str,
    timeout: float,
    **kwargs: Any,
) -> dict[str, Any]:
    response = requests.request(method, url, headers=auth_headers(api_key), timeout=timeout, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        raise TripoError(f"Non-JSON response from {url}: HTTP {response.status_code}") from exc
    if response.status_code >= 400:
        message = payload.get("message") or payload.get("error") or payload
        raise TripoError(f"HTTP {response.status_code}: {message}")
    if payload.get("code") not in (None, 0):
        raise TripoError(f"API error {payload.get('code')}: {payload.get('message') or payload}")
    return payload


def normalize_task_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise TripoError(f"Unexpected task payload: {payload}")
    return data


def extract_task_id(payload: dict[str, Any]) -> str:
    data = normalize_task_payload(payload)
    task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if not task_id:
        raise TripoError(f"Task id not found in response: {payload}")
    return str(task_id)


def extract_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    if isinstance(value, dict):
        for key in ("url", "href", "download_url"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.startswith(("http://", "https://")):
                return nested
    return None


def output_urls(result: dict[str, Any]) -> dict[str, str]:
    candidates = {
        "pbr_model": result.get("pbr_model"),
        "model": result.get("model"),
        "base_model": result.get("base_model"),
        "rendered_image": result.get("rendered_image"),
    }
    urls: dict[str, str] = {}
    for key, value in candidates.items():
        url = extract_url(value)
        if url:
            urls[key] = url
    return urls


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def upload_local_file(base_url: str, api_key: str, path: Path, timeout: float) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as file_obj:
        payload = request_json(
            "POST",
            upload_url(base_url),
            api_key=api_key,
            timeout=timeout,
            files={"file": (path.name, file_obj, mime_type)},
        )
    data = normalize_task_payload(payload)
    token = data.get("image_token") or data.get("file_token") or data.get("token")
    if not token:
        raise TripoError(f"Upload token not found in response: {payload}")
    return {"type": path.suffix.lstrip(".").lower() or "png", "file_token": token}


def image_file_descriptor(base_url: str, api_key: str, image: str, timeout: float) -> dict[str, Any]:
    if is_http_url(image):
        ext = Path(urlparse(image).path).suffix.lstrip(".").lower() or "png"
        return {"type": ext, "url": image}
    return upload_local_file(base_url, api_key, Path(image), timeout)


def dry_run_file_descriptor(image: str) -> dict[str, str]:
    ext = Path(urlparse(image).path if is_http_url(image) else image).suffix.lstrip(".").lower() or "png"
    if is_http_url(image):
        return {"type": ext, "url": image}
    return {"type": ext, "file_token": "<uploaded-on-run>"}


def build_generation_payload(args: argparse.Namespace, api_key: str, *, dry_run: bool = False) -> dict[str, Any]:
    preset = ASSET_PRESETS[args.asset]
    base: dict[str, Any] = {
        "model_version": args.model_version,
        "texture": args.texture,
        "pbr": args.pbr,
        "texture_quality": args.texture_quality,
        "geometry_quality": args.geometry_quality,
        "face_limit": args.face_limit,
        "auto_size": args.auto_size,
    }
    if args.input_image:
        base.update(
            {
                "type": "image_to_model",
                "file": dry_run_file_descriptor(args.input_image)
                if dry_run
                else image_file_descriptor(args.base_url, api_key, args.input_image, args.timeout),
            }
        )
    else:
        base.update({"type": "text_to_model", "prompt": args.prompt or preset["prompt"]})
    return base


def download_file(url: str, path: Path, timeout: float) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file_obj.write(chunk)
    return path.stat().st_size


def poll_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    deadline = time.time() + args.timeout
    last_status = None
    while time.time() < deadline:
        payload = request_json("GET", task_url(args.base_url, task_id), api_key=api_key, timeout=args.timeout)
        data = normalize_task_payload(payload)
        status = str(data.get("status") or data.get("state") or "").lower()
        if status != last_status:
            print(f"[tripo] task {task_id}: {status or 'unknown'}", flush=True)
            last_status = status
        if status in {"success", "succeeded", "completed"}:
            return data
        if status in {"failed", "cancelled", "canceled", "error"}:
            raise TripoError(f"Task {task_id} failed: {data}")
        time.sleep(args.poll_interval)
    raise TimeoutError(f"Timed out waiting for Tripo task {task_id}")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key and not args.dry_run:
        raise SystemExit(f"Set {args.api_key_env} before running this script.")

    asset_dir = args.out_dir / args.asset
    asset_dir.mkdir(parents=True, exist_ok=True)
    preset = ASSET_PRESETS[args.asset]
    payload = build_generation_payload(args, api_key or "", dry_run=args.dry_run)
    manifest: dict[str, Any] = {
        "asset": args.asset,
        "category": preset["category"],
        "target_size_m": preset["target_size_m"],
        "base_url": args.base_url,
        "request": {key: value for key, value in payload.items() if key != "file"},
    }
    if args.input_image:
        manifest["request"]["input_image"] = "url" if is_http_url(args.input_image) else str(Path(args.input_image).name)

    if args.dry_run:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    submit_payload = request_json("POST", task_url(args.base_url), api_key=api_key, timeout=args.timeout, json=payload)
    task_id = extract_task_id(submit_payload)
    manifest["task_id"] = task_id
    manifest["submit_keys"] = sorted(normalize_task_payload(submit_payload).keys())
    write_manifest(asset_dir / "manifest.json", manifest)

    result = poll_task(args, api_key, task_id)
    urls = output_urls(result.get("output") if isinstance(result.get("output"), dict) else result)
    if not urls:
        urls = output_urls(result)
    manifest["status"] = result.get("status")
    manifest["result_keys"] = sorted(result.keys())
    manifest["outputs"] = {}

    preferred_model_url = urls.get("pbr_model") or urls.get("model") or urls.get("base_model")
    if preferred_model_url:
        model_path = asset_dir / f"{args.asset}.glb"
        manifest["outputs"]["model"] = {
            "source": "pbr_model" if urls.get("pbr_model") else "model",
            "path": str(model_path),
            "size_bytes": download_file(preferred_model_url, model_path, args.timeout),
        }
    if urls.get("rendered_image"):
        preview_path = asset_dir / f"{args.asset}_preview.png"
        manifest["outputs"]["preview"] = {
            "path": str(preview_path),
            "size_bytes": download_file(urls["rendered_image"], preview_path, args.timeout),
        }

    write_manifest(asset_dir / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[tripo] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
