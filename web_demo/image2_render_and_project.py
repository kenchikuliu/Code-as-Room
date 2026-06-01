from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent
RUN_DIR = ROOT / "repro_outputs" / "gpt55_stage1_4" / "run_20260530_141733_example1"
DEFAULT_MODEL = RUN_DIR / "optimized_scene" / "scene.glb"
DEFAULT_REFERENCE = RUN_DIR / "stage12_render_apimart" / "final_render_apimart_textures.png"
DEFAULT_OUT_DIR = WEB_DIR / "image2_outputs"
DEFAULT_MAPPED_DIR = WEB_DIR / "image2_mapped_models"


IMAGE2_PROMPT = """Create a polished photorealistic interior renovation render from this top-down room render.
Preserve the exact floor plan, wall positions, bed, wardrobe, cabinets, armchairs, rugs, lighting positions, and camera angle.
Improve the visual design only: warm natural wood floor, soft plaster walls, premium upholstered bedding, coherent rugs, walnut cabinetry, realistic fabric, subtle daylight, soft shadows.
Do not add rooms, do not remove furniture, do not move objects, do not add labels or text, and keep the same top-down/isometric architectural view."""

WALL_PROMPTS = {
    "wall_main": "Seamless warm off-white limewash plaster interior wall material, subtle mineral grain, premium renovated bedroom, no furniture, no text, square texture, physically plausible.",
    "wall_accent": "Seamless walnut vertical wood slat feature wall material for a modern bedroom headboard wall, warm brown wood, narrow rhythmic grooves, no furniture, no text, square texture.",
    "wall_panel": "Seamless soft taupe upholstered acoustic wall panel material, fine woven fabric, subtle seams, premium interior finish, no furniture, no text, square texture.",
}

OBJECT_PROMPTS = {
    "object_wood": "Seamless premium walnut furniture wood veneer material, subtle linear grain, modern bedroom cabinetry, no object, no text, square PBR color texture.",
    "object_bedding": "Seamless warm ivory cotton bedding fabric material, soft woven threads, subtle quilted variation, no object, no text, square PBR color texture.",
    "object_upholstery": "Seamless greige boucle upholstery fabric material, fine woven texture, premium lounge chair textile, no object, no text, square PBR color texture.",
    "object_stone": "Seamless warm limestone and travertine counter surface material, subtle veins, premium interior stone, no object, no text, square PBR color texture.",
    "object_ceramic": "Seamless matte warm white ceramic decor material, subtle speckled glaze, no object, no text, square PBR color texture.",
    "object_dark": "Seamless dark stained oak furniture material, low sheen, fine wood grain, no object, no text, square PBR color texture.",
}


def normalize_base_url(base_url: str | None) -> str:
    root = (base_url or "https://api.apimart.ai/v1").rstrip("/")
    if root.endswith("/v1"):
        return root
    return f"{root}/v1"


def api_key_from_env(names: list[str]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def upload_reference_image(root: str, api_key: str, path: Path, timeout: int) -> str:
    import requests

    with path.open("rb") as handle:
        response = requests.post(
            f"{root}/uploads/images",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (path.name, handle, "image/png")},
            timeout=timeout,
        )
    if not response.ok:
        raise RuntimeError(f"Image upload HTTP {response.status_code}: {response.text[:1200]}")
    payload = response.json()
    url = payload.get("url") or payload.get("data", {}).get("url")
    if not url:
        raise ValueError(f"Upload response did not include a URL: {response.text[:1200]}")
    return str(url)


def extract_task_id(payload: dict[str, Any]) -> str | None:
    for key in ("id", "task_id"):
        if payload.get(key):
            return str(payload[key])
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("id", "task_id"):
            if data.get(key):
                return str(data[key])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            for key in ("id", "task_id"):
                if first.get(key):
                    return str(first[key])
    return None


def extract_status(payload: dict[str, Any]) -> str:
    for obj in (payload, payload.get("data")):
        if isinstance(obj, dict) and obj.get("status"):
            return str(obj["status"]).lower()
    return ""


def extract_image_url(payload: dict[str, Any]) -> str | None:
    def from_obj(obj: Any) -> str | None:
        if isinstance(obj, str) and obj.startswith(("http://", "https://")):
            return obj
        if not isinstance(obj, dict):
            return None
        for key in ("url", "image_url", "output_url"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, list) and value:
                nested = from_obj(value[0])
                if nested:
                    return nested
        for key in ("images", "output", "result"):
            value = obj.get(key)
            if isinstance(value, list) and value:
                nested = from_obj(value[0])
                if nested:
                    return nested
            if isinstance(value, dict):
                nested = from_obj(value)
                if nested:
                    return nested
        return None

    direct = from_obj(payload)
    if direct:
        return direct
    data = payload.get("data")
    if isinstance(data, list) and data:
        return from_obj(data[0])
    return from_obj(data)


