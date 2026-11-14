import io
from PIL import Image, UnidentifiedImageError

# Strict bounds for serverless safety
MAX_FILE_SIZE_BYTES = int(4.5 * 1024 * 1024)  # 4.5 MB
MAX_WIDTH = 4000
MAX_HEIGHT = 4000

# Magic number signatures for allowed image formats
MAGIC_NUMBERS = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff"
}


class SecurityValidationError(ValueError):
    """Raised when an uploaded file fails security or structural validation."""
    pass


def validate_image_payload(file_bytes: bytes) -> Image.Image:
    """
    Validates raw uploaded image bytes against magic numbers, size limits, 
    dimension bounds, and corruption vectors before processing.
    
    Returns a lazily-opened, verified PIL Image object.
    """
    if not isinstance(file_bytes, bytes):
        raise SecurityValidationError("Invalid payload format. Expected raw bytes.")

    # 1. Enforce strict file size limits (prevents memory exhaustion)
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise SecurityValidationError(
            f"File size exceeds the maximum allowed limit of {MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB."
        )

    if len(file_bytes) == 0:
        raise SecurityValidationError("Uploaded file is empty.")

    # 2. Inspect Magic Numbers (prevents MIME-spoofing and truncation attacks)
    matched_format = None
    for fmt, signature in MAGIC_NUMBERS.items():
        if file_bytes.startswith(signature):
            matched_format = fmt
            break

    if not matched_format:
        raise SecurityValidationError(
            "Invalid file signature. Only verified PNG and JPEG formats are supported."
        )

    # 3. Parse headers lazily using Pillow to check dimensions and integrity
    try:
        image_stream = io.BytesIO(file_bytes)
        with Image.open(image_stream) as img:
            # Verify file integrity (catches truncation and corruption)
            img.verify()
    except UnidentifiedImageError:
        raise SecurityValidationError("File is corrupted or not a valid image structure.")
    except Exception as e:
        raise SecurityValidationError(f"Failed to parse image headers: {str(e)}")

    # Re-open stream since verify() exhausts the iterator/stream state in Pillow
    image_stream = io.BytesIO(file_bytes)
    img = Image.open(image_stream)

    # 4. Enforce strict dimension boundaries (prevents pixel bombs / OOM)
    width, height = img.size
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        img.close()
        raise SecurityValidationError(
            f"Image dimensions ({width}x{height}) exceed the maximum allowed bounds of {MAX_WIDTH}x{MAX_HEIGHT} pixels."
        )

    if width <= 0 or height <= 0:
        img.close()
        raise SecurityValidationError("Invalid image dimensions reported.")

    return img