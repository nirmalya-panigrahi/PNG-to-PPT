<div align="center">

# 🎨⚡ PNG-to-Vector PPTX Converter

### *Turn flat PNG graphics into native, fully editable PowerPoint (`.pptx`) vector slides instantly on Vercel Serverless.*

[![CI Test Suite](https://github.com/nirmalya-panigrahi/PNG-to-PPT/actions/workflows/ci.yml/badge.svg)](https://github.com/nirmalya-panigrahi/PNG-to-PPT/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Vercel Deployment](https://img.shields.io/badge/vercel-serverless-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)
[![Rust Powered](https://img.shields.io/badge/vtracer-Rust%20Engine-DEA584?style=for-the-badge&logo=rust&logoColor=black)](https://github.com/visioncortex/vtracer)
[![License: MIT](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge)](LICENSE)

<br />

[🚀 Live Demo](#) • [✨ Features](#-key-features) • [🏗️ Architecture](#️-how-it-works) • [🛠️ Quick Start](#️-quick-start--local-development) • [🧪 Testing](#-running-the-test-suite)

</div>

---

## ✨ What is This?

Most "PNG to PPTX" tools simply wrap a flat raster image inside a PowerPoint slide container—leaving you unable to recolor shapes, scale without pixelation, or edit individual components. 

**PNG-to-PPT** is built differently. It traces raster images into clean mathematical vector curves (**SVG paths**) using the Rust-powered `vtracer` engine, parses them into native PowerPoint DrawingML custom shapes (`<a:custGeom>`), and packages them into widescreen presentations—all within a zero-leak serverless architecture.

---

## 🚀 Key Features

| Feature | Description |
| :--- | :--- |
| 🦀 **Rust-Powered Vector Tracing** | Leverages `vtracer` for ultra-fast, high-fidelity edge and color region vectorization. |
| 🛡️ **Strict Security Hardening** | Magic-number header checks, payload size caps (4.5 MB), dimension limits (4000×4000px), and strict XML sanitization blocking `<script>` & `<image>` tags. |
| ⚡ **Zero-Leak Serverless Engine** | Guaranteed `try...finally` file unlinking and in-memory `BytesIO` streaming to prevent `/tmp` disk exhaustion and cross-request leaks on Vercel. |
| 🧩 **PowerPoint Lag Prevention** | Automatically wraps hundreds of individual vector path shapes into a single PowerPoint `GroupShape` container (`slide.shapes.add_group_shape()`) to keep the UI buttery smooth. |
| 🎨 **Seamless Vector Colors** | Maps SVG fills directly to `RGBColor` objects and matches border lines (`line.color.rgb`) to eliminate black outline artifacts. |

---

## 🏗️ How It Works

```mermaid
flowchart LR
    A[🖼️ PNG Upload] --> B[🛡️ Magic-Byte & Bounds Check]
    B --> C[🎨 Median Cut Quantization]
    C --> D[🦀 Rust vtracer Engine]
    D --> E[🧹 XML Security Sanitizer]
    E --> F[📐 EMU Coordinate Normalizer]
    F --> G[📊 DrawingML Freeform & GroupShape]
    G --> H[📥 Native .pptx Download]
```

<details>
<summary><b>🔍 Click to expand Pipeline Breakdown</b></summary>
<br />

1. **Ingestion & Validation (`utils/security.py`):** Verifies true PNG magic headers (`\x89PNG\r\n\x1a\n`), enforces the 4.5 MB Vercel payload ceiling, and blocks decompression bombs (>4000×4000px).
2. **Preprocessing (`utils/processor.py`):** Applies Median Cut color quantization and strips alpha channels to optimize vector path boundaries.
3. **Vector Tracing (`utils/tracer.py`):** Invokes `vtracer` to convert flat pixel clusters into smooth cubic Bezier and line segments.
4. **XML Sanitization (`utils/sanitizer.py`):** Parses the raw SVG XML tree to reject any embedded raster `<image>` fallbacks, `<script>` injections, or external `xlink:href` references.
5. **EMU Normalization (`utils/svg_parser.py`):** Translates SVG viewport coordinates into PowerPoint English Metric Units (EMUs) centered on a 16:9 widescreen slide.
6. **PPTX Compilation (`utils/ppt_builder.py`):** Constructs native `<a:custGeom>` shapes via `FreeformBuilder`, styles fills/borders, and bundles everything into a unified `GroupShape`.

</details>

---

## 📂 Repository Architecture

```text
png-to-pptx-converter/
├── .github/
│   └── workflows/
│       └── ci.yml             # 🤖 Automated CI pipeline (pytest across security, perf, e2e)
├── api/
│   └── convert.py             # ⚡ Core Flask serverless entry point with zero-leak cleanup
├── tests/
│   ├── test_security.py       # 🔒 Input hardening & malware rejection tests (Flask test client)
│   ├── test_regressions.py    # 🐛 Tracer prolog, SVG transforms, Bezier/custGeom output
│   ├── test_sanitizer.py      # 🧹 SVG XML security sanitizer tests
│   ├── test_performance.py    # ⏱️ Latency profiling (execution-time guard)
│   ├── test_memory.py         # 🧠 peak-RSS memory test
│   └── test_e2e.py            # ✅ End-to-end binary & <a:custGeom> XML validation
├── utils/
│   ├── security.py            # 🛡️ Magic number validation & size limits
│   ├── processor.py           # 🎨 Median Cut color quantization & alpha preprocessing
│   ├── tracer.py              # 🦀 Rust vtracer wrapper
│   ├── sanitizer.py           # 🧼 XML security filter
│   ├── svg_parser.py          # 📐 Path extraction & EMU coordinate normalization
│   └── ppt_builder.py         # 📊 FreeformBuilder, color styling, & GroupShape engine
├── index.html                 # 🖥️ Root drag-and-drop web UI
├── requirements.txt           # 📦 Pinned Python dependencies
└── vercel.json                # ⚙️ Vercel serverless routing & 10s timeout configuration
```

---

## 🛠️ Quick Start & Local Development

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/nirmalya-panigrahi/PNG-to-PPT.git
cd PNG-to-PPT
```

### 2️⃣ Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Start the Local Server
```bash
python api/convert.py
```
Open your browser and navigate to **`http://localhost:5000`** to test the drag-and-drop interface locally. The server binds to `127.0.0.1` with the Werkzeug debugger **off**; set `FLASK_DEBUG=1` (or `HOST`/`PORT`) only if you need them.

---

## 🧪 Running the Test Suite

This project includes comprehensive unit, security, memory, performance, and end-to-end integration tests:

```bash
# Install test runner dependencies
pip install pytest

# Execute the full test suite
pytest tests/ -v
```

| Test Module | What It Verifies |
| :--- | :--- |
| `test_security.py` | Rejects renamed PHP scripts, corrupted headers, empty/missing files and >4.5 MB payloads with HTTP 400/413. |
| `test_sanitizer.py` | Blocks malicious `<image>`, `<script>`, and external `xlink:href` XML structures. |
| `test_regressions.py` | Guards against: vtracer XML-prolog rejection, ignored `transform`s, flattened curves, lost holes. |
| `test_performance.py` | Enforces end-to-end latency under a **6.0 second** budget on a busy ~800-shape image. |
| `test_memory.py` | Checks peak process memory (RSS) on a 3000×3000px image. |
| `test_e2e.py` | Unzips the compiled `.pptx` archive and verifies `<a:custGeom>` tags in `ppt/slides/slide1.xml`. |

---

## ⚠️ GitHub Pages cannot run the converter

GitHub Pages only serves static files, so it answers the page's `POST /api/convert` with **HTTP 405**. The Python backend must run on Vercel (or locally). To keep the page on GitHub Pages anyway:

1. Deploy the repo to Vercel and set the env var `ALLOWED_ORIGINS=https://<your-user>.github.io`.
2. In `index.html`, set `<meta name="api-base" content="https://<your-app>.vercel.app" />`.

Otherwise, just use the Vercel URL directly (the default same-origin setup needs no configuration).

## 🚢 One-Click Vercel Deployment

1. Fork or push this repository to your **GitHub** account.
2. Log in to your [Vercel Dashboard](https://vercel.com/) and click **Add New → Project**.
3. Import **`PNG-to-PPT`**—Vercel will automatically detect `vercel.json` and serve `index.html` at the root alongside `/api/convert`.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<div align="center">
  <sub>Built with ❤️ using Python, Rust (<code>vtracer</code>), <code>python-pptx</code>, and Vercel Serverless.</sub>
</div>
