import io
import logging
import os
import sys
import tempfile

# Allow `python api/convert.py` (which only puts api/ on sys.path) to import utils.*
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import HTTPException

from utils.security import validate_image_payload, SecurityValidationError, MAX_FILE_SIZE_BYTES
from utils.processor import quantize_and_preprocess_image
from utils.tracer import trace_image_to_svg, TracerExecutionError
from utils.sanitizer import sanitize_svg_content, SVGSecurityError
from utils.svg_parser import parse_and_normalize_svg
from utils.ppt_builder import build_presentation_from_svg

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
# Reject oversized bodies before they are buffered (file limit + multipart overhead).
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_BYTES + 512 * 1024


def _allowed_origins():
    return [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]


@app.after_request
def add_cors_headers(response):
    """
    Opt-in CORS so a statically hosted frontend (e.g. GitHub Pages) can call this API.
    Set ALLOWED_ORIGINS to a comma-separated list such as
    "https://nirmalya-panigrahi.github.io". Unset = same-origin only (the default).
    """
    allowed = _allowed_origins()
    origin = request.headers.get("Origin")
    if allowed and origin and ("*" in allowed or origin in allowed):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.errorhandler(413)
def payload_too_large(_err):
    return jsonify({"error": "File exceeds the maximum allowed upload size."}), 413


@app.route("/", methods=["GET"])
def index():
    """Serves the web UI for local development (Vercel serves index.html statically)."""
    return send_file(os.path.join(PROJECT_ROOT, "index.html"))


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

    except HTTPException:
        # Let Flask render intended HTTP errors (e.g. 413 Request Entity Too Large).
        raise
    except Exception:
        # Log details server-side; don't leak internals to the client.
        logger.exception("Unexpected error while converting image")
        return jsonify({"error": "An unexpected server error occurred."}), 500


# For local development execution support.
# The Werkzeug debugger allows arbitrary code execution, so it is opt-in and the server
# only binds to localhost unless explicitly told otherwise.
if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
