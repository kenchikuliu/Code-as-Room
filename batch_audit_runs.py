#!/usr/bin/env python3
"""Batch-audit Code-as-Room run directories.

This script turns a folder of generated runs into a small benchmark report. It
does not call any model API; it reuses audit_run.py and Blender only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import time
from pathlib import Path
from typing import Any

from audit_run import audit


def _discover_runs(root: Path) -> list[Path]:
    if root.name.startswith("run_"):
        candidates = [root]
    else:
        candidates = [p for p in root.rglob("run_*") if p.is_dir()]
    runs = []
    for path in sorted(candidates):
        if (
            (path / "stage12_render_apimart" / "render_output.py").is_file()
            or (path / "stage12_render" / "render_output.py").is_file()
        ):
            runs.append(path)
    return runs


def _scene_summary(report: dict[str, Any]) -> dict[str, Any]:
    scene = report.get("blender", {}).get("scene", {})
    counts = scene.get("counts", {})
    diagnostics = scene.get("geometry_diagnostics", {})
    return {
        "score_ok": bool(report.get("score", {}).get("ok")),
        "passed": report.get("score", {}).get("passed", 0),
        "total": report.get("score", {}).get("total", 0),
        "objects": counts.get("objects", 0),
        "mesh_objects": counts.get("mesh_objects", 0),
        "materials": counts.get("materials", 0),
        "images": counts.get("images", 0),
        "lights": counts.get("lights", 0),
        "cameras": counts.get("cameras", 0),
        "render_engine": scene.get("render_engine", ""),
        "floor_bounds": diagnostics.get("floor_bounds"),
        "semantic_group_count": diagnostics.get("semantic_group_count", 0),
        "below_floor_count": diagnostics.get("below_floor_count", 0),
        "out_of_floor_count": diagnostics.get("out_of_floor_count", 0),
        "collision_candidate_count": diagnostics.get("collision_candidate_count", 0),
        "anomalous_dimension_count": diagnostics.get("anomalous_dimension_count", 0),
        "warnings": scene.get("warnings", []),
        "elapsed_sec": report.get("blender", {}).get("elapsed_sec"),
    }


def _write_html(index: dict[str, Any], path: Path) -> None:
    rows = []
    for row in index["runs"]:
        summary = row["summary"]
        status = "PASS" if summary["score_ok"] else "FAIL"
        status_class = "ok" if summary["score_ok"] else "bad"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(row['run_dir'])}</code></td>"
            f"<td class=\"{status_class}\">{status}</td>"
            f"<td>{summary['passed']}/{summary['total']}</td>"
            f"<td>{summary['objects']}</td>"
            f"<td>{summary['materials']}</td>"
            f"<td>{summary['images']}</td>"
            f"<td>{summary['lights']}</td>"
            f"<td>{summary['semantic_group_count']}</td>"
            f"<td>{summary['below_floor_count']}</td>"
            f"<td>{summary['out_of_floor_count']}</td>"
            f"<td>{summary['collision_candidate_count']}</td>"
            f"<td>{summary['anomalous_dimension_count']}</td>"
            f"<td>{html.escape(str(row.get('report_html', '')))}</td>"
            "</tr>"
        )

    html_text = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Code-as-Room Batch Audit</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    td, th {{ border: 1px solid #d5d9df; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f7; }}
    .ok {{ color: #087f5b; font-weight: 700; }}
    .bad {{ color: #c92a2a; font-weight: 700; }}
    code {{ background: #f3f5f7; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Code-as-Room Batch Audit</h1>
  <p>Root: <code>{html.escape(index['root'])}</code></p>
  <p>Passed: {index['passed']}/{index['total']} run(s)</p>
  <table>
    <tr>
      <th>Run</th><th>Status</th><th>Checks</th><th>Objects</th><th>Materials</th>
      <th>Images</th><th>Lights</th><th>Groups</th><th>Below Floor</th>
      <th>Out of Floor</th><th>Collisions</th><th>Dim Anomalies</th><th>Report</th>
    </tr>
    {''.join(rows)}
  </table>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    blender = Path(args.blender or os.environ.get("BLENDER", "")).resolve()
    runs = _discover_runs(root)
    if args.max_runs:
        runs = runs[: args.max_runs]

    rows = []
    passed = 0
    started = time.perf_counter()
    for i, run_dir in enumerate(runs, start=1):
        print(f"[{i}/{len(runs)}] Auditing {run_dir}")
        report = audit(
            argparse.Namespace(
                run_dir=str(run_dir),
                blender=str(blender),
                stage12_dir=args.stage12_dir,
                render=args.render,
                save_blend=args.save_blend,
                timeout=args.timeout,
            )
        )
        summary = _scene_summary(report)
        if summary["score_ok"]:
            passed += 1
        rows.append(
            {
                "run_dir": str(run_dir),
                "stage12_dir": report.get("stage12_dir"),
                "report_json": report.get("report_json"),
                "report_html": report.get("report_html"),
                "summary": summary,
            }
        )
        print(
            f"    {'PASS' if summary['score_ok'] else 'FAIL'} "
            f"{summary['passed']}/{summary['total']} checks, "
            f"{summary['objects']} objects, {summary['images']} images"
        )

    index = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "root": str(root),
        "blender": str(blender),
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "runs": rows,
    }

    output_dir = Path(args.output_dir).resolve() if args.output_dir else root
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "batch_audit_report.json"
    html_path = output_dir / "batch_audit_report.html"
    index["report_json"] = str(json_path)
    index["report_html"] = str(html_path)
    json_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_html(index, html_path)
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-audit Code-as-Room generated runs.")
    parser.add_argument("--root", required=True, help="Root containing run_* directories, or one run_* directory.")
    parser.add_argument("--blender", default=os.environ.get("BLENDER"), help="Path to Blender executable.")
    parser.add_argument("--stage12-dir", help="Stage 12 directory name to audit, e.g. stage12_render_apimart.")
    parser.add_argument("--output-dir", help="Where to write batch_audit_report.json/html. Default: --root.")
    parser.add_argument("--render", action="store_true", help="Render an audit still for each run.")
    parser.add_argument("--save-blend", action="store_true", help="Save an audit .blend for each run.")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run Blender timeout in seconds.")
    parser.add_argument("--max-runs", type=int, help="Limit discovered runs for quick smoke tests.")
    parser.add_argument("--fail-on-bad", action="store_true", help="Return non-zero if any run fails audit.")
    args = parser.parse_args()

    index = run_batch(args)
    print(
        f"Batch audit: {index['passed']}/{index['total']} passed "
        f"in {index['elapsed_sec']:.1f}s"
    )
    print(f"JSON: {index['report_json']}")
    print(f"HTML: {index['report_html']}")
    if args.fail_on_bad and index["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
