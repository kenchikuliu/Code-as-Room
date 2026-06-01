#!/usr/bin/env python3
"""Place generated Tripo assets back into a room GLB.

The first prototype replaces named procedural furniture groups with higher
quality Tripo-generated single-object assets while preserving the room shell.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


WEB_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_MODEL = WEB_DIR / "image2_mapped_models" / "scene_image2_mapped.glb"
DEFAULT_ASSET_MODEL = WEB_DIR / "tripo_assets" / "lounge_armchair" / "lounge_armchair.glb"
DEFAULT_OUTPUT = WEB_DIR / "tripo_assets" / "composed" / "scene_tripo_armchairs.glb"

PLACEMENT_PRESETS: dict[str, list[dict[str, Any]]] = {
    "lounge_armchair": [
        {"name": "Upper_Armchair", "prefixes": ["Upper_Armchair"], "yaw_deg": -45.0},
        {"name": "Lower_Armchair", "prefixes": ["Lower_Armchair"], "yaw_deg": 45.0},
    ]
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument("--asset-model", type=Path, default=DEFAULT_ASSET_MODEL)
    parser.add_argument("--asset-name", default="lounge_armchair", choices=sorted(PLACEMENT_PRESETS))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def node_matches(node_name: str, geom_name: str, prefixes: list[str]) -> bool:
    haystack = f"{node_name} {geom_name}"
    return any(haystack.startswith(prefix) or f" {prefix}" in haystack for prefix in prefixes)


def transformed_bounds(mesh: trimesh.Trimesh, transform: np.ndarray) -> np.ndarray:
    vertices = trimesh.transform_points(mesh.vertices, transform)
    return np.vstack([vertices.min(axis=0), vertices.max(axis=0)])


def collect_group_bounds(scene: trimesh.Scene, prefixes: list[str]) -> tuple[np.ndarray, list[str]]:
    bounds: list[np.ndarray] = []
    nodes: list[str] = []
    for node_name in scene.graph.nodes_geometry:
        transform, geom_name = scene.graph[node_name]
        if not node_matches(str(node_name), str(geom_name), prefixes):
            continue
        geom = scene.geometry[geom_name]
        if not isinstance(geom, trimesh.Trimesh) or len(geom.vertices) == 0:
            continue
        bounds.append(transformed_bounds(geom, transform))
        nodes.append(str(node_name))
    if not bounds:
        raise ValueError(f"No scene nodes matched prefixes: {prefixes}")
    stacked = np.vstack(bounds)
    return np.vstack([stacked.min(axis=0), stacked.max(axis=0)]), nodes


def copy_scene_without_nodes(scene: trimesh.Scene, excluded_nodes: set[str]) -> trimesh.Scene:
    new_scene = trimesh.Scene()
    for node_name in scene.graph.nodes_geometry:
        if str(node_name) in excluded_nodes:
            continue
        transform, geom_name = scene.graph[node_name]
        new_scene.add_geometry(
            scene.geometry[geom_name].copy(),
            node_name=str(node_name),
            geom_name=str(geom_name),
            transform=transform,
        )
    return new_scene


def yaw_matrix(degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    c = math.cos(angle)
    s = math.sin(angle)
    matrix = np.eye(4)
    matrix[0, 0] = c
    matrix[0, 2] = s
    matrix[2, 0] = -s
    matrix[2, 2] = c
    return matrix


def translation_matrix(vector: np.ndarray) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = vector[:3]
    return matrix


def scale_matrix(scale: np.ndarray) -> np.ndarray:
    matrix = np.eye(4)
    matrix[0, 0] = scale[0]
    matrix[1, 1] = scale[1]
    matrix[2, 2] = scale[2]
    return matrix


def asset_scene_bounds(asset_scene: trimesh.Scene) -> np.ndarray:
    if asset_scene.bounds is None:
        raise ValueError("Asset scene has no bounds")
    return asset_scene.bounds.astype(np.float64)


def add_asset_instance(
    scene: trimesh.Scene,
    asset_scene: trimesh.Scene,
    *,
    placement_name: str,
    target_bounds: np.ndarray,
    yaw_deg: float,
) -> dict[str, Any]:
    asset_bounds = asset_scene_bounds(asset_scene)
    asset_center = asset_bounds.mean(axis=0)
    asset_extents = np.maximum(asset_bounds[1] - asset_bounds[0], 1e-6)
    target_center = target_bounds.mean(axis=0)
    target_extents = np.maximum(target_bounds[1] - target_bounds[0], 1e-6)

    # Keep the replacement inside the old footprint and height.
    scale = target_extents / asset_extents
    transform = (
        translation_matrix(target_center)
        @ yaw_matrix(yaw_deg)
        @ scale_matrix(scale)
        @ translation_matrix(-asset_center)
    )

    for index, node_name in enumerate(asset_scene.graph.nodes_geometry):
        asset_transform, geom_name = asset_scene.graph[node_name]
        scene.add_geometry(
            asset_scene.geometry[geom_name].copy(),
            node_name=f"{placement_name}_Tripo_{index}",
            geom_name=f"{placement_name}_Tripo_{geom_name}",
            transform=transform @ asset_transform,
        )

    return {
        "placement": placement_name,
        "yaw_deg": yaw_deg,
        "target_bounds": target_bounds.tolist(),
        "target_extents": target_extents.tolist(),
        "asset_extents": asset_extents.tolist(),
        "scale": scale.tolist(),
    }


def main() -> int:
    args = parse_args()
    report_path = args.report or args.output.with_suffix(".json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    room_scene = trimesh.load(args.base_model, force="scene")
    asset_scene = trimesh.load(args.asset_model, force="scene")
    placements = PLACEMENT_PRESETS[args.asset_name]

    excluded_nodes: set[str] = set()
    placement_bounds: dict[str, np.ndarray] = {}
    placement_node_counts: dict[str, int] = {}
    for placement in placements:
        bounds, nodes = collect_group_bounds(room_scene, placement["prefixes"])
        excluded_nodes.update(nodes)
        placement_bounds[placement["name"]] = bounds
        placement_node_counts[placement["name"]] = len(nodes)

    composed = copy_scene_without_nodes(room_scene, excluded_nodes)
    placement_reports = []
    for placement in placements:
        placement_reports.append(
            add_asset_instance(
                composed,
                asset_scene,
                placement_name=placement["name"],
                target_bounds=placement_bounds[placement["name"]],
                yaw_deg=float(placement["yaw_deg"]),
            )
        )

    composed.export(args.output)
    report = {
        "base_model": str(args.base_model),
        "asset_model": str(args.asset_model),
        "output": str(args.output),
        "size_bytes": args.output.stat().st_size,
        "removed_node_count": len(excluded_nodes),
        "removed_nodes_by_placement": placement_node_counts,
        "placements": placement_reports,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