def create_image2_task(
    root: str,
    api_key: str,
    model: str,
    image_url: str | None,
    prompt: str,
    size: str,
    resolution: str,
    timeout: int,
) -> tuple[str, dict[str, Any]]:
    import requests

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base_payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "resolution": resolution,
    }

    if not image_url:
        response = requests.post(
            f"{root}/images/generations",
            headers=headers,
            json=base_payload,
            timeout=timeout,
        )
        if response.ok:
            data = response.json()
            task_id = extract_task_id(data)
            if task_id:
                return task_id, data
            raise ValueError(f"Generation response did not include a task id: {response.text[:1200]}")
        raise RuntimeError(f"Image2 generation request failed: HTTP {response.status_code}: {response.text[:1200]}")

    last_error = ""
    for image_urls in ([{"url": image_url}], [image_url]):
        payload = dict(base_payload)
        payload["image_urls"] = image_urls
        response = requests.post(
            f"{root}/images/generations",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        if response.ok:
            data = response.json()
            task_id = extract_task_id(data)
            if task_id:
                return task_id, data
            raise ValueError(f"Generation response did not include a task id: {response.text[:1200]}")
        last_error = f"HTTP {response.status_code}: {response.text[:1200]}"
    raise RuntimeError(f"Image2 generation request failed: {last_error}")


def poll_image2_task(root: str, api_key: str, task_id: str, timeout: int) -> tuple[str, dict[str, Any]]:
    import requests

    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + max(60, timeout)
    last_payload: dict[str, Any] = {}
    endpoints = (f"{root}/tasks/{task_id}", f"{root}/images/generations/{task_id}")

    while time.time() < deadline:
        for endpoint in endpoints:
            response = requests.get(endpoint, headers=headers, timeout=min(60, timeout))
            if response.status_code == 404:
                continue
            if not response.ok:
                raise RuntimeError(f"Task poll HTTP {response.status_code}: {response.text[:1200]}")
            payload = response.json()
            last_payload = payload
            status = extract_status(payload)
            if status in {"completed", "succeeded", "success", "done"}:
                image_url = extract_image_url(payload)
                if not image_url:
                    raise ValueError(f"Completed task did not include an image URL: {json.dumps(payload)[:1200]}")
                return image_url, payload
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise RuntimeError(f"Image2 task failed: {json.dumps(payload)[:1200]}")
        time.sleep(4.0)
    raise TimeoutError(f"Timed out waiting for image2 task {task_id}: {json.dumps(last_payload)[:1200]}")


def download_image(url: str, output: Path, timeout: int) -> None:
    import requests

    response = requests.get(url, timeout=timeout)
    if not response.ok:
        raise RuntimeError(f"Image download HTTP {response.status_code}: {response.text[:500]}")
    output.write_bytes(response.content)


def generate_image2_render(args: argparse.Namespace, reference_path: Path, output_path: Path) -> dict[str, Any]:
    key = api_key_from_env(args.api_key_env)
    root = normalize_base_url(args.base_url or os.environ.get("APIMART_BASE_URL") or os.environ.get("SCENEGEN_TEXTURE_BASE_URL"))
    manifest: dict[str, Any] = {
        "source_reference": str(reference_path),
        "output": str(output_path),
        "model": args.image_model,
        "base_url": root,
        "used_api": False,
    }

    if not key:
        if args.require_api:
            raise RuntimeError(
                "APIMart key missing. Set APIMART_API_KEY or SCENEGEN_TEXTURE_API_KEY before running with --require-api."
            )
        if output_path.is_file():
            manifest["mode"] = "reuse_existing_render_no_api_key"
            manifest["reused_existing"] = True
            return manifest
        Image.open(reference_path).save(output_path)
        manifest["mode"] = "fallback_existing_render_no_api_key"
        return manifest

    uploaded_url = upload_reference_image(root, key, reference_path, args.timeout)
    task_id, submit_payload = create_image2_task(
        root=root,
        api_key=key,
        model=args.image_model,
        image_url=uploaded_url,
        prompt=args.prompt,
        size=args.size,
        resolution=args.resolution,
        timeout=args.timeout,
    )
    result_url, task_payload = poll_image2_task(root, key, task_id, args.timeout)
    download_image(result_url, output_path, args.timeout)
    manifest.update(
        {
            "used_api": True,
            "mode": "image2_reference_generation",
            "uploaded_reference_url": uploaded_url,
            "task_id": task_id,
            "submit_keys": sorted(submit_payload.keys()),
            "task_keys": sorted(task_payload.keys()),
            "result_url": result_url,
        }
    )
    return manifest


def room_crop_box(image: Image.Image) -> tuple[int, int, int, int]:
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3] > 8
    bright = arr[:, :, :3].max(axis=2) > 24
    mask = alpha & bright
    if not mask.any():
        return (0, 0, image.width, image.height)

    row_counts = mask.sum(axis=1)
    col_counts = mask.sum(axis=0)
    row_threshold = max(8, int(image.width * 0.08))
    col_threshold = max(8, int(image.height * 0.08))
    rows = np.where(row_counts > row_threshold)[0]
    cols = np.where(col_counts > col_threshold)[0]
    if len(rows) == 0 or len(cols) == 0:
        ys, xs = np.where(mask)
        rows = ys
        cols = xs

    left = int(cols.min())
    right = int(cols.max() + 1)
    top = int(rows.min())
    bottom = int(rows.max() + 1)
    pad_x = int((right - left) * 0.015)
    pad_y = int((bottom - top) * 0.015)
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )


def fit_box_to_aspect(box: tuple[int, int, int, int], image_size: tuple[int, int], aspect: float) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return (0, 0, image_size[0], image_size[1])
    current = width / height
    if abs(current - aspect) < 0.03:
        return box
    cx = (left + right) / 2.0
    cy = (top + bottom) / 2.0
    if current < aspect:
        width = int(round(height * aspect))
    else:
        height = int(round(width / aspect))
    left = int(round(cx - width / 2))
    right = left + width
    top = int(round(cy - height / 2))
    bottom = top + height
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > image_size[0]:
        left -= right - image_size[0]
        right = image_size[0]
    if bottom > image_size[1]:
        top -= bottom - image_size[1]
        bottom = image_size[1]
    return (max(0, left), max(0, top), min(image_size[0], right), min(image_size[1], bottom))


