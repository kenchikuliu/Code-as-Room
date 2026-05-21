# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Operating Principles
1. Codex is watching you work.
2. In Plan mode, if the ask-codex skill is available, you must ask codex's opinion before exiting plan mode and handing it back to the user for review.
3. Do not write code in any language other than English.
4. Before writing any code, describe your approach and wait for approval.
5. If the requirements I give are ambiguous, ask clarifying questions before writing code.
6. After finishing any code, list edge cases and suggest test cases that cover them.
7. If a task requires modifying more than 3 files, stop and split it into smaller tasks first.
8. When a bug appears, write a test that reproduces it first, then fix it until the test passes.
9. Every time I correct you, reflect on what you did wrong and make a plan to never repeat it.
10. Do not write any code in plan mode.

## Project Overview

SceneGen Agent is a multi-stage AI-driven pipeline that automatically generates renderable 3D Blender scenes from a single indoor top-down view (floor plan). The entire process uses LLM for semantic understanding and code generation to achieve end-to-end scene reconstruction.

## Core Architecture

### Pipeline Flow (9 Active Stages)

**unified_pipeline.py supports Stage 1-4 + 7-11 + Stage_small_objects (Stage 5-6 deprecated):**

1. **Stage 1: Spatial Semantic Analysis**
   - Identify functional areas (living room, bedroom, kitchen, etc.)
   - Extract object list (furniture, decorations)
   - Analyze architectural features (walls, doors, windows)

2. **Stage 2: Scene Graph Construction**
   - Build spatial relationship graph between objects
   - Direction/distance/alignment relationships

3. **Stage 3: Blender Code Generation**
   - Generate Blender Python script
   - Render top-down view and compare with original image
   - LLM feedback iterative optimization

4. **Stage 4: Wall-Mounted Decorations ONLY** (narrowed scope, 2026-04 refactor)
   - Appends paintings / mirrors / wall clocks / wall shelves / wall sconces /
     wall-mounted TVs / pegboards / curtain rods … on top of Stage 3 code
   - Strictly rejects surface-bound items (table-top, shelf, seat, floor);
     those are handled by `Stage_small_objects` after Stage 8
   - Automatically cleans direction-marker arrows

**[Stage 5-6: Deprecated - Old layout optimization approach using IncrementalLayoutEngine]**

7. **Stage 7: Object Description Generation (stage_describe)**
   - Parse position/size/rotation of each object from code
   - Analyze object type, appearance, material, color based on original image
   - Analyze overall room style

8. **Stage 8: Detailed Geometry Generation (stage_geometry)**
   - Generate detailed composite geometry for each object (box/cylinder/sphere/cone)
   - Incremental save, supports resume from checkpoint
   - Generate integrated code (replace simple bbox with detailed geometry)

8.5. **Stage_small_objects: Surface-Driven Small Objects (stage_small_objects)**
   - Rule-based plane discovery on `DETAILED_GEOMETRY` from Stage 8
     (table/cabinet tops, internal shelves for open furniture, chair/sofa seats)
   - Per-parent LLM call (with reference image + room style + Stage 1/2 hints)
     decides which small objects to place on each plane, in plane-local UV
   - Appends `create_box` / `create_cylinder` calls for each item on top of the
     Stage 8 Blender script (bbox-only geometry for now)
   - Runs automatically when `--start <= 8` and `--end >= 9`

9. **Stage 9: Per-Part Material & Texture Generation (stage_material)**
   - Parse DETAILED_GEOMETRY from Stage 8 to identify each object's parts
   - Generate per-part PBR materials (different parts get different materials)
   - Generate enhanced floor material (with procedural patterns/textures)
   - Generate enhanced wall material (with bump/roughness)
   - Output enhanced Blender code with PART_MATERIALS dictionary

