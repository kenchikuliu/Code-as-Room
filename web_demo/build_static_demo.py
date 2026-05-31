from __future__ import annotations

import base64
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "repro_outputs" / "gpt55_stage1_4" / "run_20260530_141733_example1"
GLB_PATH = RUN_DIR / "optimized_scene" / "scene.glb"
PREVIEW_PATH = RUN_DIR / "optimized_scene" / "preview.png"
OUT_PATH = Path(__file__).resolve().parent / "index.html"
MODEL_VIEWER_PATH = Path(__file__).resolve().parent / "model-viewer-3.5.0.min.js"
SAMPLE_DIR = Path(__file__).resolve().parent / "sample_models"
TEXTURED_DIR = Path(__file__).resolve().parent / "textured_models"
IMAGE2_DIR = Path(__file__).resolve().parent / "image2_outputs"
IMAGE2_MAPPED_DIR = Path(__file__).resolve().parent / "image2_mapped_models"


SAMPLE_DEFS = [
    {
        "title": "Example 1 · Image2 Mapped Bedroom",
        "badge": "Render-mapped GLB",
        "objects": "300",
        "meshes": "250",
        "textures": "1 atlas",
        "orbit": "0deg 0deg 11m",
        "fov": "30deg",
        "exposure": "1.0",
        "shadow": "0.65",
        "spin": True,
        "sub": "Image2 map",
        "model": IMAGE2_MAPPED_DIR / "scene_image2_mapped.glb",
        "preview": IMAGE2_DIR / "final_interior_render.png",
    },
    {
        "title": "Example 2 · Studio Apartment",
        "badge": "Textured GLB",
        "objects": "11",
        "meshes": "11",
        "textures": "7",
        "orbit": "40deg 56deg 8.2m",
        "fov": "33deg",
        "exposure": "1.0",
        "shadow": "0.75",
        "spin": False,
        "sub": "Studio",
        "model": TEXTURED_DIR / "sample_2_studio_textured.glb",
        "preview": SAMPLE_DIR / "preview_2_studio.png",
    },
    {
        "title": "Example 3 · L Office",
        "badge": "Textured GLB",
        "objects": "12",
        "meshes": "12",
        "textures": "4",
        "orbit": "-35deg 58deg 9m",
        "fov": "32deg",
        "exposure": "0.98",
        "shadow": "0.8",
        "spin": False,
        "sub": "Office",
        "model": TEXTURED_DIR / "sample_3_office_textured.glb",
        "preview": SAMPLE_DIR / "preview_3_office.png",
    },
    {
        "title": "Example 4 · Retail Loft",
        "badge": "Textured GLB",
        "objects": "11",
        "meshes": "11",
        "textures": "5",
        "orbit": "25deg 52deg 8.8m",
        "fov": "34deg",
        "exposure": "1.08",
        "shadow": "0.62",
        "spin": True,
        "sub": "Retail",
        "model": TEXTURED_DIR / "sample_4_retail_textured.glb",
        "preview": SAMPLE_DIR / "preview_4_retail.png",
    },
    {
        "title": "Example 5 · Kitchen Dining",
        "badge": "Textured GLB",
        "objects": "12",
        "meshes": "12",
        "textures": "5",
        "orbit": "70deg 50deg 8.4m",
        "fov": "33deg",
        "exposure": "1.02",
        "shadow": "0.72",
        "spin": False,
        "sub": "Kitchen",
        "model": TEXTURED_DIR / "sample_5_kitchen_textured.glb",
        "preview": SAMPLE_DIR / "preview_5_kitchen.png",
    },
    {
        "title": "Example 6 · Compact Suite",
        "badge": "Textured GLB",
        "objects": "12",
        "meshes": "12",
        "textures": "7",
        "orbit": "-75deg 54deg 7.6m",
        "fov": "34deg",
        "exposure": "1.04",
        "shadow": "0.7",
        "spin": True,
        "sub": "Compact",
        "model": TEXTURED_DIR / "sample_6_compact_textured.glb",
        "preview": SAMPLE_DIR / "preview_6_compact.png",
    },
]


