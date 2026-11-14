import os
import tempfile
from PIL import Image
import vtracer


class TracerExecutionError(Exception):
    """Raised when the native Rust-powered vtracer engine fails or encounters an error."""
    pass


def trace_image_to_svg(img: Image.Image) -> str:
    """
    Wraps vtracer to convert a preprocessed PIL Image into an SVG string.
    Configured explicitly for clean flat vector output with optimized path precision,
    segment filtering, and hierarchical layering.
    
    Includes robust exception boundaries around native C-extension calls to 
    prevent container crashes or unhandled segmentation faults.
    """
    input_tmp_path = None
    output_tmp_path = None

    try:
        # Vtracer's underlying Python binding reads and writes via disk paths
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_in:
            input_tmp_path = f_in.name
            img.save(input_tmp_path, format="PNG")

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f_out:
            output_tmp_path = f_out.name

        # Invoke vtracer with explicit parameters optimized for flat vector output
        vtracer.convert_image_to_svg_py(
            input_path=input_tmp_path,
            output_path=output_tmp_path,
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=4,         # Discard microscopic noise / speckles below 4px
            color_precision=6,        # Clamped precision for clean color boundaries
            layer_difference=16,      # Gradient layer separation threshold
            corner_threshold=60,      # Corner angle threshold in degrees
            length_threshold=4.0,     # Segment filtering length threshold
            max_iterations=10,
            splice_threshold=45
        )

        # Validate generated SVG output
        if not os.path.exists(output_tmp_path) or os.path.getsize(output_tmp_path) == 0:
            raise TracerExecutionError("Vtracer completed execution but produced an empty SVG output file.")

        with open(output_tmp_path, "r", encoding="utf-8") as f_svg:
            svg_content = f_svg.read()

        if not svg_content.strip().startswith("<svg"):
            raise TracerExecutionError("Generated output is not a valid SVG document structure.")

        return svg_content

    except Exception as e:
        if isinstance(e, TracerExecutionError):
            raise e
        # Catch-all boundary for native C-extension faults or memory exceptions
        raise TracerExecutionError(f"Native vectorization engine error: {str(e)}") from e

    finally:
        # Ensure temporary files are always purged to prevent disk bloat
        for path in [input_tmp_path, output_tmp_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass