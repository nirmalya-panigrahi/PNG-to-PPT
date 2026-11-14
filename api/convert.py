import io
import os
from flask import Flask, request, jsonify, send_file

from utils.security import validate_image_payload, SecurityValidationError
from utils.processor import quantize_and_preprocess_image
from utils.tracer import trace_image_to_svg, TracerExecutionError
from utils.sanitizer import sanitize_svg_content, SVGSecurityError
from utils.svg_parser import parse_and_normalize_svg
from utils.ppt_builder import build_presentation_from_svg

app = Flask(__name__)


@app.route("/api/convert", methods=["POST"])
def convert_image_to_pptx():
    """
    Core serverless function entry point with zero-leak resource management.
    Ingests an uploaded image, runs the pipeline, compiles the presentation,
    reads it into memory, and purges all temporary files before returning the stream.
    """
    tmp_output_path = None
    try:
        # 1. Parse multipart form-data request in memory
        if "file" not in request.files:
            return jsonify({"error": "No file part provided in the request."}), 400

        uploaded_file = request.files["file"]
        if not uploaded_file.filename:
            return jsonify({"error": "No selected file."}), 400

        file_bytes = uploaded_file.read()

        # 2. Pipeline Step 1: Security & Header Validation
        try:
            img = validate_image_payload(file_bytes)
        except SecurityValidationError as e:
            return jsonify({"error": f"Security validation failed: {str(e)}"}), 400

        with img:
            # 3. Pipeline Step 2: Color Quantization & Preprocessing
            preprocessed_img = quantize_and_preprocess_image(img)

        # 4. Pipeline Step 3: Rust-Powered Vector Tracing (vtracer)
        try:
            svg_content = trace_image_to_svg(preprocessed_img)
        except TracerExecutionError as e:
            return jsonify({"error": f"Vector tracing failed: {str(e)}"}), 422

        # 5. Pipeline Step 4: Strict XML Security Sanitization
        try:
            sanitize_svg_content(svg_content)
        except SVGSecurityError as e:
            return jsonify({"error": f"SVG security violation: {str(e)}"}), 422

        # 6. Pipeline Step 5: Path Parsing & EMU Coordinate Normalization
        try:
            parsed_svg_data = parse_and_normalize_svg(svg_content)
        except Exception as e:
            return jsonify({"error": f"SVG path parsing failed: {str(e)}"}), 422

        # 7. Pipeline Step 6: Presentation Compilation with Zero-Leak Guarantee
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp_out:
                tmp_output_path = tmp_out.name

            build_presentation_from_svg(parsed_svg_data, output_path=tmp_output_path)

            # Read into memory buffer so we can delete the disk artifact immediately
            with open(tmp_output_path, "rb") as f_in:
                ppt_bytes = f_in.read()

        finally:
            # Guaranteed file unlinking before HTTP response stream is returned
            if tmp_output_path and os.path.exists(tmp_output_path):
                try:
                    os.remove(tmp_output_path)
                except OSError:
                    pass

        return send_file(
            io.BytesIO(ppt_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name="converted_presentation.pptx"
        )

    except Exception as e:
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500


# For local development execution support
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)