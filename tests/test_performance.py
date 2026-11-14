import time
import io
import pytest
from PIL import Image

from utils.security import validate_image_payload
from utils.processor import quantize_and_preprocess_image
from utils.tracer import trace_image_to_svg
from utils.sanitizer import sanitize_svg_content
from utils.svg_parser import parse_and_normalize_svg
from utils.ppt_builder import build_presentation_from_svg


def create_sample_png_bytes(width=200, height=200) -> bytes:
    """Helper to generate a clean sample PNG image in memory for profiling."""
    img = Image.new("RGBA", (width, height), (37, 99, 235, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pipeline_stage_latencies_and_total_duration():
    """
    Measures execution time across each distinct pipeline stage 
    (Ingestion, Quantization, Tracing, Sanitization/Parsing, PPTX Compilation)
    and asserts that the full end-to-end execution completes within 4.0 seconds.
    """
    file_bytes = create_sample_png_bytes()

    # Stage 1: Ingestion & Security Validation
    t0 = time.perf_counter()
    img = validate_image_payload(file_bytes)
    t_ingestion = time.perf_counter() - t0

    # Stage 2: Color Quantization & Preprocessing
    t0 = time.perf_counter()
    with img:
        preprocessed_img = quantize_and_preprocess_image(img)
    t_quantization = time.perf_counter() - t0

    # Stage 3: Rust-Powered Vector Tracing (vtracer)
    t0 = time.perf_counter()
    svg_content = trace_image_to_svg(preprocessed_img)
    t_tracing = time.perf_counter() - t0

    # Stage 4: XML Sanitization & Path Parsing
    t0 = time.perf_counter()
    sanitize_svg_content(svg_content)
    parsed_svg_data = parse_and_normalize_svg(svg_content)
    t_parsing = time.perf_counter() - t0

    # Stage 5: Presentation Compilation (python-pptx & GroupShape)
    t0 = time.perf_counter()
    build_presentation_from_svg(parsed_svg_data, output_path=None)
    t_compilation = time.perf_counter() - t0

    total_duration = (
        t_ingestion + 
        t_quantization + 
        t_tracing + 
        t_parsing + 
        t_compilation
    )

    # Print profiling breakdown for test logs
    print(f"\n[Performance Profile]")
    print(f" • Ingestion & Validation: {t_ingestion:.4f}s")
    print(f" • Quantization:           {t_quantization:.4f}s")
    print(f" • Vector Tracing:         {t_tracing:.4f}s")
    print(f" • Sanitization & Parsing: {t_parsing:.4f}s")
    print(f" • PPTX Compilation:       {t_compilation:.4f}s")
    print(f" -----------------------------------------")
    print(f" • Total End-to-End:       {total_duration:.4f}s")

    # Assert execution stays comfortably beneath Vercel's strict timeout threshold
    assert total_duration < 4.0, (
        f"Performance regression detected: Pipeline took {total_duration:.2f}s "
        f"(exceeds the 4.0-second limit)."
    )