def prepare_projection_texture(render_path: Path, output_path: Path, room_aspect: float, texture_width: int) -> dict[str, Any]:
    image = Image.open(render_path).convert("RGB")
    crop = fit_box_to_aspect(room_crop_box(image), image.size, room_aspect)
    cropped = image.crop(crop)
    texture_height = max(64, int(round(texture_width / room_aspect)))
    texture = cropped.resize((texture_width, texture_height), Image.Resampling.LANCZOS)
    texture = texture.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    texture.save(output_path)
    return {"source": str(render_path), "output": str(output_path), "crop_box": crop, "size": texture.size}


def solid_texture(color: tuple[int, int, int], size: int = 48) -> Image.Image:
    return Image.new("RGB", (size, size), color)


def plaster_texture(seed: int, size: int = 512, base: tuple[int, int, int] = (229, 226, 218)) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    base_arr = np.array(base, dtype=np.int16)
    yy, xx = np.mgrid[0:size, 0:size]
    waves = 4 * np.sin(xx / 21.0) + 3 * np.cos((xx + yy) / 37.0)
    noise = rng.normal(0, 7, (size, size, 1))
    values = np.clip(base_arr + waves[:, :, None] + noise, 0, 255).astype(np.uint8)
    arr[:, :, :] = values
    image = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=0.35))
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(90):
        x0 = int(rng.integers(0, size))
        y0 = int(rng.integers(0, size))
        x1 = x0 + int(rng.integers(-90, 90))
        y1 = y0 + int(rng.integers(-30, 30))
        color = (255, 255, 255, int(rng.integers(5, 18))) if rng.random() < 0.5 else (120, 114, 104, int(rng.integers(4, 12)))
        draw.line([x0, y0, x1, y1], fill=color, width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.25))


def wood_slat_texture(seed: int, size: int = 512) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = Image.new("RGB", (size, size), (82, 52, 34))
    draw = ImageDraw.Draw(image)
    slat_w = max(22, size // 14)
    for x in range(0, size, slat_w):
        x1 = min(size - 1, x + slat_w - 3)
        groove0 = min(size - 1, x + slat_w - 3)
        groove1 = min(size - 1, x + slat_w)
        shade = int(rng.integers(-10, 11))
        base = (
            max(0, min(255, 92 + shade)),
            max(0, min(255, 59 + shade // 2)),
            max(0, min(255, 37 + shade // 3)),
        )
        draw.rectangle([x, 0, x1, size - 1], fill=base)
        if groove1 >= groove0:
            draw.rectangle([groove0, 0, groove1, size - 1], fill=(30, 22, 17))
        for y in range(0, size, 9):
            grain_shade = int(rng.integers(-8, 9))
            color = tuple(max(0, min(255, c + grain_shade)) for c in base)
            wobble = int(2 * np.sin((y + x) / 23.0))
            line_x0 = max(0, min(size - 1, x + 2 + wobble))
            line_x1 = max(line_x0, min(size - 1, x + slat_w - 5 + wobble))
            draw.line([line_x0, y, line_x1, min(size - 1, y + 2)], fill=color, width=1)
        for offset in (4, slat_w // 2):
            gx = max(0, min(size - 1, x + offset))
            draw.line([gx, 0, gx, size - 1], fill=(116, 78, 52), width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.22))


def upholstered_panel_texture(seed: int, size: int = 512) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = plaster_texture(seed, size, base=(184, 174, 160)).filter(ImageFilter.GaussianBlur(radius=0.5))
    draw = ImageDraw.Draw(image, "RGBA")
    panel_w = size // 4
    panel_h = size // 3
    for x in range(0, size, panel_w):
        draw.line([x, 0, x, size], fill=(100, 88, 76, 55), width=2)
        draw.line([x + 2, 0, x + 2, size], fill=(240, 234, 224, 28), width=1)
    for y in range(0, size, panel_h):
        draw.line([0, y, size, y], fill=(100, 88, 76, 45), width=2)
        draw.line([0, y + 2, size, y + 2], fill=(240, 234, 224, 24), width=1)
    for i in range(0, size, 7):
        color = (120, 112, 102, int(rng.integers(10, 23)))
        draw.line([0, i, size, i], fill=color, width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.2))


def wood_veneer_texture(seed: int, size: int = 384, dark: bool = False) -> Image.Image:
    rng = np.random.default_rng(seed)
    base = np.array((92, 58, 36) if dark else (126, 82, 49), dtype=np.float32)
    yy, xx = np.mgrid[0:size, 0:size]
    wave = 13 * np.sin((xx + 5 * np.sin(yy / 31.0)) / 18.0) + 5 * np.sin(xx / 5.5)
    noise = rng.normal(0, 8, (size, size, 1))
    arr = np.clip(base + wave[:, :, None] + noise, 0, 255).astype(np.uint8)
    image = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=0.25))
    draw = ImageDraw.Draw(image, "RGBA")
    plank_w = size // 6
    for x in range(0, size, plank_w):
        draw.line([x, 0, x, size], fill=(42, 28, 20, 52), width=2)
        draw.line([x + 2, 0, x + 2, size], fill=(190, 139, 93, 22), width=1)
    for _ in range(30):
        y = int(rng.integers(0, size))
        color = (45, 30, 21, int(rng.integers(18, 42)))
        draw.line([0, y, size, y + int(rng.integers(-4, 5))], fill=color, width=1)
    return image


def woven_fabric_texture(seed: int, size: int = 384, base: tuple[int, int, int] = (214, 207, 193)) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    base_arr = np.array(base, dtype=np.int16)
    yy, xx = np.mgrid[0:size, 0:size]
    weave = ((xx % 8) < 3).astype(np.int16) * 8 + ((yy % 7) < 3).astype(np.int16) * -7
    noise = rng.normal(0, 5, (size, size, 1))
    arr[:, :, :] = np.clip(base_arr + weave[:, :, None] + noise, 0, 255).astype(np.uint8)
    image = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=0.18))
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(0, size, 12):
        draw.line([0, i, size, i], fill=(95, 88, 78, 18), width=1)
        draw.line([i, 0, i, size], fill=(255, 250, 240, 14), width=1)
    return image


