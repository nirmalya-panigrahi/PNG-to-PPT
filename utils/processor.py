from PIL import Image


def quantize_and_preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocesses a PIL Image for vectorization:
    1. Strips alpha transparency by compositing onto a solid white background (RGB).
    2. Clamps the color palette down to a maximum of 12 distinct flat colors
       using Median Cut quantization to prevent microscopic SVG path explosions.
    3. Preserves sharp edge definitions (no smoothing/blurring filters).
    4. Caps oversized input dimensions to keep tracing fast and memory-safe.
    """
    img.load()

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")

        if img.mode == "RGBA":
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    else:
        img = img.convert("RGB")

    max_side = 1800
    if max(img.size) > max_side:
        scale = max_side / float(max(img.size))
        new_size = (
            max(1, int(round(img.width * scale))),
            max(1, int(round(img.height * scale))),
        )
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    quantized_p = img.quantize(colors=12, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    rgb_quantized = quantized_p.convert("RGB")

    return rgb_quantized
