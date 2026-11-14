from PIL import Image

def quantize_and_preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocesses a PIL Image for vectorization:
    1. Strips alpha transparency by compositing onto a solid white background (RGB).
    2. Clamps the color palette down to a maximum of 12 distinct flat colors 
       using Median Cut quantization to prevent microscopic SVG path explosions.
    3. Preserves sharp edge definitions (no smoothing/blurring filters).
    """
    # Ensure image data is loaded into memory
    img.load()

    # 1. Strip alpha / transparency channels safely
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        
        if img.mode == "RGBA":
            # Paste using alpha mask to prevent black artifact bleeding on transparent pixels
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    else:
        img = img.convert("RGB")

    # 2. Median Cut Color Quantization (Max 12 flat colors, zero dithering for clean flat edges)
    # Quantize reduces the color space, and converting back to RGB yields flat-color regions
    quantized_p = img.quantize(colors=12, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    rgb_quantized = quantized_p.convert("RGB")

    return rgb_quantized