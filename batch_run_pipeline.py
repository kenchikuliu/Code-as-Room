#!/usr/bin/env python3
"""
Batch-run run_pipeline.py for every image under generated_images/.

Output layout
-------------
Each batch goes to:
  <output-root>/<model_slug>/<label_slug>/run_<timestamp>_<image_stem>/

Where:
  - <output-root>  defaults to <repo>/agent_utils/pipeline_output/
  - <model_slug>   is a filesystem-cleaned form of --model
                   (e.g. "[official]gemini-3.1-pro-preview" -> "gemini-3.1-pro-preview")
                   Falls back to "default" when --model is omitted.
                   Override with --model-tag.
  - <label_slug>   comes from --label (e.g. "bedroom", "kitchen_v2").
                   When omitted, the model layer is followed directly by run_*.

This keeps "same image type, different models" and "same model, different image
types" both easy to compare side-by-side.

Examples:
  # Default model + bedroom batch
  python batch_run_pipeline.py --images-dir generated_images/bedroom --label bedroom

  # Claude opus on kitchens (custom model + label)
  python batch_run_pipeline.py \\
      --images-dir generated_images/kitchen \\
      --model "claude-opus-4-6" \\
      --base-url "https://esapi.top/v1" \\
      --api-key "sk-..." \\
      --label kitchen

Options:
  --images-dir PATH   Folder of images (default: ./generated_images under repo root)
  --output-root PATH  Where batch results land (default: agent_utils/pipeline_output)
  --label TEXT        Image-class label that becomes a sub-directory.
  --model-tag TEXT    Override the auto-derived model directory name.
  --start / --end     Same as run_pipeline
  --dry-run           Only list images + planned output paths, do not run
  --stop-on-error     Exit on first failed image (default: continue)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _project_paths() -> tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir
    agent_utils = project_root / "agent_utils"
    return project_root, agent_utils


def collect_images(images_dir: Path) -> list[Path]:
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    files = []
    for p in sorted(images_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(p)
    return files


# ---------------------------------------------------------------------------
# Naming helpers (kept tiny on purpose; no exotic chars survive)
# ---------------------------------------------------------------------------
def slugify(s: str | None, *, fallback: str = "") -> str:
    """Filesystem-safe slug.

    Strips brackets / Chinese brackets, replaces whitespace and path
    separators with '_', drops anything outside [A-Za-z0-9_.-].
    Returns ``fallback`` if the result is empty.
    """
    if not s:
        return fallback
    s = re.sub(r"[\[\]\(\)\{\}【】（）]", "", s)
    s = re.sub(r"[\s/\\]+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_.\-]", "", s)
    s = s.strip("_-.")
    return s or fallback


def build_run_dir(
    output_root: Path,
    model_slug: str,
    label_slug: str,
    image_path: Path,
    timestamp: str | None = None,
) -> Path:
    """Compose the per-image run directory under (model)/(label)/run_<ts>_<stem>."""
    ts = timestamp or time.strftime("%Y%m%d_%H%M%S")
    stem = image_path.stem[:50].rstrip("_-")
    parts: list[Path] = [output_root]
    if model_slug:
        parts.append(Path(model_slug))
    if label_slug:
        parts.append(Path(label_slug))
    parts.append(Path(f"run_{ts}_{stem}"))
    out = parts[0]
    for p in parts[1:]:
        out = out / p
    return out


# ---------------------------------------------------------------------------
# Pipeline-result classifier
# ---------------------------------------------------------------------------
# `run_pipeline.run_full_pipeline` defines `success` strictly: every
# stage in the requested range must report success. That's too harsh for
# batch reporting because Stage 3 routinely returns success=False purely
# because its image-similarity score didn't clear the runner's threshold,
# even though Stage 3 still emits a valid Blender script and later stages
# happily run on top of it. Treating that as a batch failure inflates the
# "Failed" list with rooms that actually rendered fine.
#
# We re-classify each pipeline result into:
#   ok      - run_full_pipeline returned success=True (everything cleared).
#   partial - the ONLY stage that failed is stage3, AND the final stage
#             in the requested range still succeeded. Stage 3 quality is
#             captured in `<run_dir>/run.log` and `stage3_iter*.py` files;
#             we refuse to fail the batch over a low score when the rest
#             of the pipeline produced renderable output.
#   failed  - anything else (any non-stage3 failure, or final stage didn't
#             succeed). These are the only entries that go into the
#             "Failed" list and into the process exit code.
def _classify_pipeline_outcome(
    result: dict, end_stage: int
) -> tuple[str, str]:
    """Return (status, note) where status is 'ok' / 'partial' / 'failed'."""
    if result.get("success"):
        return "ok", ""

    stages = result.get("stages") or {}
    failed = sorted(
        k for k, v in stages.items()
        if isinstance(v, dict) and v.get("success") is False
    )

    # Determine the "final stage" key for the requested range. For
    end_key_candidates = [f"stage{end_stage}"]
    end_ok = any(
        isinstance(stages.get(k), dict) and stages[k].get("success") is True
        for k in end_key_candidates
    )

    stage3_score = (stages.get("stage3") or {}).get("score")
    if (
        failed == ["stage3"]
        and end_ok
        and stage3_score is not None
    ):
        return "partial", (
            f"Stage 3 score {stage3_score:.2f} below threshold; "
            "Stages 4..end completed."
        )

    if failed:
        return "failed", "failed stages: " + ",".join(failed)
    return "failed", "pipeline reported failure"


# ---------------------------------------------------------------------------
# Multiprocess worker
# ---------------------------------------------------------------------------
# IMPORTANT: this function MUST live at module top-level so
# ProcessPoolExecutor can pickle it. It is a self-contained one-shot
# wrapper around `run_pipeline.run_full_pipeline` that:
#   1. Inserts agent_utils on sys.path inside the child process (each
#      worker process has its own sys.path).
#   2. Redirects stdout/stderr to <run_dir>/run.log so that N concurrent
#      pipelines do not interleave their (very chatty) progress output in
#      the parent terminal. The parent prints a one-line summary on
#      completion, the per-image log keeps the full trace.
#   3. Returns a dict (instead of raising) so the parent can show all
#      failures at the end without one bad image killing the batch.
def _run_one_image(payload: dict) -> dict:
    """Run run_pipeline for a single image. Top-level for pickling."""
    image_path: str = payload["image_path"]
    run_dir: str = payload["run_dir"]
    agent_utils: str = payload["agent_utils"]
    pipeline_kwargs: dict = payload["pipeline_kwargs"]

    import sys as _sys
    import time as _time
    from pathlib import Path as _Path

    # Each child process needs its own sys.path entry.
    if agent_utils not in _sys.path:
        _sys.path.insert(0, agent_utils)

    log_path = _Path(run_dir) / "run.log"
    _Path(run_dir).mkdir(parents=True, exist_ok=True)

    t0 = _time.perf_counter()
    status = "failed"
    err_msg = ""
    try:
        # Line-buffered (buffering=1) so a `tail -f` on the log file
        # streams output in real time even though we're inside a worker.
        with open(log_path, "w", encoding="utf-8", buffering=1) as logf:
            old_out, old_err = _sys.stdout, _sys.stderr
            _sys.stdout = logf
            _sys.stderr = logf
            try:
                from run_pipeline import run_full_pipeline
                result = run_full_pipeline(
                    image_path=image_path,
                    output_dir=run_dir,
                    **pipeline_kwargs,
                )
                end_stage = pipeline_kwargs.get("end_stage", 11)
                status, note = _classify_pipeline_outcome(result, end_stage)
                err_msg = note
            finally:
                _sys.stdout = old_out
                _sys.stderr = old_err
    except Exception as e:  # noqa: BLE001
        # Capture the traceback into the log too — by now stdout is
        # restored, so we open the log in append mode and dump it.
        import traceback
        try:
            with open(log_path, "a", encoding="utf-8") as logf:
                logf.write("\n=== Worker exception ===\n")
                traceback.print_exc(file=logf)
        except Exception:  # noqa: BLE001
            pass
        status = "failed"
        err_msg = f"{type(e).__name__}: {e}"

    return {
        "image_name": _Path(image_path).name,
        "status": status,
        "success": status == "ok",
        "elapsed": _time.perf_counter() - t0,
        "error": err_msg,
        "run_dir": run_dir,
        "log_path": str(log_path),
    }


def main() -> int:
    project_root, agent_utils = _project_paths()
    default_images = Path(__file__).resolve().parent / "generated_images"

    parser = argparse.ArgumentParser(description="Batch run run_pipeline on generated_images")
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=default_images,
        help="Directory containing input images",
    )
    parser.add_argument("--start", type=int, default=1, choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    parser.add_argument("--end", type=int, default=12, choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    parser.add_argument("--max-iter", type=int, default=5)
    parser.add_argument("--no-iterate", action="store_true", help="Stage3 single pass")
    parser.add_argument("--enable-rotation", action="store_true", help="Enable rotation correction after Stage3")
    parser.add_argument("--no-rotation", action="store_true", help="Disable rotation correction after Stage3")
    parser.add_argument("--rotation-iter", type=int, default=3, help="Rotation correction iterations")
    parser.add_argument("--parallel", type=int, default=8, help="Stage 6 geometry parallel workers")
    parser.add_argument("--no-compress", action="store_true")
    parser.add_argument("--image-target-kb", type=int, default=1024)
    parser.add_argument("--model", type=str, default=None, help="Global LLM model name (overrides default)")
    parser.add_argument("--base-url", type=str, default=None, help="Global API base URL (overrides default)")
    parser.add_argument("--api-key", type=str, default=None, help="Global API key (overrides default)")
    # Output-organisation knobs (v3, 2026-05-02)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Root for batch outputs (default: <repo>/agent_utils/pipeline_output)",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="",
        help="Image-class label, becomes a sub-directory (e.g. 'bedroom', 'kitchen_v2')",
    )
    parser.add_argument(
        "--model-tag",
        type=str,
        default=None,
        help="Override the auto-derived model directory name (defaults to slug of --model, "
             "or 'default' when --model is omitted)",
    )
    parser.add_argument(
        "--max-concurrent",
        "-j",
        type=int,
        default=1,
        help=(
            "Run this many pipelines in parallel via ProcessPoolExecutor. "
            "Default 1 = sequential (legacy behaviour). Each worker writes its "
            "full pipeline log to <run_dir>/run.log; the parent terminal only "
            "shows one summary line per finished image. NOTE: each worker can "
            "spawn a Blender subprocess (Stage 3) and call LLM APIs — keep this "
            "small enough to respect (a) your machine's RAM/CPU and (b) the API "
            "rate limit. 2-4 is a safe starting point on a 16GB box."
        ),
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    args = parser.parse_args()
    """
    python /Users/yangyixuan/SceneGen_Agent_new/batch_run_pipeline.py --parallel 16 --quiet
    """
    images_dir = args.images_dir
    if not images_dir.is_absolute():
        images_dir = (Path.cwd() / images_dir).resolve()

    if args.start > args.end:
        print(f"--start ({args.start}) must be <= --end ({args.end})", file=sys.stderr)
        return 2

    try:
        images = collect_images(images_dir)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if not images:
        print(f"No images found in {images_dir}", file=sys.stderr)
        return 1

    # Resolve naming: --model-tag wins; else slugify --model; else "default".
    if args.model_tag:
        model_slug = slugify(args.model_tag, fallback="default")
    elif args.model:
        model_slug = slugify(args.model, fallback="default")
    else:
        model_slug = "default"
    label_slug = slugify(args.label, fallback="")

    output_root = args.output_root
    if output_root is None:
        output_root = agent_utils / "pipeline_output"
    if not output_root.is_absolute():
        output_root = (Path.cwd() / output_root).resolve()

    print(f"Found {len(images)} image(s) in {images_dir}")
    print(f"Output root : {output_root}")
    print(f"Model dir   : {model_slug}")
    print(f"Label dir   : {label_slug or '(none)'}")
    print()
    # Pre-compute (and print) the full target dir for every image so the
    # user can sanity-check the layout before the long run starts. We use
    # one frozen timestamp per image to keep dry-run output and the actual
    # run aligned 1:1.
    plan: list[tuple[Path, Path, str]] = []  # (image, run_dir, ts)
    for p in images:
        ts = time.strftime("%Y%m%d_%H%M%S")
        # Sleep tiny step to keep timestamps unique within the same second;
        # only matters for dry-run pretty-print, real runs serialize anyway.
        time.sleep(0.001)
        rd = build_run_dir(output_root, model_slug, label_slug, p, timestamp=ts)
        plan.append((p, rd, ts))
        print(f"  - {p.name}\n      -> {rd.relative_to(output_root) if rd.is_relative_to(output_root) else rd}")

    if args.dry_run:
        return 0

    # Build the kwargs dict we'll forward to run_full_pipeline ONCE here so
    # both the sequential and the parallel path send identical settings.
    pipeline_kwargs: dict[str, Any] = dict(
        start_stage=args.start,
        end_stage=args.end,
        max_iterations=args.max_iter,
        stage3_iterate=not args.no_iterate,
        stage3_rotation=args.enable_rotation and not args.no_rotation,
        stage3_rotation_iterations=args.rotation_iter,
        stage8_parallel=args.parallel,
        compress_image=not args.no_compress,
        image_target_kb=args.image_target_kb,
        verbose=not args.quiet,
    )
    if args.model:
        pipeline_kwargs["model"] = args.model
    if args.base_url:
        pipeline_kwargs["base_url"] = args.base_url
    if args.api_key:
        pipeline_kwargs["api_key"] = args.api_key

    bucket = (
        output_root / model_slug / label_slug
        if label_slug else output_root / model_slug
    )

    ok = 0
    partial = 0
    partial_runs: list[tuple[str, str]] = []  # not failures, but worth noting
    failed: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Sequential path: keeps full pipeline output streaming to terminal.
    # This stays the default (--max-concurrent=1) so existing callers see
    # zero behaviour change.
    # ------------------------------------------------------------------
    if args.max_concurrent <= 1:
        sys.path.insert(0, str(agent_utils))
        from run_pipeline import run_full_pipeline  # noqa: WPS433

        for i, (image_path, _planned_dir, _ts) in enumerate(plan, start=1):
            run_ts = time.strftime("%Y%m%d_%H%M%S")
            run_dir = build_run_dir(
                output_root, model_slug, label_slug, image_path, timestamp=run_ts,
            )
            run_dir.mkdir(parents=True, exist_ok=True)

            print("\n" + "=" * 72)
            print(f"[{i}/{len(images)}] Running pipeline: {image_path}")
            print(f"           -> {run_dir}")
            print("=" * 72)

            t0 = time.perf_counter()
            try:
                result = run_full_pipeline(
                    image_path=str(image_path),
                    output_dir=str(run_dir),
                    **pipeline_kwargs,
                )
                elapsed = time.perf_counter() - t0
                status, note = _classify_pipeline_outcome(
                    result, args.end
                )
                if status == "ok":
                    ok += 1
                    print(f"OK in {elapsed:.1f}s  ({run_dir})")
                elif status == "partial":
                    partial += 1
                    partial_runs.append((image_path.name, note))
                    print(
                        f"PARTIAL in {elapsed:.1f}s  ({run_dir})\n"
                        f"          note: {note}"
                    )
                else:
                    failed.append((image_path.name, note or "pipeline reported failure"))
                    print(f"FAILED in {elapsed:.1f}s  ({run_dir})")
                    if args.stop_on_error:
                        return 1
            except Exception as e:  # noqa: BLE001
                elapsed = time.perf_counter() - t0
                failed.append((image_path.name, str(e)))
                print(f"ERROR after {elapsed:.1f}s: {e}  ({run_dir})")
                if args.stop_on_error:
                    return 1

    # ------------------------------------------------------------------
    # Parallel path: ProcessPoolExecutor, one worker process per image.
    # Each worker redirects its (very chatty) pipeline output to
    # <run_dir>/run.log; we only print a one-line summary per image as it
    # finishes. Use ProcessPoolExecutor (not ThreadPool) because:
    #   - pipelines spawn Blender subprocesses (Stage 3) that are easier
    #     to manage and clean up via process isolation
    #   - several internal stages already use ThreadPoolExecutor; nesting
    #     threads inside the same interpreter would amplify GIL contention
    #   - process boundaries protect against state bleed in singleton-ish
    #     modules (Memory caches, llm_client retry counters, etc.)
    # ------------------------------------------------------------------
    else:
        # Pre-compute every image's run_dir + payload UP FRONT so that
        # output directories are created before workers start (avoids two
        # workers racing to mkdir the same parent layer).
        payloads: list[dict] = []
        for image_path, _planned_dir, _ts in plan:
            run_ts = time.strftime("%Y%m%d_%H%M%S")
            time.sleep(0.01)  # ensure distinct timestamps even on fast systems
            run_dir = build_run_dir(
                output_root, model_slug, label_slug, image_path, timestamp=run_ts,
            )
            run_dir.mkdir(parents=True, exist_ok=True)
            payloads.append({
                "image_path": str(image_path),
                "run_dir": str(run_dir),
                "agent_utils": str(agent_utils),
                "pipeline_kwargs": pipeline_kwargs,
            })

        n_workers = min(args.max_concurrent, len(payloads))
        print()
        print("=" * 72)
        print(f"Parallel batch: {len(payloads)} image(s), {n_workers} worker(s)")
        print(f"Per-image logs : <run_dir>/run.log   (use `tail -f` to watch)")
        print("=" * 72)

        done = 0
        t_batch = time.perf_counter()
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            future_to_name: dict = {}
            for p in payloads:
                fut = ex.submit(_run_one_image, p)
                future_to_name[fut] = p["image_path"]

            try:
                for fut in as_completed(future_to_name):
                    done += 1
                    try:
                        r = fut.result()
                    except Exception as e:  # noqa: BLE001
                        # The worker itself returns errors as a dict; an
                        # exception here means pickling/IPC blew up.
                        name = Path(future_to_name[fut]).name
                        failed.append((name, f"worker IPC error: {e}"))
                        print(f"[{done}/{len(payloads)}] IPC-FAIL  {name}: {e}")
                        if args.stop_on_error:
                            for f in future_to_name:
                                f.cancel()
                            break
                        continue

                    status = r.get("status") or ("ok" if r.get("success") else "failed")
                    tag = {
                        "ok": "OK     ",
                        "partial": "PARTIAL",
                        "failed": "FAILED ",
                    }.get(status, "FAILED ")
                    msg = (
                        f"[{done}/{len(payloads)}] {tag}  "
                        f"{r['elapsed']:6.1f}s  {r['image_name']}"
                    )
                    if status == "ok":
                        ok += 1
                        print(msg)
                    elif status == "partial":
                        partial += 1
                        partial_runs.append((r["image_name"], r["error"]))
                        print(f"{msg}\n          note:  {r['error']}")
                        print(f"          log:   {r['log_path']}")
                    else:
                        failed.append((r["image_name"], r["error"]))
                        print(f"{msg}\n          error: {r['error']}")
                        print(f"          log:   {r['log_path']}")
                        if args.stop_on_error:
                            for f in future_to_name:
                                f.cancel()
                            break
            except KeyboardInterrupt:
                print("\n^C received — cancelling pending workers...", file=sys.stderr)
                for f in future_to_name:
                    f.cancel()
                raise

        batch_elapsed = time.perf_counter() - t_batch
        print(f"\n(parallel batch wall-time: {batch_elapsed:.1f}s)")

    # ------------------------------------------------------------------
    # Final summary (shared by both paths)
    # ------------------------------------------------------------------
    # `ok` counts strict full-pipeline successes. `partial` counts runs
    # where only Stage 3 fell short of its score threshold but the rest
    # of the pipeline still produced a renderable script — the user
    # explicitly asked NOT to flag those as batch failures.
    usable = ok + partial
    print("\n" + "=" * 72)
    if partial:
        print(
            f"Batch finished: {usable}/{len(images)} usable  "
            f"({ok} clean + {partial} partial), "
            f"{len(failed)} failed"
        )
    else:
        print(f"Batch finished: {ok}/{len(images)} succeeded")
    print(f"Output bucket : {bucket}")
    if partial_runs:
        print("Partial (Stage 3 below threshold but pipeline completed):")
        for name, reason in partial_runs:
            print(f"  - {name}: {reason}")
    if failed:
        print("Failed:")
        for name, reason in failed:
            print(f"  - {name}: {reason}")
    print("=" * 72)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())


"""
Examples (after the --output-root / --model-tag / --label refactor)
==================================================================