def stone_surface_texture(seed: int, size: int = 384) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = plaster_texture(seed, size, base=(192, 180, 160)).filter(ImageFilter.GaussianBlur(radius=0.35))
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(24):
        x0 = int(rng.integers(0, size))
        y0 = int(rng.integers(0, size))
        points = []
        for step in range(0, 120, 12):
            points.append((x0 + step, y0 + int(13 * np.sin((step + x0) / 22.0))))
        draw.line(points, fill=(104, 94, 82, int(rng.integers(18, 38))), width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.18))


def ceramic_speckle_texture(seed: int, size: int = 256) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = plaster_texture(seed, size, base=(221, 216, 204)).filter(ImageFilter.GaussianBlur(radius=0.2))
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(900):
        x = int(rng.integers(0, size))
        y = int(rng.integers(0, size))
        tone = int(rng.integers(110, 170))
        draw.point((x, y), fill=(tone, tone - 4, tone - 12, int(rng.integers(16, 48))))
    return image.filter(ImageFilter.GaussianBlur(radius=0.12))


def fallback_wall_texture(name: str) -> Image.Image:
    if name == "wall_accent":
        return wood_slat_texture(34)
    if name == "wall_panel":
        return upholstered_panel_texture(35)
    return plaster_texture(33)


def fallback_object_texture(name: str) -> Image.Image:
    if name == "object_wood":
        return wood_veneer_texture(44)
    if name == "object_dark":
        return wood_veneer_texture(45, dark=True)
    if name == "object_bedding":
        return woven_fabric_texture(46, base=(224, 220, 211))
    if name == "object_upholstery":
        return woven_fabric_texture(47, base=(181, 171, 157))
    if name == "object_stone":
        return stone_surface_texture(48)
    if name == "object_ceramic":
        return ceramic_speckle_texture(49)
    return woven_fabric_texture(50)


