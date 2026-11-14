import io
import tracemalloc
from PIL import Image

from utils.security import validate_image_payload
from utils.processor import quantize_and_preprocess_image
from utils.tracer import trace_image_to_svg
from utils.sanitizer import sanitize_svg_content
from utils.svg_parser import parse_and_normalize_svg
from utils.ppt_builder import build_presentation_from_svg


def create_high_res_png_bytes(width=3000, height=3000) -> bytes:
    """Helper to generate a high-resolution 3000x3000px PNG image in memory."""
    img = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_high_resolution_memory_leak_and_peak():
    """
    Monitors peak RAM consumption using tracemalloc during the quantization 
    and vector tracing of a large 3000x3000px PNG, and asserts that memory 
    allocation returns cleanly after execution without lingering leaks.
    """
    file_bytes = create_high_res_png_bytes(3000, 3000)

    # Start tracemalloc memory profiling
    tracemalloc.start()
    
    # Take baseline snapshot
    _, baseline_peak = tracemalloc.get_traced_memory()

    try:
        # Execute the heavy processing pipeline
        img = validate_image_payload(file_bytes)
        with img:
            preprocessed_img = quantize_and_preprocess_image(img)
        
        svg_content = trace_image_to_svg(preprocessed_img)
        sanitize_svg_content(svg_content)
        parsed_svg_data = parse_and_normalize_svg(svg_content)
        build_presentation_from_svg(parsed_svg_data, output_path=None)

        # Measure peak memory during execution
        current, peak = tracemalloc.get_traced_memory()
        
        peak_mb = peak / (1024 * 1024)
        print(f"\n[Memory Profiling - 3000x3000px PNG]")
        print(f" • Peak RAM Consumed: {peak_mb:.2f} MB")

        # Assert peak memory remains well within serverless container bounds (e.g., < 256 MB)
        assert peak_mb < 256.0, f"Memory spike detected: Peak RAM reached {peak_mb:.2f} MB"

    finally:
        tracemalloc.stop()

    # Verify memory is released after tracemalloc stops and objects go out of scope
    tracemalloc.start()
    _, post_cleanup_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    post_cleanup_mb = post_cleanup_peak / (1024 * 1024)
    assert post_cleanup_mb < 50.0, (
        f"Possible memory leak detected: Post-cleanup baseline remains elevated at {post_cleanup_mb:.2f} MB"
    )