# 1) Default model, bedroom batch (auto image-class subfolder)
python batch_run_pipeline.py \
    --images-dir image_prompt_gen/generated_images/bedroom \
    --label bedroom --parallel 16

# 2) Claude Opus on kitchens
python batch_run_pipeline.py \
    --images-dir image_prompt_gen/generated_images/kitchen \
    --label kitchen --parallel 16 \
    --model "claude-opus-4-6" \
    --base-url "https://esapi.top/v1" \
    --api-key "<api-key>"

# 3) Custom model-tag (override slug) + custom output-root
python batch_run_pipeline.py \
    --images-dir image_prompt_gen/generated_images/2026_4_23 \
    --label 2026_4_23 --parallel 16 \
    --model "[official]gemini-3.1-pro-preview" \
    --base-url "https://bitexingai.com/v1" \
    --api-key "<api-key>" \
    --model-tag gemini31pro \
    --output-root /Volumes/Disk1/scenegen_runs

# 4) Dry-run to preview the planned directory tree without running anything
python batch_run_pipeline.py \
    --images-dir image_prompt_gen/generated_images/bedroom \
    --label bedroom --model-tag gemini31flash --dry-run

# 5) Parallel batch (4 images at the same time, each writes its own run.log)
python batch_run_pipeline.py \
    --images-dir image_prompt_gen/generated_images/bedroom \
    --label bedroom --max-concurrent 4