def generate_named_textures(
    args: argparse.Namespace,
    output_dir: Path,
    prompts: dict[str, str],
    fallback_fn,
    *,
    subdir: str,
) -> dict[str, Any]:
    texture_dir = output_dir / subdir
    texture_dir.mkdir(parents=True, exist_ok=True)
    key = api_key_from_env(args.api_key_env)
    manifest: dict[str, Any] = {"textures": {}, "used_api": False}

    for name, prompt in prompts.items():
        path = texture_dir / f"{name}.png"
        info: dict[str, Any]
        if key:
            try:
                info = generate_text_image2(args, prompt, path)
                manifest["used_api"] = bool(manifest["used_api"] or info.get("used_api"))
            except Exception as exc:
                image = fallback_fn(name)
                image.save(path)
                info = {
                    "output": str(path),
                    "used_api": False,
                    "mode": f"fallback_{subdir}_texture_after_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        else:
            image = fallback_fn(name)
            image.save(path)
            info = {"output": str(path), "used_api": False, "mode": f"fallback_{subdir}_texture"}
        info["prompt"] = prompt
        manifest["textures"][name] = info
    return manifest


def generate_text_image2(
    args: argparse.Namespace,
    prompt: str,
    output_path: Path,
) -> dict[str, Any]:
    key = api_key_from_env(args.api_key_env)
    root = normalize_base_url(args.base_url or os.environ.get("APIMART_BASE_URL") or os.environ.get("SCENEGEN_TEXTURE_BASE_URL"))
    manifest: dict[str, Any] = {
        "output": str(output_path),
        "model": args.image_model,
        "base_url": root,
        "used_api": False,
    }
    if not key:
        return manifest
    task_id, submit_payload = create_image2_task(
        root=root,
        api_key=key,
        model=args.image_model,
        image_url=None,
        prompt=prompt,
        size="1:1",
        resolution=args.resolution,
        timeout=args.timeout,
    )
    result_url, task_payload = poll_image2_task(root, key, task_id, args.timeout)
    download_image(result_url, output_path, args.timeout)
    manifest.update(
        {
            "used_api": True,
            "mode": "image2_text_generation",
            "task_id": task_id,
            "submit_keys": sorted(submit_payload.keys()),
            "task_keys": sorted(task_payload.keys()),
            "result_url": result_url,
        }
    )
    return manifest


def generate_wall_textures(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    return generate_named_textures(args, output_dir, WALL_PROMPTS, fallback_wall_texture, subdir="wall_textures")


def generate_object_textures(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    return generate_named_textures(args, output_dir, OBJECT_PROMPTS, fallback_object_texture, subdir="object_textures")


def load_texture(path: Path | None, fallback: Image.Image) -> Image.Image:
    if path and path.is_file():
        return Image.open(path).convert("RGB")
    return fallback.convert("RGB")


def make_materials(projected_texture: Path, wall_textures: dict[str, Path] | None = None) -> dict[str, PBRMaterial]:
    projection = Image.open(projected_texture).convert("RGB")
    wall_textures = wall_textures or {}
    return {
        "room_projection": PBRMaterial(
            name="image2_projected_atlas",
            baseColorTexture=projection,
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.72,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "wall_main": PBRMaterial(
            name="limewash_plaster_wall",
            baseColorTexture=load_texture(wall_textures.get("wall_main"), fallback_wall_texture("wall_main")),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.9,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "wall_accent": PBRMaterial(
            name="bedroom_feature_wall",
            baseColorTexture=load_texture(wall_textures.get("wall_accent"), fallback_wall_texture("wall_accent")),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.72,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "wall_panel": PBRMaterial(
            name="upholstered_wall_panel",
            baseColorTexture=load_texture(wall_textures.get("wall_panel"), fallback_wall_texture("wall_panel")),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.86,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "metal": PBRMaterial(
            name="brushed_metal_clean",
            baseColorTexture=solid_texture((184, 181, 172)),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.38,
            metallicFactor=0.58,
            doubleSided=True,
        ),
        "glass": PBRMaterial(
            name="soft_glass",
            baseColorTexture=Image.new("RGBA", (32, 32), (174, 211, 226, 92)),
            baseColorFactor=[255, 255, 255, 180],
            roughnessFactor=0.12,
            metallicFactor=0.0,
            alphaMode="BLEND",
            doubleSided=True,
        ),
        "foliage": PBRMaterial(
            name="plant_green",
            baseColorTexture=solid_texture((70, 132, 78)),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.78,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "soil": PBRMaterial(
            name="plant_soil",
            baseColorTexture=solid_texture((78, 58, 43)),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.9,
            metallicFactor=0.0,
            doubleSided=True,
        ),
        "soft_fabric": PBRMaterial(
            name="soft_fabric_clean",
            baseColorTexture=solid_texture((224, 226, 224)),
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.88,
            metallicFactor=0.0,
            doubleSided=True,
        ),
    }


def classify_material(node_name: str, geom_name: str, world_bounds: np.ndarray | None = None) -> str:
    name = f"{node_name} {geom_name}".lower()
    if "wall" in name or "partition" in name:
        if "panel" in name or "vent" in name:
            return "wall_panel"
        if "wall_north" in name and world_bounds is not None:
            center_x = float((world_bounds[0, 0] + world_bounds[1, 0]) * 0.5)
            width_x = float(world_bounds[1, 0] - world_bounds[0, 0])
            if abs(center_x) < 2.2 and width_x < 5.5:
                return "wall_accent"
        return "wall_main"
    if "glass" in name or "mirror" in name or "window" in name:
        return "glass"
    if "soil" in name:
        return "soil"
    if any(token in name for token in ("pot_rim", "pot_base", "vase", "ceramic", "decor_box", "decor_sphere")):
        return "object_ceramic"
    if "plant" in name or "foliage" in name or "leaf" in name:
        return "foliage"
    if any(token in name for token in ("metal", "handle", "knob", "rail", "pole", "stem", "spike", "cap")):
        return "metal"
    if any(token in name for token in ("floor", "rug", "carpet", "runner")):
        return "room_projection"
    if any(token in name for token in ("pillow", "sheet", "duvet", "blanket", "mattress", "bedding")):
        return "object_bedding"
    if any(token in name for token in ("sofa", "armchair", "seat", "cushion", "bench", "chair", "ottoman")):
        return "object_upholstery"
    if any(token in name for token in ("counter", "stone", "vanity", "plinth", "kitchen", "surface")):
        return "object_stone"
    if any(token in name for token in ("black", "media", "screen", "tv", "closet", "wardrobe")):
        return "object_dark"
    if any(
        token in name
        for token in (
            "bed",
            "cabinet",
            "shelf",
            "drawer",
            "nightstand",
            "console",
            "table",
            "desk",
            "headboard",
            "frame",
        )
    ):
        return "object_wood"
    if world_bounds is not None:
        ext = world_bounds[1] - world_bounds[0]
        footprint = float(max(ext[0], 0.0) * max(ext[2], 0.0))
        if footprint > 0.03:
            return "object_ceramic"
    return "soft_fabric"


def projected_uv(vertices: np.ndarray, transform: np.ndarray, bounds: np.ndarray, *, flip_v: bool) -> np.ndarray:
    ones = np.ones((len(vertices), 1), dtype=np.float64)
    local_h = np.concatenate([vertices.astype(np.float64), ones], axis=1)
    world = (transform @ local_h.T).T[:, :3]
    span = np.maximum(bounds[1] - bounds[0], 1e-6)
    u = (world[:, 0] - bounds[0, 0]) / span[0]
    z_norm = (world[:, 2] - bounds[0, 2]) / span[2]
    v = 1.0 - z_norm if flip_v else z_norm
    return np.column_stack([u, v]).astype(np.float32)


def world_vertices(vertices: np.ndarray, transform: np.ndarray) -> np.ndarray:
    if len(vertices) == 0:
        return np.zeros((0, 3), dtype=np.float64)
    ones = np.ones((len(vertices), 1), dtype=np.float64)
    local_h = np.concatenate([vertices.astype(np.float64), ones], axis=1)
    return (transform @ local_h.T).T[:, :3]


def projected_uv_from_world(world: np.ndarray, bounds: np.ndarray, *, flip_v: bool) -> np.ndarray:
    if len(world) == 0:
        return np.zeros((0, 2), dtype=np.float32)
    span = np.maximum(bounds[1] - bounds[0], 1e-6)
    u = (world[:, 0] - bounds[0, 0]) / span[0]
    z_norm = (world[:, 2] - bounds[0, 2]) / span[2]
    v = 1.0 - z_norm if flip_v else z_norm
    return np.column_stack([u, v]).astype(np.float32)


def wall_uv_from_world(world: np.ndarray, wbounds: np.ndarray, category: str) -> np.ndarray:
    if len(world) == 0:
        return np.zeros((0, 2), dtype=np.float32)
    ext = np.maximum(wbounds[1] - wbounds[0], 1e-6)
    horizontal_axis = 0 if ext[0] >= ext[2] else 2
    horizontal_repeat = 1.35 if category == "wall_accent" else 1.8
    vertical_repeat = 1.0 if category == "wall_panel" else 1.4
    u = (world[:, horizontal_axis] - wbounds[0, horizontal_axis]) / max(horizontal_repeat, 1e-6)
    v = (world[:, 1] - wbounds[0, 1]) / max(vertical_repeat, 1e-6)
    return np.column_stack([u, v]).astype(np.float32)


def crop_material_from_projection(
    projection_image: Image.Image,
    uv: np.ndarray,
    material_name: str,
    *,
    max_size: int = 256,
) -> tuple[PBRMaterial, np.ndarray, tuple[int, int, int, int]]:
    if len(uv) == 0:
        image = solid_texture((190, 185, 174))
        material = PBRMaterial(
            name=material_name,
            baseColorTexture=image,
            baseColorFactor=[255, 255, 255, 255],
            roughnessFactor=0.78,
            metallicFactor=0.0,
            doubleSided=True,
        )
        return material, uv, (0, 0, image.width, image.height)

    uv_clamped = np.clip(uv, 0.0, 1.0)
    min_uv = uv_clamped.min(axis=0)
    max_uv = uv_clamped.max(axis=0)
    span_uv = np.maximum(max_uv - min_uv, 0.012)
    center = (min_uv + max_uv) * 0.5
    min_uv = center - span_uv * 0.58
    max_uv = center + span_uv * 0.58
    min_uv = np.clip(min_uv, 0.0, 1.0)
    max_uv = np.clip(max_uv, 0.0, 1.0)
    if max_uv[0] <= min_uv[0]:
        max_uv[0] = min(1.0, min_uv[0] + 0.02)
    if max_uv[1] <= min_uv[1]:
        max_uv[1] = min(1.0, min_uv[1] + 0.02)

    width, height = projection_image.size
    left = int(np.floor(min_uv[0] * (width - 1)))
    right = int(np.ceil(max_uv[0] * (width - 1))) + 1
    top = int(np.floor(min_uv[1] * (height - 1)))
    bottom = int(np.ceil(max_uv[1] * (height - 1))) + 1
    left = max(0, min(width - 1, left))
    right = max(left + 2, min(width, right))
    top = max(0, min(height - 1, top))
    bottom = max(top + 2, min(height, bottom))

    crop = projection_image.crop((left, top, right, bottom)).convert("RGB")
    crop.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if crop.width < 8 or crop.height < 8:
        crop = crop.resize((max(8, crop.width), max(8, crop.height)), Image.Resampling.BICUBIC)

    local_uv = (uv_clamped - min_uv) / np.maximum(max_uv - min_uv, 1e-6)
    local_uv = np.clip(local_uv, 0.0, 1.0).astype(np.float32)
    material = PBRMaterial(
        name=material_name,
        baseColorTexture=crop,
        baseColorFactor=[255, 255, 255, 255],
        roughnessFactor=0.76,
        metallicFactor=0.0,
        doubleSided=True,
    )
    return material, local_uv, (left, top, right, bottom)


def projection_crop_box_from_uv(
    projection_image: Image.Image,
    uv: np.ndarray,
    *,
    pad_scale: float = 0.58,
) -> tuple[int, int, int, int]:
    if len(uv) == 0:
        return (0, 0, projection_image.width, projection_image.height)
    uv_clamped = np.clip(uv, 0.0, 1.0)
    min_uv = uv_clamped.min(axis=0)
    max_uv = uv_clamped.max(axis=0)
    span_uv = np.maximum(max_uv - min_uv, 0.012)
    center = (min_uv + max_uv) * 0.5
    min_uv = np.clip(center - span_uv * pad_scale, 0.0, 1.0)
    max_uv = np.clip(center + span_uv * pad_scale, 0.0, 1.0)

    width, height = projection_image.size
    left = int(np.floor(min_uv[0] * (width - 1)))
    right = int(np.ceil(max_uv[0] * (width - 1))) + 1
    top = int(np.floor(min_uv[1] * (height - 1)))
    bottom = int(np.ceil(max_uv[1] * (height - 1))) + 1
    left = max(0, min(width - 1, left))
    right = max(left + 2, min(width, right))
    top = max(0, min(height - 1, top))
    bottom = max(top + 2, min(height, bottom))
    return (left, top, right, bottom)


def projection_tint_from_uv(
    projection_image: Image.Image,
    uv: np.ndarray,
    fallback: tuple[int, int, int],
) -> tuple[tuple[int, int, int], tuple[int, int, int, int]]:
    box = projection_crop_box_from_uv(projection_image, uv)
    crop = projection_image.crop(box).convert("RGB")
    arr = np.asarray(crop, dtype=np.uint8)
    brightness = arr.mean(axis=2)
    mask = (brightness > 28) & (brightness < 245)
    if not mask.any():
        return fallback, box
    color = np.median(arr[mask], axis=0)
    color = np.clip(color, 38, 235).astype(np.uint8)
    return (int(color[0]), int(color[1]), int(color[2])), box


def tint_texture(base: Image.Image, tint: tuple[int, int, int], strength: float) -> Image.Image:
    image = base.convert("RGB").resize((192, 192), Image.Resampling.LANCZOS)
    arr = np.asarray(image, dtype=np.float32)
    mean = np.maximum(arr.mean(axis=(0, 1), keepdims=True), 1.0)
    target = np.array(tint, dtype=np.float32).reshape((1, 1, 3))
    shifted = arr * (target / mean)
    out = arr * (1.0 - strength) + shifted * strength
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def semantic_object_uv(mesh: trimesh.Trimesh, category: str) -> np.ndarray:
    uv = full_uv(mesh)
    tile = {
        "object_wood": 1.8,
        "object_dark": 1.6,
        "object_bedding": 1.25,
        "object_upholstery": 1.45,
        "object_stone": 1.2,
        "object_ceramic": 1.0,
    }.get(category, 1.0)
    return (uv * tile).astype(np.float32)


def semantic_object_material(
    mesh: trimesh.Trimesh,
    category: str,
    object_textures: dict[str, Path],
    projection_image: Image.Image,
    atlas_uv: np.ndarray,
    material_name: str,
) -> tuple[PBRMaterial, np.ndarray, tuple[int, int, int], tuple[int, int, int, int]]:
    fallback_color = {
        "object_wood": (126, 82, 49),
        "object_dark": (70, 48, 35),
        "object_bedding": (224, 220, 211),
        "object_upholstery": (181, 171, 157),
        "object_stone": (192, 180, 160),
        "object_ceramic": (221, 216, 204),
    }.get(category, (190, 185, 174))
    tint, crop_box = projection_tint_from_uv(projection_image, atlas_uv, fallback_color)
    base = load_texture(object_textures.get(category), fallback_object_texture(category))
    strength = {
        "object_wood": 0.28,
        "object_dark": 0.22,
        "object_bedding": 0.42,
        "object_upholstery": 0.38,
        "object_stone": 0.24,
        "object_ceramic": 0.30,
    }.get(category, 0.3)
    image = tint_texture(base, tint, strength)
    uv = semantic_object_uv(mesh, category)
    material = PBRMaterial(
        name=material_name,
        baseColorTexture=image,
        baseColorFactor=[255, 255, 255, 255],
        roughnessFactor={
            "object_stone": 0.48,
            "object_ceramic": 0.62,
            "object_wood": 0.58,
            "object_dark": 0.55,
        }.get(category, 0.84),
        metallicFactor=0.0,
        doubleSided=True,
    )
    return material, uv, tint, crop_box


def full_uv(mesh: trimesh.Trimesh) -> np.ndarray:
    vertices = np.asarray(mesh.vertices)
    if len(vertices) == 0:
        return np.zeros((0, 2), dtype=np.float32)
    extents = np.ptp(vertices, axis=0)
    axes = np.argsort(extents)[-2:]
    values = vertices[:, axes]
    mins = values.min(axis=0)
    span = np.maximum(values.max(axis=0) - mins, 1e-6)
    return ((values - mins) / span).astype(np.float32)


def add_bed_feature_wall_panel(scene: trimesh.Scene, materials: dict[str, PBRMaterial]) -> dict[str, Any]:
    """Add a separate feature-wall plane instead of texturing the whole north wall."""
    x0, x1 = -1.85, 1.85
    y0, y1 = 0.22, 2.55
    z = -2.735
    vertices = np.array(
        [
            [x0, y0, z],
            [x1, y0, z],
            [x1, y1, z],
            [x0, y1, z],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    wbounds = np.array([vertices.min(axis=0), vertices.max(axis=0)], dtype=np.float64)
    uv = wall_uv_from_world(vertices, wbounds, "wall_accent")
    mesh.visual = TextureVisuals(uv=uv, material=materials["wall_accent"])
    scene.add_geometry(mesh, geom_name="Image2_Bed_Feature_Wall_Panel", node_name="Image2_Bed_Feature_Wall_Panel")
    return {
        "name": "Image2_Bed_Feature_Wall_Panel",
        "bounds": wbounds.tolist(),
        "material": "wall_accent",
    }


def project_render_to_glb(
    model_path: Path,
    projected_texture: Path,
    wall_textures: dict[str, Path],
    object_textures: dict[str, Path],
    output_path: Path,
    *,
    flip_v: bool,
) -> dict[str, Any]:
    scene = trimesh.load(model_path, force="scene")
    bounds = scene.bounds.astype(np.float64)
    materials = make_materials(projected_texture, wall_textures)
    projection_image = Image.open(projected_texture).convert("RGB")
    counts: dict[str, int] = {}
    crop_boxes: dict[str, tuple[int, int, int, int]] = {}
    object_tints: dict[str, dict[str, Any]] = {}
    feature_panels: list[dict[str, Any]] = []

    for node_name in scene.graph.nodes_geometry:
        transform, geom_name = scene.graph[node_name]
        mesh = scene.geometry[geom_name]
        world = world_vertices(np.asarray(mesh.vertices), transform)
        if len(world):
            wbounds = np.array([world.min(axis=0), world.max(axis=0)], dtype=np.float64)
        else:
            wbounds = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64)
        category = classify_material(node_name, geom_name, wbounds)
        counts[category] = counts.get(category, 0) + 1
        if category == "room_projection":
            uv = projected_uv_from_world(world, bounds, flip_v=flip_v)
            mesh.visual = TextureVisuals(uv=uv, material=materials[category])
        elif category == "object_crop":
            atlas_uv = projected_uv_from_world(world, bounds, flip_v=flip_v)
            material, uv, crop_box = crop_material_from_projection(
                projection_image,
                atlas_uv,
                f"image2_crop_{len(crop_boxes):03d}",
            )
            crop_boxes[node_name] = crop_box
            mesh.visual = TextureVisuals(uv=uv, material=material)
        elif category.startswith("object_"):
            atlas_uv = projected_uv_from_world(world, bounds, flip_v=flip_v)
            material, uv, tint, crop_box = semantic_object_material(
                mesh,
                category,
                object_textures,
                projection_image,
                atlas_uv,
                f"{category}_{len(object_tints):03d}",
            )
            object_tints[node_name] = {
                "category": category,
                "tint": tint,
                "crop_box": crop_box,
            }
            mesh.visual = TextureVisuals(uv=uv, material=material)
        elif category.startswith("wall_"):
            uv = wall_uv_from_world(world, wbounds, category)
            mesh.visual = TextureVisuals(uv=uv, material=materials[category])
        else:
            uv = full_uv(mesh)
            mesh.visual = TextureVisuals(uv=uv, material=materials[category])

    feature_panels.append(add_bed_feature_wall_panel(scene, materials))
    counts["wall_accent"] = counts.get("wall_accent", 0) + 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output_path)
    return {
        "input_model": str(model_path),
        "output_model": str(output_path),
        "projection_texture": str(projected_texture),
        "bounds": bounds.tolist(),
        "geometry": len(scene.geometry),
        "materials": counts,
        "object_crop_count": len(crop_boxes),
        "object_crop_boxes": crop_boxes,
        "semantic_object_count": len(object_tints),
        "semantic_object_tints": object_tints,
        "feature_panels": feature_panels,
        "size_bytes": output_path.stat().st_size,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an image2 interior render and project it back onto the GLB.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--reference-render", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--mapped-dir", type=Path, default=DEFAULT_MAPPED_DIR)
    parser.add_argument("--image-model", default=os.environ.get("APIMART_IMAGE_MODEL", "gpt-image-2"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", nargs="+", default=["APIMART_API_KEY", "SCENEGEN_TEXTURE_API_KEY"])
    parser.add_argument("--prompt", default=IMAGE2_PROMPT)
    parser.add_argument("--size", default="4:3")
    parser.add_argument("--resolution", default="1k")
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--texture-width", type=int, default=1280)
    parser.add_argument("--require-api", action="store_true")
    parser.add_argument("--flip-v", action="store_true", default=True)
    parser.add_argument("--no-flip-v", dest="flip_v", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    if not args.reference_render.is_file():
        raise FileNotFoundError(args.reference_render)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.mapped_dir.mkdir(parents=True, exist_ok=True)
    final_render = args.out_dir / "final_interior_render.png"
    projection_texture = args.out_dir / "final_interior_projection_texture.png"
    mapped_glb = args.mapped_dir / "scene_image2_mapped.glb"

    image_manifest = generate_image2_render(args, args.reference_render, final_render)
    wall_manifest = generate_wall_textures(args, args.out_dir)
    object_manifest = generate_object_textures(args, args.out_dir)
    wall_paths = {
        key: Path(value["output"])
        for key, value in wall_manifest["textures"].items()
        if isinstance(value, dict) and value.get("output")
    }
    object_paths = {
        key: Path(value["output"])
        for key, value in object_manifest["textures"].items()
        if isinstance(value, dict) and value.get("output")
    }

    scene = trimesh.load(args.model, force="scene")
    bounds = scene.bounds.astype(np.float64)
    room_aspect = float((bounds[1, 0] - bounds[0, 0]) / max(bounds[1, 2] - bounds[0, 2], 1e-6))
    texture_manifest = prepare_projection_texture(final_render, projection_texture, room_aspect, args.texture_width)
    model_manifest = project_render_to_glb(args.model, projection_texture, wall_paths, object_paths, mapped_glb, flip_v=args.flip_v)

    manifest = {
        "image2": image_manifest,
        "wall_textures": wall_manifest,
        "object_textures": object_manifest,
        "projection_texture": texture_manifest,
        "model": model_manifest,
    }
    manifest_path = args.out_dir / "image2_projection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {final_render}")
    print(f"Wrote {projection_texture}")
    print(f"Wrote {mapped_glb}")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
