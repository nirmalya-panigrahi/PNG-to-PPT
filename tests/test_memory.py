import io
import resource
import sys
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


def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS and kilobytes on Linux.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def test_high_resolution_peak_memory():
    """
    Runs the whole pipeline on a 3000x3000px PNG and checks peak process memory (RSS).
    tracemalloc is not used because it cannot see native (Rust/Pillow) allocations, which
    is where most of the memory goes. Stays well below typical serverless limits.
    """
    file_bytes = create_high_res_png_bytes(3000, 3000)
    before = _peak_rss_mb()

    img = validate_image_payload(file_bytes)
    with img:
        preprocessed_img = quantize_and_preprocess_image(img)

    svg_content = trace_image_to_svg(preprocessed_img)
    sanitize_svg_content(svg_content)
    parsed_svg_data = parse_and_normalize_svg(svg_content)
    build_presentation_from_svg(parsed_svg_data, output_path=None)

    peak_mb = _peak_rss_mb()
    print(f"\n[Memory Profiling - 3000x3000px PNG] peak RSS {peak_mb:.1f} MB (was {before:.1f} MB)")
    assert peak_mb < 1024.0, f"Memory spike detected: peak RSS reached {peak_mb:.1f} MB"
