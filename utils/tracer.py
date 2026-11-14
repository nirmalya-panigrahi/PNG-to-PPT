import inspect
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
    Supports multiple installed vtracer signatures across versions.
    """
    input_tmp_path = None
    output_tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_in:
            input_tmp_path = f_in.name
            img.save(input_tmp_path, format="PNG")

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f_out:
            output_tmp_path = f_out.name

        tracer_kwargs = dict(
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=4,
            color_precision=6,
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
        )

        func = vtracer.convert_image_to_svg_py
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        if "input_path" in param_names and "output_path" in param_names:
            func(input_path=input_tmp_path, output_path=output_tmp_path, **tracer_kwargs)
        elif "input_file" in param_names and "output_file" in param_names:
            func(input_file=input_tmp_path, output_file=output_tmp_path, **tracer_kwargs)
        else:
            func(input_tmp_path, output_tmp_path, **tracer_kwargs)

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
        raise TracerExecutionError(f"Native vectorization engine error: {str(e)}") from e

    finally:
        for path in [input_tmp_path, output_tmp_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