def data_url(path: Path, mime: str) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def main() -> None:
    if not MODEL_VIEWER_PATH.is_file():
        raise FileNotFoundError(MODEL_VIEWER_PATH)
    for sample in SAMPLE_DEFS:
        if not sample["model"].is_file():
            raise FileNotFoundError(sample["model"])
        if not sample["preview"].is_file():
            raise FileNotFoundError(sample["preview"])

    samples = []
    for sample in SAMPLE_DEFS:
        item = {
            key: value
            for key, value in sample.items()
            if key not in {"model", "preview"}
        }
        item["fileName"] = sample["model"].name
        item["modelUrl"] = data_url(sample["model"], "model/gltf-binary")
        item["previewUrl"] = data_url(sample["preview"], "image/png")
        samples.append(item)

    samples_json = json.dumps(samples, ensure_ascii=False)
    first_model_url = samples[0]["modelUrl"]
    first_preview_url = samples[0]["previewUrl"]
    model_viewer_url = data_url(MODEL_VIEWER_PATH, "text/javascript")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Top-down Room to 3D GLB</title>
  <script type="module" src="{model_viewer_url}"></script>
  <style>
    :root {{
      --bg: #0f1115;
      --panel: rgba(24, 27, 34, 0.92);
      --panel2: rgba(244, 245, 247, 0.96);
      --line: rgba(255,255,255,0.14);
      --text: #f5f7fb;
      --muted: #aeb6c4;
      --accent: #46a6ff;
      --green: #4ec98d;
      --amber: #d7a848;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    .app {{
      min-height: 100vh;
      display: grid;
      grid-template-rows: 56px minmax(0, 1fr) 72px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0)),
        #0f1115;
    }}

    header {{
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(15,17,21,0.92);
      backdrop-filter: blur(16px);
      z-index: 3;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      font-size: 15px;
      font-weight: 650;
      letter-spacing: 0;
      white-space: nowrap;
    }}

    .mark {{
      width: 24px;
      height: 24px;
      border: 1px solid rgba(255,255,255,0.18);
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: var(--accent);
      background: rgba(70,166,255,0.09);
    }}

    .actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .upload {{
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      height: 34px;
      padding: 0 12px;
      border: 1px solid rgba(255,255,255,0.18);
      border-radius: 8px;
      background: rgba(255,255,255,0.08);
      color: var(--text);
      font-size: 13px;
      cursor: pointer;
      user-select: none;
    }}

    .upload svg {{
      width: 16px;
      height: 16px;
    }}

    .upload input {{
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
    }}

    .viewport {{
      position: relative;
      min-height: 0;
      overflow: hidden;
    }}

    model-viewer {{
      width: 100%;
      height: 100%;
      min-height: calc(100vh - 128px);
      background-color: #0f1115;
      --poster-color: #0f1115;
    }}

    .side {{
      position: absolute;
      left: 18px;
      top: 18px;
      width: min(320px, calc(100vw - 36px));
      display: grid;
      gap: 10px;
      pointer-events: none;
    }}

    .sample-info,
    .upload-preview {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 45px rgba(0,0,0,0.26);
      pointer-events: auto;
    }}

    .sample-info {{
      padding: 12px;
      display: grid;
      gap: 8px;
    }}

    .title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}

    .title-row strong {{
      font-size: 13px;
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .badge {{
      height: 22px;
      padding: 0 8px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(78,201,141,0.28);
      color: #bdf6d7;
      background: rgba(78,201,141,0.12);
      font-size: 12px;
      white-space: nowrap;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}

    .metric {{
      padding: 8px;
      min-height: 54px;
      border-radius: 7px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.05);
    }}

    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.2;
      margin-bottom: 6px;
    }}

    .metric b {{
      display: block;
      font-size: 14px;
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .upload-preview {{
      display: none;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 10px;
      padding: 10px;
      align-items: center;
    }}

    .upload-preview.active {{
      display: grid;
    }}

    .upload-preview img {{
      width: 82px;
      height: 62px;
      object-fit: cover;
      border-radius: 6px;
      background: #20242c;
    }}

    .upload-preview strong {{
      display: block;
      font-size: 12px;
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .upload-preview span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}

    .tools {{
      position: absolute;
      right: 18px;
      top: 18px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      z-index: 2;
    }}

    .icon-btn {{
      width: 38px;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--text);
      display: grid;
      place-items: center;
      cursor: pointer;
    }}

    .icon-btn svg {{
      width: 17px;
      height: 17px;
    }}

    footer {{
      height: 72px;
      border-top: 1px solid var(--line);
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0 18px;
      background: rgba(15,17,21,0.94);
      z-index: 3;
      overflow-x: auto;
    }}

    .tab {{
      min-width: 132px;
      height: 46px;
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 8px;
      background: rgba(255,255,255,0.05);
      color: var(--text);
      display: grid;
      align-content: center;
      gap: 2px;
      padding: 0 12px;
      cursor: pointer;
      text-align: left;
      flex: 0 0 auto;
    }}

    .tab.active {{
      border-color: rgba(70,166,255,0.7);
      background: rgba(70,166,255,0.16);
    }}

    .tab b {{
      font-size: 13px;
      font-weight: 650;
      line-height: 1.1;
    }}

    .tab span {{
      font-size: 11px;
      color: var(--muted);
      line-height: 1.1;
    }}

    .status {{
      margin-left: auto;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      padding-left: 14px;
    }}

    .fallback {{
      position: absolute;
      inset: 0;
      display: none;
      place-items: center;
      background: #0f1115;
      z-index: 1;
    }}

    .fallback img {{
      width: min(84vw, 920px);
      max-height: 72vh;
      object-fit: contain;
      border-radius: 8px;
      border: 1px solid var(--line);
    }}

    @media (max-width: 760px) {{
      .app {{
        grid-template-rows: 54px minmax(0, 1fr) 86px;
      }}
      header {{
        padding: 0 12px;
      }}
      .brand span {{
        max-width: 160px;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .side {{
        left: 10px;
        top: 10px;
        width: min(280px, calc(100vw - 20px));
      }}
      .tools {{
        right: 10px;
        top: 10px;
      }}
      .metrics {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      footer {{
        height: 86px;
        padding: 8px 10px;
      }}
      .tab {{
        min-width: 106px;
      }}
      .status {{
        display: none;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z" stroke="currentColor" stroke-width="1.7"/>
            <path d="M12 12 4.6 7.8M12 12l7.4-4.2M12 12v8.4" stroke="currentColor" stroke-width="1.5"/>
          </svg>
        </div>
        <span>Code-as-Room GLB Viewer</span>
      </div>
      <div class="actions">
        <label class="upload" title="上传俯视图">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 16V4m0 0 4.5 4.5M12 4 7.5 8.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M5 16.5V19a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          上传图片
          <input id="imageInput" type="file" accept="image/*">
        </label>
      </div>
    </header>

    <main class="viewport">
      <model-viewer id="viewer"
        src="{first_model_url}"
        poster="{first_preview_url}"
        camera-controls
        touch-action="pan-y"
        interaction-prompt="none"
        shadow-intensity="0.65"
        exposure="0.92"
        environment-image="neutral"
        camera-orbit="0deg 0deg 11m"
        field-of-view="30deg"
        auto-rotate
        auto-rotate-delay="1800"
        rotation-per-second="8deg"
        ar-status="not-presenting">
      </model-viewer>

      <div class="fallback" id="fallback">
        <img id="fallbackImage" src="{first_preview_url}" alt="3D scene preview">
      </div>

      <section class="side">
        <div class="sample-info">
          <div class="title-row">
            <strong id="sampleTitle">Example 1 · Bedroom Suite</strong>
            <span class="badge" id="qualityBadge">GLB verified</span>
          </div>
          <div class="metrics">
            <div class="metric"><span>Objects</span><b id="objectsMetric">300</b></div>
            <div class="metric"><span>Meshes</span><b id="meshesMetric">250</b></div>
            <div class="metric"><span>Textures</span><b id="texturesMetric">6</b></div>
          </div>
        </div>

        <div class="upload-preview" id="uploadPreview">
          <img id="uploadedImage" alt="Uploaded room image">
          <div>
            <strong id="uploadedName">uploaded image</strong>
            <span id="uploadedMeta">ready</span>
          </div>
        </div>
      </section>

      <div class="tools">
        <button class="icon-btn" id="topBtn" title="俯视">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 4v16M4 12h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="m8 8 4-4 4 4M8 16l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button class="icon-btn" id="isoBtn" title="等距视角">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" stroke="currentColor" stroke-width="1.7"/>
            <path d="m4.5 7.8 7.5 4.3 7.5-4.3M12 12.1v8.3" stroke="currentColor" stroke-width="1.45"/>
          </svg>
        </button>
        <button class="icon-btn" id="spinBtn" title="自动旋转">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 12a8 8 0 0 1 13.6-5.7L20 8.7M20 4v4.7h-4.7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20 12A8 8 0 0 1 6.4 17.7L4 15.3M4 20v-4.7h4.7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </main>

    <footer id="tabs"></footer>
  </div>

  <script>
    const samples = {samples_json};

    const viewer = document.getElementById("viewer");
    const fallback = document.getElementById("fallback");
    const fallbackImage = document.getElementById("fallbackImage");
    const tabs = document.getElementById("tabs");
    const sampleTitle = document.getElementById("sampleTitle");
    const qualityBadge = document.getElementById("qualityBadge");
    const objectsMetric = document.getElementById("objectsMetric");
    const meshesMetric = document.getElementById("meshesMetric");
    const texturesMetric = document.getElementById("texturesMetric");
    const uploadPreview = document.getElementById("uploadPreview");
    const uploadedImage = document.getElementById("uploadedImage");
    const uploadedName = document.getElementById("uploadedName");
    const uploadedMeta = document.getElementById("uploadedMeta");
    let active = 0;

    function setSample(index) {{
      active = index;
      const s = samples[index];
      sampleTitle.textContent = s.title;
      qualityBadge.textContent = s.badge;
      objectsMetric.textContent = s.objects;
      meshesMetric.textContent = s.meshes;
      texturesMetric.textContent = s.textures;
      const sameModel = viewer.src === s.modelUrl;
      viewer.src = s.modelUrl;
      viewer.poster = s.previewUrl;
      fallbackImage.src = s.previewUrl;
      viewer.cameraOrbit = s.orbit;
      viewer.fieldOfView = s.fov;
      viewer.exposure = s.exposure;
      viewer.shadowIntensity = s.shadow;
      viewer.autoRotate = s.spin;
      status.textContent = sameModel && viewer.loaded ? `${{s.fileName}} · loaded` : `${{s.fileName}} · loading`;
      document.querySelectorAll(".tab").forEach((tab, i) => {{
        tab.classList.toggle("active", i === index);
      }});
    }}

    samples.forEach((sample, i) => {{
      const btn = document.createElement("button");
      btn.className = "tab";
      btn.innerHTML = `<b>${{i + 1}} · ${{sample.title.split("·")[1].trim()}}</b><span>${{sample.sub}}</span>`;
      btn.addEventListener("click", () => setSample(i));
      tabs.appendChild(btn);
    }});

    const status = document.createElement("div");
    status.className = "status";
    status.textContent = `${{samples[0].fileName}} · file-ready`;
    tabs.appendChild(status);

    document.getElementById("topBtn").addEventListener("click", () => {{
      viewer.cameraOrbit = "0deg 0deg 11m";
      viewer.fieldOfView = "30deg";
      viewer.autoRotate = false;
      viewer.jumpCameraToGoal();
    }});

    document.getElementById("isoBtn").addEventListener("click", () => {{
      viewer.cameraOrbit = "42deg 58deg 10m";
      viewer.fieldOfView = "32deg";
      viewer.autoRotate = false;
      viewer.jumpCameraToGoal();
    }});

    document.getElementById("spinBtn").addEventListener("click", () => {{
      viewer.autoRotate = !viewer.autoRotate;
    }});

    document.getElementById("imageInput").addEventListener("change", (event) => {{
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      uploadedImage.src = url;
      uploadedName.textContent = file.name;
      uploadedMeta.textContent = `${{Math.round(file.size / 1024)}} KB`;
      uploadPreview.classList.add("active");
      setSample(0);
      status.textContent = "uploaded · preview linked";
    }});

    viewer.addEventListener("error", () => {{
      fallback.style.display = "grid";
      status.textContent = `${{samples[active].fileName}} · preview fallback`;
    }});

    viewer.addEventListener("load", () => {{
      fallback.style.display = "none";
      status.textContent = `${{samples[active].fileName}} · loaded`;
    }});

    setSample(0);
  </script>
</body>
</html>
"""

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Size: {OUT_PATH.stat().st_size / (1024 * 1024):.1f} MB")


if __name__ == "__main__":
    main()
