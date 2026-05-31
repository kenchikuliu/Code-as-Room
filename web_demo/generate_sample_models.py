from __future__ import annotations

from pathlib import Path

import trimesh
from PIL import Image, ImageDraw


OUT_DIR = Path(__file__).resolve().parent / "sample_models"


PALETTE = {
    "floor": (210, 205, 194, 255),
    "wall": (245, 244, 239, 255),
    "wood": (122, 88, 62, 255),
    "bed": (235, 238, 240, 255),
    "fabric": (92, 122, 143, 255),
    "desk": (196, 158, 107, 255),
    "green": (110, 160, 116, 255),
    "stone": (156, 160, 155, 255),
    "accent": (194, 92, 74, 255),
    "blue": (82, 130, 176, 255),
    "yellow": (214, 176, 86, 255),
}


def box(name: str, size: tuple[float, float, float], center: tuple[float, float, float], color: tuple[int, int, int, int]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(center)
    mesh.visual.face_colors = color
    mesh.metadata["name"] = name
    return mesh


def add_room_shell(scene: trimesh.Scene, width: float, depth: float, wall: float = 0.16) -> None:
    scene.add_geometry(box("floor", (width, depth, 0.06), (0, 0, -0.03), PALETTE["floor"]), node_name="floor")
    h = 1.15
    scene.add_geometry(box("wall_north", (width, wall, h), (0, depth / 2, h / 2), PALETTE["wall"]), node_name="wall_north")
    scene.add_geometry(box("wall_south", (width, wall, h), (0, -depth / 2, h / 2), PALETTE["wall"]), node_name="wall_south")
    scene.add_geometry(box("wall_west", (wall, depth, h), (-width / 2, 0, h / 2), PALETTE["wall"]), node_name="wall_west")
    scene.add_geometry(box("wall_east", (wall, depth, h), (width / 2, 0, h / 2), PALETTE["wall"]), node_name="wall_east")


def add_furniture(scene: trimesh.Scene, items: list[tuple[str, tuple[float, float, float], tuple[float, float, float], str]]) -> None:
    for name, size, center, color_key in items:
        scene.add_geometry(box(name, size, center, PALETTE[color_key]), node_name=name)


def build_studio() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 7.2, 5.4)
    add_furniture(scene, [
        ("bed_frame", (2.1, 1.6, 0.28), (-2.1, 1.3, 0.14), "wood"),
        ("mattress", (1.9, 1.4, 0.18), (-2.1, 1.3, 0.36), "bed"),
        ("sofa", (1.9, 0.72, 0.52), (1.55, 1.55, 0.26), "fabric"),
        ("coffee_table", (1.0, 0.55, 0.22), (1.55, 0.55, 0.11), "desk"),
        ("desk", (1.35, 0.58, 0.42), (-2.35, -1.65, 0.21), "desk"),
        ("kitchen_run", (2.2, 0.55, 0.62), (2.1, -1.85, 0.31), "stone"),
        ("plant", (0.35, 0.35, 0.55), (3.05, 2.0, 0.28), "green"),
    ])
    return scene


def build_office() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 8.2, 5.8)
    add_furniture(scene, [
        ("partition_long", (0.14, 3.6, 0.92), (-0.7, 0.2, 0.46), "wall"),
        ("meeting_table", (2.1, 1.05, 0.34), (2.0, 1.0, 0.17), "desk"),
        ("desk_a", (1.2, 0.62, 0.38), (-2.7, 1.7, 0.19), "desk"),
        ("desk_b", (1.2, 0.62, 0.38), (-2.7, 0.35, 0.19), "desk"),
        ("desk_c", (1.2, 0.62, 0.38), (-2.7, -1.0, 0.19), "desk"),
        ("storage_wall", (2.0, 0.36, 0.88), (2.4, -2.2, 0.44), "wood"),
        ("sofa_waiting", (1.7, 0.62, 0.48), (0.65, -2.05, 0.24), "blue"),
    ])
    return scene


def build_retail() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 7.8, 6.2)
    add_furniture(scene, [
        ("display_island", (2.0, 0.9, 0.45), (0.0, 0.2, 0.23), "yellow"),
        ("display_table_left", (1.45, 0.65, 0.4), (-2.2, 1.45, 0.2), "desk"),
        ("display_table_right", (1.45, 0.65, 0.4), (2.2, 1.45, 0.2), "desk"),
        ("shelf_north", (4.8, 0.34, 0.85), (0.0, 2.65, 0.43), "wood"),
        ("cash_wrap", (1.55, 0.75, 0.68), (2.75, -2.0, 0.34), "stone"),
        ("accent_rug", (2.4, 1.8, 0.04), (-1.0, -1.6, 0.03), "accent"),
    ])
    return scene


def build_kitchen() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 7.4, 5.6)
    add_furniture(scene, [
        ("cabinet_wall", (4.8, 0.52, 0.68), (0.0, 2.15, 0.34), "stone"),
        ("island", (2.25, 0.92, 0.72), (-0.7, 0.25, 0.36), "desk"),
        ("dining_table", (1.55, 1.05, 0.38), (2.1, -1.45, 0.19), "wood"),
        ("bench_a", (1.35, 0.32, 0.32), (2.1, -0.75, 0.16), "fabric"),
        ("bench_b", (1.35, 0.32, 0.32), (2.1, -2.15, 0.16), "fabric"),
        ("pantry", (0.7, 0.8, 1.0), (-3.0, 1.95, 0.5), "wood"),
        ("plant_corner", (0.38, 0.38, 0.58), (-3.0, -2.1, 0.29), "green"),
    ])
    return scene


