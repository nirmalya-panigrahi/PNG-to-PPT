import xml.etree.ElementTree as ET


class SVGSecurityError(ValueError):
    """Raised when an SVG violates security rules, such as containing prohibited raster elements."""
    pass


def sanitize_svg_content(svg_content: str) -> None:
    """
    Parses the generated SVG string using Python's xml.etree.ElementTree 
    and enforces an absolute security rule: Zero <image> tags permitted.
    
    Aborts conversion immediately by raising an SVGSecurityError if any 
    base64-encoded raster fallback tag or external image reference is detected.
    """
    if not isinstance(svg_content, str) or not svg_content.strip():
        raise SVGSecurityError("SVG content is empty or invalid.")

    try:
        # Parse the XML structure
        root = ET.fromstring(svg_content)
    except ET.ParseError as e:
        raise SVGSecurityError(f"Failed to parse SVG XML structure: {str(e)}") from e

    # Traverse all elements to check for prohibited <image> tags,
    # accounting for potential XML namespaces (e.g., {http://www.w3.org/2000/svg}image)
    for elem in root.iter():
        # Strip out namespace brackets if present to evaluate the local tag name
        tag_local = elem.tag.split("}")[-1].lower() if "}" in elem.tag else elem.tag.lower()

        if tag_local == "image":
            raise SVGSecurityError(
                "Security violation: Prohibited <image> tag detected inside SVG. "
                "Raster embedding and raster bypasses are strictly forbidden."
            )