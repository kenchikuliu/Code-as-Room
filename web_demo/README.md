# Code-as-Room Web Demo

This folder contains a local, offline-openable GLB viewer prototype.

Open `index.html` directly in a browser. The first sample demonstrates the
image2 render-mapping path:

1. Generate or reuse a polished interior render.
2. Project the render back onto floor and object surfaces.
3. Apply semantic object textures for wood, bedding, upholstery, stone,
   ceramic, and dark furniture, tinted from the room render.
4. Apply separate wall textures with vertical UV mapping.
5. Package the mapped GLB into the local HTML viewer.

To rebuild the static page after changing assets:

```powershell
python web_demo\build_static_demo.py
```

To rerun image2 render mapping, set `APIMART_API_KEY` in the current shell:

```powershell
$env:APIMART_API_KEY="your-apimart-key"
python web_demo\image2_render_and_project.py --require-api
python web_demo\build_static_demo.py
```

Alternatively, run the prompt-based helper so the key stays in that PowerShell
process only:

```powershell
powershell -ExecutionPolicy Bypass -File web_demo\run_image2_with_prompt.ps1
```

## Tripo Object Assets

The next fidelity step is to generate high-quality single-object GLBs first,
then place those assets back into the room and optionally retexture them from
the final room render.

Generate one object asset with Tripo:

```powershell
$env:TRIPO_API_KEY="your-tripo-key"
python web_demo\tripo_object_pipeline.py --asset lounge_armchair
```

Outputs are written under `web_demo/tripo_assets/`, which is ignored by git.
To replace the current low-poly armchair groups with that asset:

```powershell
python web_demo\place_tripo_asset_in_scene.py
```