def build_gallery() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 8.6, 5.2)
    add_furniture(scene, [
        ("plinth_a", (0.75, 0.75, 0.62), (-2.7, 1.0, 0.31), "stone"),
        ("plinth_b", (0.75, 0.75, 0.82), (-0.7, -0.9, 0.41), "stone"),
        ("plinth_c", (0.75, 0.75, 0.55), (1.45, 1.15, 0.28), "stone"),
        ("bench", (1.9, 0.45, 0.32), (2.55, -1.45, 0.16), "wood"),
        ("divider", (0.14, 2.4, 0.9), (-3.4, -0.75, 0.45), "wall"),
        ("feature_wall", (2.1, 0.18, 0.95), (0.4, 2.15, 0.48), "accent"),
    ])
    return scene


def build_compact() -> trimesh.Scene:
    scene = trimesh.Scene()
    add_room_shell(scene, 5.8, 6.4)
    add_furniture(scene, [
        ("sleeping_platform", (2.05, 1.45, 0.36), (-1.35, 1.55, 0.18), "wood"),
        ("mattress", (1.85, 1.25, 0.16), (-1.35, 1.55, 0.44), "bed"),
        ("bath_partition", (0.14, 2.0, 0.98), (1.1, 1.55, 0.49), "wall"),
        ("vanity", (1.15, 0.52, 0.62), (2.1, 2.2, 0.31), "stone"),
        ("wardrobe", (0.72, 1.8, 0.92), (-2.35, -1.5, 0.46), "wood"),
        ("folding_table", (1.15, 0.7, 0.38), (1.45, -1.6, 0.19), "desk"),
        ("chair", (0.48, 0.48, 0.5), (2.3, -1.6, 0.25), "blue"),
    ])
    return scene


def draw_preview(path: Path, title: str, width: float, depth: float, items: list[tuple[float, float, float, float, tuple[int, int, int]]]) -> None:
    image = Image.new("RGB", (960, 720), (20, 23, 28))
    draw = ImageDraw.Draw(image)
    margin = 70
    scale = min((960 - margin * 2) / width, (720 - margin * 2) / depth)
    cx, cy = 480, 380

    def to_px(x: float, y: float) -> tuple[int, int]:
        return int(cx + x * scale), int(cy - y * scale)

    left, top = to_px(-width / 2, depth / 2)
    right, bottom = to_px(width / 2, -depth / 2)
    draw.rectangle([left, top, right, bottom], fill=(218, 214, 204), outline=(245, 245, 240), width=8)
    for x, y, w, d, color in items:
        x1, y1 = to_px(x - w / 2, y + d / 2)
        x2, y2 = to_px(x + w / 2, y - d / 2)
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=(55, 58, 63), width=2)
    draw.text((32, 28), title, fill=(245, 247, 251))
    image.save(path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        ("sample_2_studio.glb", "preview_2_studio.png", "Example 2 - Studio Apartment", build_studio, 7.2, 5.4, [
            (-2.1, 1.3, 2.1, 1.6, (235, 238, 240)),
            (1.55, 1.55, 1.9, 0.72, (92, 122, 143)),
            (2.1, -1.85, 2.2, 0.55, (156, 160, 155)),
            (-2.35, -1.65, 1.35, 0.58, (196, 158, 107)),
        ]),
        ("sample_3_office.glb", "preview_3_office.png", "Example 3 - L Office", build_office, 8.2, 5.8, [
            (-0.7, 0.2, 0.14, 3.6, (245, 244, 239)),
            (2.0, 1.0, 2.1, 1.05, (196, 158, 107)),
            (-2.7, 1.7, 1.2, 0.62, (196, 158, 107)),
            (-2.7, 0.35, 1.2, 0.62, (196, 158, 107)),
            (-2.7, -1.0, 1.2, 0.62, (196, 158, 107)),
        ]),
        ("sample_4_retail.glb", "preview_4_retail.png", "Example 4 - Retail Loft", build_retail, 7.8, 6.2, [
            (0.0, 0.2, 2.0, 0.9, (214, 176, 86)),
            (-2.2, 1.45, 1.45, 0.65, (196, 158, 107)),
            (2.2, 1.45, 1.45, 0.65, (196, 158, 107)),
            (0.0, 2.65, 4.8, 0.34, (122, 88, 62)),
            (2.75, -2.0, 1.55, 0.75, (156, 160, 155)),
        ]),
        ("sample_5_kitchen.glb", "preview_5_kitchen.png", "Example 5 - Kitchen Dining", build_kitchen, 7.4, 5.6, [
            (0.0, 2.15, 4.8, 0.52, (156, 160, 155)),
            (-0.7, 0.25, 2.25, 0.92, (196, 158, 107)),
            (2.1, -1.45, 1.55, 1.05, (122, 88, 62)),
            (2.1, -0.75, 1.35, 0.32, (92, 122, 143)),
            (2.1, -2.15, 1.35, 0.32, (92, 122, 143)),
        ]),
        ("sample_6_compact.glb", "preview_6_compact.png", "Example 6 - Compact Suite", build_compact, 5.8, 6.4, [
            (-1.35, 1.55, 2.05, 1.45, (235, 238, 240)),
            (1.1, 1.55, 0.14, 2.0, (245, 244, 239)),
            (2.1, 2.2, 1.15, 0.52, (156, 160, 155)),
            (-2.35, -1.5, 0.72, 1.8, (122, 88, 62)),
            (1.45, -1.6, 1.15, 0.7, (196, 158, 107)),
        ]),
    ]
    for glb_name, preview_name, title, builder, width, depth, preview_items in specs:
        scene = builder()
        scene.export(OUT_DIR / glb_name)
        draw_preview(OUT_DIR / preview_name, title, width, depth, preview_items)
        print(f"Wrote {OUT_DIR / glb_name}")
        print(f"Wrote {OUT_DIR / preview_name}")


if __name__ == "__main__":
    main()