# Then in another terminal:
#   tail -f agent_utils/pipeline_output/default/bedroom/run_*/run.log

python batch_run_pipeline.py \
    --images-dir /Users/yangyixuan/generated_images/simple_5 \
    --label simple \
    --model-tag gemini3-flash \
    --parallel 16 \
    --output-root /Users/yangyixuan/CAR3D_output

python /home/pjlab/SceneAgent/Code_as_3D_Room/batch_run_pipeline.py \
    --images-dir /home/pjlab/SceneAgent/benchmark_input/test\
    --output-root /home/pjlab/SceneAgent/CAR3D_output \
    --parallel 16 \
    --label test --model-tag gemini3-flash \
    --max-concurrent 1   

python /home/pjlab/SceneAgent/Code_as_3D_Room/batch_run_pipeline.py \
    --images-dir /home/pjlab/SceneAgent/benchmark_input/hard \
    --output-root /home/pjlab/SceneAgent/CAR3D_output \
    --parallel 16 \
    --label hard --model-tag gemini3-flash \
    --max-concurrent 5  


python /home/pjlab/SceneAgent/Code_as_3D_Room/batch_run_pipeline.py \
    --images-dir /home/pjlab/SceneAgent/benchmark_input/special_10 \
    --output-root /home/pjlab/SceneAgent/CAR3D_output \

    --parallel 16 \
    --label special --model-tag gemini3-flash \
    --max-concurrent 1    

tail -f /Users/yangyixuan/CAR3D_output/gemini3-flash/simple/run_*/run.log
"""
