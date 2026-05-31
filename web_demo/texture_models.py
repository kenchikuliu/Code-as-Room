from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "repro_outputs" / "gpt55_stage1_4" / "run_20260530_141733_example1"
SOURCE_MAIN = SOURCE_DIR / "optimized_scene" / "scene.glb"
SAMPLE_DIR = WEB_DIR / "sample_models"
OUT_DIR = WEB_DIR / "textured_models"


INPUTS = [
    (SOURCE_MAIN, OUT_DIR / "scene_textured.glb"),
    (SAMPLE_DIR / "sample_2_studio.glb", OUT_DIR / "sample_2_studio_textured.glb"),
    (SAMPLE_DIR / "sample_3_office.glb", OUT_DIR / "sample_3_office_textured.glb"),
    (SAMPLE_DIR / "sample_4_retail.glb", OUT_DIR / "sample_4_retail_textured.glb"),
    (SAMPLE_DIR / "sample_5_kitchen.glb", OUT_DIR / "sample_5_kitchen_textured.glb"),
    (SAMPLE_DIR / "sample_6_compact.glb", OUT_DIR / "sample_6_compact_textured.glb"),
]


def clamp_channel(value: int) -> int:
    return max(0, min(255, value))


def jitter(color: tuple[int, int, int], amount: int, rng: np.random.Generator) -> tuple[int, int, int]:
    return tuple(clamp_channel(c + int(rng.integers(-amount, amount + 1))) for c in color)


def noise_texture(base: tuple[int, int, int], accent: tuple[int, int, int], *, seed: int, size: int = 192, strength: int = 18) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            wave = int(8 * np.sin((x + y * 0.35) / 13.0))
            if rng.random() < 0.08:
                color = jitter(accent, strength, rng)
            else:
                color = jitter(base, strength + wave, rng)
            arr[y, x] = color
    return Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(radius=0.35))


def wood_texture(seed: int, size: int = 256) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = Image.new("RGB", (size, size), (118, 76, 43))
    draw = ImageDraw.Draw(image)
    plank_w = size // 7
    for x in range(0, size, plank_w):
        base = jitter((132, 86, 48), 18, rng)
        draw.rectangle([x, 0, min(size, x + plank_w), size], fill=base)
        draw.line([x, 0, x, size], fill=(64, 43, 29), width=2)
        for _ in range(12):
            y = int(rng.integers(0, size))
            amp = int(rng.integers(7, 18))
            color = jitter((92, 58, 34), 14, rng)
            points = []
            for i in range(0, plank_w + 6, 6):
                px = min(size - 1, x + i)
                py = int(y + np.sin((i + seed) / amp) * rng.uniform(2, 7))
                points.append((px, max(0, min(size - 1, py))))
            draw.line(points, fill=color, width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.25))


def floor_texture(seed: int, size: int = 256) -> Image.Image:
    image = wood_texture(seed, size)
    draw = ImageDraw.Draw(image)
    plank_h = size // 8
    for y in range(0, size, plank_h):
        draw.line([0, y, size, y], fill=(74, 50, 35), width=2)
    return image


def fabric_texture(base: tuple[int, int, int], seed: int, size: int = 192) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = noise_texture(base, tuple(max(0, c - 35) for c in base), seed=seed, size=size, strength=10)
    draw = ImageDraw.Draw(image)
    for i in range(0, size, 8):
        line_color = jitter(tuple(max(0, c - 24) for c in base), 8, rng)
        draw.line([0, i, size, i], fill=line_color, width=1)
        draw.line([i, 0, i, size], fill=jitter(tuple(min(255, c + 20) for c in base), 8, rng), width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.2))


def stone_texture(seed: int, size: int = 192) -> Image.Image:
    image = noise_texture((156, 157, 151), (210, 210, 202), seed=seed, size=size, strength=16)
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(seed)
    for _ in range(18):
        x0, y0 = int(rng.integers(0, size)), int(rng.integers(0, size))
        x1 = max(0, min(size, x0 + int(rng.integers(-80, 80))))
        y1 = max(0, min(size, y0 + int(rng.integers(-80, 80))))
        draw.line([x0, y0, x1, y1], fill=(112, 112, 108), width=1)
    return image.filter(ImageFilter.GaussianBlur(radius=0.35))


