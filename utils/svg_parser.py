import xml.etree.ElementTree as ET
from svgpathtools import parse_path, Polygon

# Constants for PowerPoint EMU (English Metric Units) conversion
EMUS_PER_INCH = 914400
DEFAULT_TARGET_INCHES = 6.0


def parse_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    """
    Extracts (min_x, min_y, width, height) from the SVG root element's viewBox,
    falling back safely to width/height attributes or a default 800x600 canvas.
    """
    viewbox = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if viewbox:
        try:
            parts = [float(p) for p in viewbox.replace(",", " ").split() if p.strip()]
            if len(parts) == 4:
                return parts[0], parts[1], parts[2], parts[3]
        except ValueError:
            pass

    try:
        raw_w = root.attrib.get("width", "800").replace("px", "").replace("pt", "").strip()
        raw_h = root.attrib.get("height", "600").replace("px", "").replace("pt", "").strip()
        return 0.0, 0.0, float(raw_w), float(raw_h)
    except ValueError:
        return 0.0, 0.0, 800.0, 600.0


def compute_normalization_transform(
    root: ET.Element,
    target_width_inches: float = DEFAULT_TARGET_INCHES,
    target_height_inches: float = DEFAULT_TARGET_INCHES
):
    """
    Computes an aspect-ratio-preserving scaling matrix to map SVG viewport coordinates
    into PowerPoint EMUs, guarding against zero-dimension viewBoxes.
    """
    vx, vy, vw, vh = parse_viewbox(root)

    # Prevent divide-by-zero errors on malformed or zero-dimension viewBoxes
    safe_vw = vw if vw > 0 else 1.0
    safe_vh = vh if vh > 0 else 1.0

    target_w_emus = target_width_inches * EMUS_PER_INCH
    target_h_emus = target_height_inches * EMUS_PER_INCH

    scale = min(target_w_emus / safe_vw, target_h_emus / safe_vh)

    def transform_point(complex_pt: complex) -> tuple[int, int]:
        x_emu = int(round((complex_pt.real - vx) * scale))
        y_emu = int(round((complex_pt.imag - vy) * scale))
        return x_emu, y_emu

    normalized_width_emus = int(round(safe_vw * scale))
    normalized_height_emus = int(round(safe_vh * scale))

    return transform_point, scale, (normalized_width_emus, normalized_height_emus)


def _extract_fill_color(elem: ET.Element) -> str:
    """Extracts hex/named fill color from element attributes or inline CSS style."""
    fill = elem.attrib.get("fill", "").strip()
    if fill and fill.lower() != "none":
        return fill

    style = elem.attrib.get("style", "")
    if "fill:" in style:
        for declaration in style.split(";"):
            if "fill:" in declaration:
                val = declaration.split(":", 1)[-1].strip()
                if val and val.lower() != "none":
                    return val

    return "#000000"


def parse_and_normalize_svg(
    svg_content: str,
    target_width_inches: float = DEFAULT_TARGET_INCHES,
    target_height_inches: float = DEFAULT_TARGET_INCHES
) -> dict:
    """
    Main entry point for utils/svg_parser.py.
    Parses sanitized SVG XML, filters out degenerate or micro-paths (< 2x2 px),
    and returns normalized EMU coordinates alongside canvas dimensions.
    """
    root = ET.fromstring(svg_content)
    transform_point, scale, canvas_emus = compute_normalization_transform(
        root, target_width_inches, target_height_inches
    )

    shapes = []

    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag not in ("path", "polygon"):
            continue

        color = _extract_fill_color(elem)

        try:
            if tag == "path":
                d = elem.attrib.get("d", "").strip()
                if not d:
                    continue
                path_obj = parse_path(d)
            else:
                points = elem.attrib.get("points", "").strip()
                if not points:
                    continue
                coords = [float(p) for p in points.replace(",", " ").split() if p.strip()]
                if len(coords) < 6:
                    continue
                complex_pts = [complex(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
                path_obj = Polygon(*complex_pts)

            if not path_obj or len(path_obj) == 0:
                continue

            # Filter out micro-paths (< 2x2 pixels bounding box)
            xmin, xmax, ymin, ymax = path_obj.bbox()
            if (xmax - xmin) < 2.0 or (ymax - ymin) < 2.0:
                continue

            # Map segments into normalized EMU coordinates
            normalized_segments = []
            for seg in path_obj:
                seg_type = type(seg).__name__
                start_emu = transform_point(seg.start)
                end_emu = transform_point(seg.end)

                if seg_type == "CubicBezier":
                    ctrl1_emu = transform_point(seg.control1)
                    ctrl2_emu = transform_point(seg.control2)
                    normalized_segments.append({
                        "type": "C",
                        "start": start_emu,
                        "control1": ctrl1_emu,
                        "control2": ctrl2_emu,
                        "end": end_emu
                    })
                elif seg_type == "QuadraticBezier":
                    # Elevate quadratic control point to cubic equivalent for PowerPoint FreeformBuilder
                    c1 = seg.start + (2.0 / 3.0) * (seg.control - seg.start)
                    c2 = seg.end + (2.0 / 3.0) * (seg.control - seg.end)
                    normalized_segments.append({
                        "type": "C",
                        "start": start_emu,
                        "control1": transform_point(c1),
                        "control2": transform_point(c2),
                        "end": end_emu
                    })
                else:
                    normalized_segments.append({
                        "type": "L",
                        "start": start_emu,
                        "end": end_emu
                    })

            if normalized_segments:
                shapes.append({
                    "color": color,
                    "segments": normalized_segments,
                    "closed": path_obj.isclosed()
                })

        except Exception:
            continue

    return {
        "canvas_width_emus": canvas_emus[0],
        "canvas_height_emus": canvas_emus[1],
        "scale": scale,
        "shapes": shapes
    }