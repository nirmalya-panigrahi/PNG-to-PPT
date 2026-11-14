import xml.etree.ElementTree as ET


class SVGSecurityError(ValueError):
    """Raised when an SVG violates security rules, such as containing prohibited raster elements."""
    pass


def _local_name(tag: str) -> str:
    """Normalizes XML tag names to their local (namespace-free) form."""
    if tag is None:
        return ""
    return tag.split("}")[-1].lower() if "}" in tag else str(tag).lower()


def sanitize_svg_content(svg_content: str) -> None:
    """
    Parses the generated SVG string using Python's xml.etree.ElementTree
    and enforces the security rules required for safe PPT conversion.

    It rejects raster fallback tags, executable script elements, inline event handlers,
    external references, and other URL-based payload vectors that could enable XSS or
    unexpected content embedding.
    """
    if not isinstance(svg_content, str) or not svg_content.strip():
        raise SVGSecurityError("SVG content is empty or invalid.")

    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError as e:
        raise SVGSecurityError(f"Failed to parse SVG XML structure: {str(e)}") from e

    for elem in root.iter():
        tag_local = _local_name(elem.tag)

        # Block unsafe SVG elements outright.
        if tag_local in {"image", "script", "foreignobject", "iframe", "audio", "video"}:
            raise SVGSecurityError(
                f"Security violation: Prohibited <{tag_local}> tag detected inside SVG. "
                "Raster embedding, script execution, and embedded active content are strictly forbidden."
            )

        # Block inline script/event payloads and dangerous URL references.
        for attr_name, attr_value in elem.attrib.items():
            attr_key = _local_name(attr_name)
            value = (attr_value or "").strip()

            if attr_key.startswith("on"):
                raise SVGSecurityError(
                    f"Security violation: Event handler '{attr_name}' detected inside SVG."
                )

            if attr_key in {"href", "xlink:href", "src"}:
                if value and not value.startswith("#"):
                    raise SVGSecurityError(
                        "Security violation: External or non-fragment SVG references are prohibited."
                    )

            if attr_key == "style":
                style_value = value.lower()
                if "javascript:" in style_value or "data:" in style_value or "url(" in style_value:
                    raise SVGSecurityError(
                        "Security violation: Dangerous CSS URL or script reference detected in SVG style attribute."
                    )

        # Reject embedded external references from any element, including <use href="...">.
        if "href" in elem.attrib and elem.attrib.get("href", "").strip() and not elem.attrib.get("href", "").strip().startswith("#"):
            raise SVGSecurityError(
                "Security violation: External href reference detected inside SVG."
            )

        if "xlink:href" in elem.attrib and elem.attrib.get("xlink:href", "").strip() and not elem.attrib.get("xlink:href", "").strip().startswith("#"):
            raise SVGSecurityError(
                "Security violation: External xlink:href reference detected inside SVG."
            )

        if tag_local == "use" and elem.attrib.get("href", "").strip().startswith("#"):
            continue
