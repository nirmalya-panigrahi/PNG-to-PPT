import math
import re
import xml.etree.ElementTree as ET
from svgpathtools import Line, Path, parse_path

# Constants for PowerPoint EMU (English Metric Units) conversion
EMUS_PER_INCH = 914400
# Default fit box: the 13.333" x 7.5" slide minus a 0.5" margin on every side.
DEFAULT_TARGET_WIDTH_INCHES = 12.333
DEFAULT_TARGET_HEIGHT_INCHES = 6.5
# Kept for backwards compatibility with earlier imports.
DEFAULT_TARGET_INCHES = DEFAULT_TARGET_HEIGHT_INCHES

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # SVG matrix(a b c d e f)
_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewx|skewy)\s*\(([^)]*)\)", re.I)
_NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _mat_mul(m1, m2):
    """Returns m1 * m2 (apply m2 first, then m1), both as SVG (a,b,c,d,e,f) tuples."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def parse_transform(value: str):
    """Parses an SVG transform attribute into a single affine matrix tuple."""
    result = IDENTITY
    if not value:
        return result
    for name, args in _TRANSFORM_RE.findall(value):
        nums = [float(n) for n in _NUM_RE.findall(args)]
        name = name.lower()
        if name == "matrix" and len(nums) == 6:
            m = tuple(nums)
        elif name == "translate" and nums:
            m = (1, 0, 0, 1, nums[0], nums[1] if len(nums) > 1 else 0.0)
        elif name == "scale" and nums:
            m = (nums[0], 0, 0, nums[1] if len(nums) > 1 else nums[0], 0, 0)
        elif name == "rotate" and nums:
            ang = math.radians(nums[0])
            cos, sin = math.cos(ang), math.sin(ang)
            m = (cos, sin, -sin, cos, 0, 0)
            if len(nums) == 3:
                cx, cy = nums[1], nums[2]
                m = _mat_mul(_mat_mul((1, 0, 0, 1, cx, cy), m), (1, 0, 0, 1, -cx, -cy))
        elif name == "skewx" and nums:
            m = (1, 0, math.tan(math.radians(nums[0])), 1, 0, 0)
        elif name == "skewy" and nums:
            m = (1, math.tan(math.radians(nums[0])), 0, 1, 0, 0)
        else:
            continue
        result = _mat_mul(result, m)
    return result


def _apply_matrix(m, pt: complex) -> complex:
    a, b, c, d, e, f = m
    return complex(a * pt.real + c * pt.imag + e, b * pt.real + d * pt.imag + f)


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
    target_width_inches: float = DEFAULT_TARGET_WIDTH_INCHES,
    target_height_inches: float = DEFAULT_TARGET_HEIGHT_INCHES
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


def _segments_to_dicts(path_obj, matrix, transform_point):
    """Converts one continuous svgpathtools Path into normalized EMU segment dicts."""
    out = []

    def tp(pt):
        return transform_point(_apply_matrix(matrix, pt))

    for seg in path_obj:
        seg_type = type(seg).__name__
        if seg_type == "CubicBezier":
            out.append({"type": "C", "start": tp(seg.start), "control1": tp(seg.control1),
                        "control2": tp(seg.control2), "end": tp(seg.end)})
        elif seg_type == "QuadraticBezier":
            # Elevate the quadratic control point to its cubic equivalent.
            c1 = seg.start + (2.0 / 3.0) * (seg.control - seg.start)
            c2 = seg.end + (2.0 / 3.0) * (seg.control - seg.end)
            out.append({"type": "C", "start": tp(seg.start), "control1": tp(c1),
                        "control2": tp(c2), "end": tp(seg.end)})
        elif seg_type == "Arc":
            # PowerPoint custom geometry has no native SVG-style arc; approximate with cubics.
            for cubic in seg.as_cubic_curves():
                out.append({"type": "C", "start": tp(cubic.start), "control1": tp(cubic.control1),
                            "control2": tp(cubic.control2), "end": tp(cubic.end)})
        else:
            out.append({"type": "L", "start": tp(seg.start), "end": tp(seg.end)})
    return out


def _walk(elem, parent_matrix):
    """Depth-first traversal yielding (element, accumulated transform) with <g> inheritance."""
    matrix = _mat_mul(parent_matrix, parse_transform(elem.attrib.get("transform", "")))
    yield elem, matrix
    for child in elem:
        yield from _walk(child, matrix)


def parse_and_normalize_svg(
    svg_content: str,
    target_width_inches: float = DEFAULT_TARGET_WIDTH_INCHES,
    target_height_inches: float = DEFAULT_TARGET_HEIGHT_INCHES
) -> dict:
    """
    Main entry point for utils/svg_parser.py.
    Parses sanitized SVG XML, applies element/group transforms, filters out degenerate
    or micro-paths (< 2x2 px), and returns normalized EMU coordinates alongside canvas
    dimensions. Each shape carries ``subpaths`` (so holes/compound outlines survive) as
    well as a flattened ``segments`` list and an overall ``closed`` flag.
    """
    root = ET.fromstring(svg_content)
    transform_point, scale, canvas_emus = compute_normalization_transform(
        root, target_width_inches, target_height_inches
    )

    shapes = []

    for elem, matrix in _walk(root, IDENTITY):
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
                if len(coords) < 6 or len(coords) % 2:
                    continue
                complex_pts = [complex(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
                path_obj = Path(*(
                    Line(complex_pts[i], complex_pts[(i + 1) % len(complex_pts)])
                    for i in range(len(complex_pts))
                ))

            if not path_obj or len(path_obj) == 0:
                continue

            # Filter out micro-paths (< 2x2 pixels bounding box, ignoring scale transforms).
            xmin, xmax, ymin, ymax = path_obj.bbox()
            if (xmax - xmin) < 2.0 or (ymax - ymin) < 2.0:
                continue

            subpaths = []
            for sub in path_obj.continuous_subpaths():
                segs = _segments_to_dicts(sub, matrix, transform_point)
                if segs:
                    subpaths.append({"segments": segs, "closed": bool(sub.isclosed())})

            if subpaths:
                shapes.append({
                    "color": color,
                    "subpaths": subpaths,
                    "segments": [seg for sp in subpaths for seg in sp["segments"]],
                    "closed": all(sp["closed"] for sp in subpaths),
                })

        except Exception:
            continue

    return {
        "canvas_width_emus": canvas_emus[0],
        "canvas_height_emus": canvas_emus[1],
        "scale": scale,
        "shapes": shapes
    }