10. **Stage 10: Real Texture Generation (stage_texture)**
    - Generate real texture PNGs for floor / walls / wall art via NanoBanana (Gemini Image)
    - Rewrite the Blender code from Stage 9 to load those textures via `ShaderNodeTexImage`
    - Controls wall visual intensity (`subtle` / `bold` / `mural_like`) and wall art full-bleed prompts
    - Does NOT add lighting (that is Stage 11's responsibility)

11. **Stage 11: Lighting & Render Settings (stage_render)**
    - Parse lighting information from image (light source type/color temperature/intensity)
    - Add Cycles render engine settings (samples, denoising, color management)
    - Create light sources (Area, Point, Sun, Spot) and world environment
    - Does NOT handle materials (that is Stage 9's responsibility)

### Key Components

- **Memory System** (`agent_utils/memory.py`): Cross-stage data transfer, automatically saves intermediate results
- **LLMClient** (`agent_utils/llm_client.py`): LLM call wrapper, supports multiple model switching
- **PromptManager** (`agent_utils/stage3/core.py`): Manages Prompt templates in `agent_prompt/` directory
- **Stage Runners**: Each Stage has independent Runner class (e.g., `Stage1Runner`, `Stage3Runner`)

### Directory Structure

```
agent_input/          # Input images
agent_prompt/         # Prompt templates for each Stage
agent_utils/          # Core code
  ├── unified_pipeline.py      # 🔥 Main entry (Stage 1-4, 7-11)
  ├── stage_describe.py        # Stage 7 implementation
  ├── stage_geometry.py        # Stage 8 implementation
  ├── stage_small_objects.py   # Stage 8.5 implementation (surface-driven small objects)
  ├── stage_material.py        # Stage 9 implementation
  ├── stage_texture.py         # Stage 10 implementation
  ├── stage_render.py          # Stage 11 implementation
  ├── memory.py                # Memory system
  ├── llm_client.py            # LLM client
  ├── stage1/                  # Stage1 implementation
  ├── stage2/                  # Stage2 implementation
  ├── stage3/                  # Stage3 implementation (includes core.py)
  ├── stage4/                  # Stage4 implementation
  ├── stage5/                  # [Deprecated] Old layout optimization
  ├── stage6/                  # [Deprecated] Old IncrementalLayoutEngine
  └── pipeline_output/         # Output directory
      ├── stage1/
      ├── stage2/
      ├── stage3/
      ├── stage4/
      ├── stage_describe/      # Stage 7 output
      ├── stage_geometry/      # Stage 8 output
      ├── stage_small_objects/ # Stage 8.5 output (planes.json, small_objects.json, *_output.py)
      ├── stage_material/      # Stage 9 output
      ├── stage_texture/       # Stage 10 output
      └── stage_render/        # Stage 11 output
```

## Common Commands

### Run Complete Pipeline (Recommended)

```bash
cd agent_utils

# 🔥 One-click run complete Pipeline (Stage 1-4 + 7-11)
python unified_pipeline.py --image ../agent_input/your_image.png

# Final output file:
# - pipeline_output/stage_render/render_output.py (final renderable script, now includes real textures from Stage 10)
```

### Run by Stages

```bash
# Run only Stage 1-4 (basic scene generation)
python unified_pipeline.py --image ../agent_input/your_image.png --end 4

# Run only Stage 7-11 (object description + geometry + material + texture + render)
python unified_pipeline.py --image ../agent_input/your_image.png --start 7

# Start from Stage 3 (with Stage1/2 results already available)
python unified_pipeline.py --image input.png --start 3 --end 11
```

### Stage 3 Configuration Options

```bash
# Stage3 no iteration (single generation)
python unified_pipeline.py --image input.png --no-iterate

# Use OpenAI model for Stage3
python unified_pipeline.py --image input.png --stage3-model gpt-4o
python unified_pipeline.py --image input.png --stage3-model gpt-5.1-codex-max
```

### Memory Management

```bash
# View Memory status
python unified_pipeline.py --status

# Clear all Memory
python unified_pipeline.py --clear-memory

# Clear specific Stage Memory
python unified_pipeline.py --clear-stage stage3
```

### Use Generated Scripts in Blender

```bash
# 🌟 Use final render script (recommended - includes detailed geometry + materials + lighting)
/Applications/Blender.app/Contents/MacOS/Blender --python pipeline_output/stage_render/render_output.py

# Use material script (detailed geometry + per-part PBR materials, no lighting)
/Applications/Blender.app/Contents/MacOS/Blender --python pipeline_output/stage_material/material_output.py

# Use detailed geometry script (no materials/lighting)
/Applications/Blender.app/Contents/MacOS/Blender --python pipeline_output/stage_geometry/geometry_output.py

# Use basic scene script (simple bbox)
/Applications/Blender.app/Contents/MacOS/Blender --python pipeline_output/stage4/stage4_output.py
```

## Development Notes

### Complete Workflow Explanation

**Recommended workflow (Stage 5-6 deprecated):**

```
Stage 1-4: Basic scene generation
  ↓ [Memory: stage1, stage2, stage3, stage4]
[Stage 5-6: DEPRECATED - Old IncrementalLayoutEngine approach]
  ↓
Stage 7: Object description generation (stage_describe)
  - Reads: stage4 or stage3 (scene code)
  - Reads: stage1 (image path)
  ↓ [Memory: stage_describe]
Stage 8: Detailed geometry generation (stage_geometry)
  - Reads: stage_describe (object description JSON)
  ↓ [Memory: stage_geometry]
Stage 8.5: Surface-driven small objects (stage_small_objects)
  - Reads: stage_geometry (geometry_progress.json for DETAILED_GEOMETRY,
    geometry_output.py as base code) ⭐ Priority
  - Reads: stage_describe (object type tags for plane whitelisting)
  - Reads: stage1 (image path, object_hierarchy as weak hints for LLM)
  - Appends small-object bbox calls to Stage 8 base code
  ↓ [Memory: stage_small_objects]
Stage 9: Per-part material & texture generation (stage_material)
  - Reads: stage_small_objects (code with small objects) ⭐ Priority
  - Fallback: stage_geometry (geometry code)
  - Reads: stage_describe (object descriptions for context)
  - Reads: stage1 (image path)
  ↓ [Memory: stage_material]
Stage 10: Real texture generation (stage_texture)
  - Reads: stage_material (code with materials) ⭐ Priority
  - Reads: stage_describe (wall art objects, room_style)
  - Reads: stage1 (image path)
  - Generates real floor/wall/wall-art PNGs via NanoBanana and injects them
  ↓ [Memory: stage_texture]
Stage 11: Lighting & render settings (stage_render)
  - Reads: stage_texture (code with real textures) ⭐ Priority
  - Fallback: stage_material / stage_geometry / stage4 / stage3
  - Reads: stage1 (image path)
  - ONLY adds lighting + render config, does NOT touch materials
  ↓ [Memory: stage_render]

Final output: pipeline_output/stage_render/render_output.py
```

### Why Stage 5-6 are Deprecated

- **Stage 5-6** used an old approach with IncrementalLayoutEngine for collision detection and layout optimization
- **Stage 7-11** is the new approach that generates detailed geometry, per-part materials, real textures, and lighting directly
- The two approaches are incompatible - use Stage 7-11 for better results

### Memory Naming Convention

- **Stage 1-4**: Use `stage1`, `stage2`, `stage3`, `stage4`
- **Stage 7**: Use `stage_describe` (in Memory)
- **Stage 8**: Use `stage_geometry` (in Memory)
- **Stage 8.5**: Use `stage_small_objects` (in Memory)
- **Stage 9**: Use `stage_material` (in Memory)
- **Stage 10**: Use `stage_texture` (in Memory)
- **Stage 11**: Use `stage_render` (in Memory)

### LLM Configuration

- Default model: `gemini-3-flash-preview-thinking`
- Supports OpenAI models (gpt-4o, gpt-5.1-codex-max, etc.)
- OpenAI models require setting `OPENAI_API_KEY` environment variable
- Model configuration in `agent_utils/stage3/core.py` LLMClient class

### Memory System Usage

- Memory data stored in `agent_utils/agent_memory.jsonl`
- Each stage automatically reads results from previous stages
- If generation quality is poor, recommend clearing Memory and re-running
- Memory supports querying by stage/type/tags

### Dependency Validation

Each Stage automatically validates previous dependencies:
- **Stage 7** requires: stage4 or stage3 (at least one)
- **Stage 8** requires: stage_describe
- **Stage 8.5 (stage_small_objects)** requires: stage_geometry (for
  geometry_progress.json DETAILED_GEOMETRY and geometry_output.py base code);
  stage_describe (for object type tags); stage1 (image + weak hints)
- **Stage 9** requires: stage_small_objects (priority) or stage_geometry or
  stage4/stage3 (fallback)
- **Stage 10** requires: stage_material (priority) or stage_geometry or stage4/stage3 (fallback); generates real texture PNGs
- **Stage 11** requires: stage_texture (priority) or stage_material / stage_geometry / stage4 / stage3 (fallback); only adds lighting

If dependencies are missing, clear error messages will be displayed.

### Prompt Templates

- All Prompt templates located in `agent_prompt/` directory
- Stage1: `Stage1_task`
- Stage2: `Stage2_task`
- Stage3: `Stage3_generate_system`, `Stage3_generate_user`, `Stage3_fix_system`, etc.
- Stage4: `Stage4_task` (wall-mounted-only, post-refactor)
- Stage_small_objects: `Stage_small_task`
- Stage 7-11: Most prompts defined inline in respective Python files

### Incremental Generation Mechanism

- `stage_geometry.py` supports per-object generation, saves immediately after each object to `geometry_progress.json`
- Use `--resume` to skip already generated objects
- Use `--code-only` to only regenerate integrated code without calling LLM

### Code Chunked Writing

- When writing large Python files, execute in chunks, no more than 300 lines or 12000 characters per chunk
- Especially when generating Blender scripts, recommend writing main structure first, then appending details

### Debugging and Logging

- Raw LLM output for each Stage saved in `pipeline_output/stageX/*_raw.txt`
- Use `--verbose` parameter to view detailed logs
- Stage3 iteration process saves `stage3_initial.py`, `stage3_iter1.py`, etc. intermediate versions

## Common Issues

1. **Blender path error**: Use `--blender` to specify correct path
2. **Image too large causing API error**: Use `--image-target-kb` to adjust compression target size
3. **Want to re-run a specific Stage**: Use `--clear-stage` to clear that Stage's Memory
4. **Geometry generation interrupted**: unified_pipeline handles automatically, or run `python stage_geometry.py --resume` separately
5. **Missing dependency error**: Ensure Stages run in order, or use `--status` to check Memory status
6. **Stage 11 not using detailed geometry**: Check if Stage 8 ran successfully, check if `stage_geometry` data exists in Memory
7. **Stage 5-6 errors**: These stages are deprecated, use Stage 7-11 instead
8. **Stage 11 not using per-part materials**: Check if Stage 9 ran successfully, check if `stage_material` data exists in Memory
9. **Stage 11 not using real textures**: Check if Stage 10 ran successfully, check if `stage_texture` data exists in Memory