def glass_texture(seed: int, size: int = 128) -> Image.Image:
    rng = np.random.default_rng(seed)
    image = Image.new("RGBA", (size, size), (176, 218, 238, 95))
    draw = ImageDraw.Draw(image)
    for i in range(0, size, 18):
        color = (230, 248, 255, int(rng.integers(75, 130)))
        draw.line([i, 0, min(size, i + size // 2), size], fill=color, width=2)
    return image.filter(ImageFilter.GaussianBlur(radius=0.6))


def make_textures() -> dict[str, Image.Image]:
    return {
        "floor": floor_texture(1),
        "wall": noise_texture((236, 234, 226), (247, 246, 241), seed=2, strength=9),
        "wood": wood_texture(3),
        "dark_wood": wood_texture(4),
        "fabric": fabric_texture((128, 142, 151), seed=5),
        "bedding": fabric_texture((232, 229, 221), seed=6),
        "rug": fabric_texture((159, 123, 93), seed=7),
        "stone": stone_texture(8),
        "metal": noise_texture((183, 178, 166), (226, 222, 210), seed=9, size=128, strength=8),
        "glass": glass_texture(10),
        "foliage": noise_texture((58, 126, 63), (35, 78, 38), seed=11, strength=18),
        "soil": noise_texture((73, 50, 35), (38, 30, 23), seed=12, size=128, strength=10),
        "ceramic": noise_texture((226, 218, 203), (248, 244, 236), seed=13, size=128, strength=7),
        "accent": fabric_texture((178, 89, 75), seed=14, size=160),
        "dark": noise_texture((54, 48, 44), (85, 76, 66), seed=15, size=128, strength=8),
    }


TEXTURES = make_textures()


def material_for(category: str) -> PBRMaterial:
    image = TEXTURES[category]
    alpha_mode = "BLEND" if category == "glass" else "OPAQUE"
    metallic = 0.55 if category == "metal" else 0.0
    roughness = {
        "glass": 0.12,
        "metal": 0.38,
        "stone": 0.48,
        "floor": 0.62,
        "wood": 0.56,
        "dark_wood": 0.52,
    }.get(category, 0.82)
    return PBRMaterial(
        name=f"car_{category}",
        baseColorTexture=image,
        baseColorFactor=[255, 255, 255, 255],
        metallicFactor=metallic,
        roughnessFactor=roughness,
        alphaMode=alpha_mode,
        doubleSided=True,
    )


MATERIALS = {name: material_for(name) for name in TEXTURES}


def classify(node_name: str, geom_name: str) -> str:
    name = f"{node_name} {geom_name}".lower()

    # Object-level materials first.
    if any(token in name for token in ["foliage", "plant", "leaf"]):
        if "pot" in name:
            return "ceramic"
        if "soil" in name:
            return "soil"
        return "foliage"
    if "soil" in name:
        return "soil"
    if any(token in name for token in ["mirror", "glass", "window"]):
        return "glass"
    if any(token in name for token in ["metal", "handle", "knob", "stem", "pole", "rail", "spike", "cap"]):
        return "metal"
    if any(token in name for token in ["lamp_shade", "shade", "curtain", "clothes", "garment"]):
        return "fabric"
    if any(token in name for token in ["pillow", "bedding", "duvet", "sheet", "blanket", "mattress"]):
        return "bedding"
    if any(token in name for token in ["sofa", "armchair", "seat", "cushion", "bench_a", "bench_b", "chair"]):
        return "fabric"
    if any(token in name for token in ["counter", "kitchen", "vanity", "cash_wrap", "plinth", "stone"]):
        return "stone"
    if any(token in name for token in ["bed_frame", "headboard", "wardrobe", "cabinet", "shelf", "drawer", "nightstand", "console", "table", "desk", "wood", "storage", "pantry", "island"]):
        return "wood"
    if any(token in name for token in ["vase", "pot", "decor_box", "decorative", "ceramic"]):
        return "ceramic"

    # Room-level materials after objects.
    if "floor" in name:
        return "floor"
    if "rug" in name:
        return "rug"
    if any(token in name for token in ["wall", "partition", "panel"]):
        return "wall"
    if any(token in name for token in ["accent", "feature"]):
        return "accent"
    if any(token in name for token in ["base", "block", "body"]):
        return "dark_wood"
    return "ceramic"


def uv_for_mesh(mesh: trimesh.Trimesh, category: str) -> np.ndarray:
    existing = getattr(getattr(mesh, "visual", None), "uv", None)
    if existing is not None and len(existing) == len(mesh.vertices):
        uv = np.asarray(existing, dtype=np.float32).copy()
    else:
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        if len(vertices) == 0:
            return np.zeros((0, 2), dtype=np.float32)
        extents = np.ptp(vertices, axis=0)
        axes = np.argsort(extents)[-2:]
        uv = vertices[:, axes]
        mins = uv.min(axis=0)
        span = np.maximum(uv.max(axis=0) - mins, 1e-6)
        uv = (uv - mins) / span

    tile = {
        "floor": 4.0,
        "wall": 2.4,
        "wood": 2.0,
        "dark_wood": 2.0,
        "fabric": 2.0,
        "rug": 3.0,
        "stone": 1.8,
        "foliage": 1.6,
    }.get(category, 1.0)
    return (uv * tile).astype(np.float32)


def texture_scene(input_path: Path, output_path: Path) -> dict[str, int | str]:
    scene = trimesh.load(input_path, force="scene")
    counts: dict[str, int] = {}

    for node_name in scene.graph.nodes_geometry:
        _, geom_name = scene.graph[node_name]
        mesh = scene.geometry[geom_name]
        category = classify(node_name, geom_name)
        counts[category] = counts.get(category, 0) + 1
        uv = uv_for_mesh(mesh, category)
        mesh.visual = TextureVisuals(uv=uv, material=MATERIALS[category])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output_path)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "geometry": len(scene.geometry),
        "categories": counts,
        "size_bytes": output_path.stat().st_size,
    }


def main() -> None:
    reports = []
    for input_path, output_path in INPUTS:
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        report = texture_scene(input_path, output_path)
        reports.append(report)
        print(f"Wrote {output_path}")

    report_path = OUT_DIR / "texture_report.json"
    report_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
