import itertools

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.shapes.autoshape import AutoShapeType
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

# Upper bound on emitted shapes. vtracer's "stacked" mode paints later paths on top of
# earlier ones, so truncating drops the finest top-layer detail; keep the cap generous
# and only use it as a guard against pathological inputs.
MAX_SHAPES = 2500

MSO_SHAPE_TYPE_RECT = AutoShapeType(MSO_SHAPE.RECTANGLE)
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def create_presentation_canvas(width_inches: float = 13.333, height_inches: float = 7.5):
    """
    Initializes a python-pptx Presentation instance configured for
    standard widescreen (16:9) layout dimensions and adds a blank slide
    layout (index 6) to eliminate default placeholder boxes.
    """
    prs = Presentation()
    prs.slide_width = Inches(width_inches)
    prs.slide_height = Inches(height_inches)
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)
    return prs, slide


def _hex_to_rgb(hex_str: str) -> RGBColor:
    """Parses a hex color string into a PowerPoint-compatible RGBColor object."""
    if not isinstance(hex_str, str):
        return RGBColor(0, 0, 0)

    cleaned = hex_str.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join([c * 2 for c in cleaned])

    if len(cleaned) != 6:
        return RGBColor(0, 0, 0)

    try:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        return RGBColor(r, g, b)
    except ValueError:
        return RGBColor(0, 0, 0)


def apply_shape_styling(shape, hex_color: str) -> None:
    """Applies solid fill properties to a generated PowerPoint shape."""
    if not hex_color or hex_color.lower() == "none":
        shape.fill.background()
        shape.line.fill.background()
        return

    rgb = _hex_to_rgb(hex_color)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    # A hairline outline in the fill colour hides anti-aliasing seams between neighbours.
    shape.line.color.rgb = rgb
    shape.line.width = Pt(0.25)


def _pt(parent, x: int, y: int):
    return etree.SubElement(parent, f"{{{_A_NS}}}pt", x=str(int(x)), y=str(int(y)))


def _build_cust_geom(subpaths, off_x: int, off_y: int, width: int, height: int):
    """Builds an <a:custGeom> element (lines + cubic Beziers) in shape-local coordinates."""
    A = lambda tag: f"{{{_A_NS}}}{tag}"
    cust = etree.Element(A("custGeom"))
    for tag in ("avLst", "gdLst", "ahLst", "cxnLst"):
        etree.SubElement(cust, A(tag))
    etree.SubElement(cust, A("rect"), l="0", t="0", r="r", b="b")
    path_lst = etree.SubElement(cust, A("pathLst"))
    path = etree.SubElement(path_lst, A("path"), w=str(width), h=str(height))

    for sub in subpaths:
        segs = sub["segments"]
        if not segs:
            continue
        sx, sy = segs[0]["start"]
        move = etree.SubElement(path, A("moveTo"))
        _pt(move, sx - off_x, sy - off_y)
        for seg in segs:
            if seg["type"] == "C":
                cub = etree.SubElement(path, A("cubicBezTo"))
                for key in ("control1", "control2", "end"):
                    px, py = seg[key]
                    _pt(cub, px - off_x, py - off_y)
            else:
                line = etree.SubElement(path, A("lnTo"))
                ex, ey = seg["end"]
                _pt(line, ex - off_x, ey - off_y)
        if sub.get("closed"):
            etree.SubElement(path, A("close"))
    return cust


def _shape_bounds(subpaths):
    xs, ys = [], []
    for sub in subpaths:
        for seg in sub["segments"]:
            for key in ("start", "control1", "control2", "end"):
                if key in seg:
                    xs.append(seg[key][0])
                    ys.append(seg[key][1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _add_rect_without_recalc(shapes, left: int, top: int, width: int, height: int, id_counter=None):
    """
    Adds a rectangle autoshape to ``shapes`` quickly. python-pptx's group add_shape()
    recalculates group extents over all children and rescans every shape id on each call
    (O(n^2); 30+ seconds for ~800 shapes). When the private helpers exist we allocate ids
    from ``id_counter`` and skip per-shape recalculation (callers recalc once at the end);
    otherwise we fall back to the public API.
    """
    grp = getattr(shapes, "_grpSp", None)
    factory = getattr(shapes, "_shape_factory", None)
    if id_counter is not None and grp is not None and factory is not None:
        try:
            shape_id = next(id_counter)
            sp = grp.add_autoshape(
                shape_id, f"Freeform {shape_id - 1}", MSO_SHAPE_TYPE_RECT.prst,
                left, top, width, height,
            )
            return factory(sp)
        except (AttributeError, TypeError):
            pass
    return shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)


def add_custom_shape(shapes, subpaths, hex_color: str, shift_x: int = 0, shift_y: int = 0, id_counter=None):
    """
    Adds one native custom-geometry freeform shape built from the given subpaths.
    python-pptx's FreeformBuilder only supports straight segments, so the <a:custGeom>
    is assembled directly to preserve the Bezier curves produced by vtracer.
    """
    bounds = _shape_bounds(subpaths)
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    width = max(1, int(round(max_x - min_x)))
    height = max(1, int(round(max_y - min_y)))
    left, top = int(round(min_x)), int(round(min_y))

    shape = _add_rect_without_recalc(shapes, left + shift_x, top + shift_y, width, height, id_counter)

    spPr = shape._element.spPr
    prst = spPr.find(qn("a:prstGeom"))
    cust = _build_cust_geom(subpaths, left, top, width, height)
    if prst is not None:
        spPr.replace(prst, cust)
    else:
        spPr.append(cust)

    # Drop theme style refs (they can add shadows/effects and a theme-coloured outline).
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)

    apply_shape_styling(shape, hex_color)
    return shape




def build_presentation_from_svg(parsed_svg_data: dict, output_path: str = None) -> Presentation:
    """
    Translates parsed and normalized SVG shapes into native PowerPoint
    DrawingML custom shapes (with real Bezier curves), styling them and wrapping
    them inside a single GroupShape container so PowerPoint stays responsive.
    The artwork is centred on the slide.
    """
    prs, slide = create_presentation_canvas()
    shapes_data = parsed_svg_data.get("shapes", [])

    if not shapes_data:
        # Gracefully produce a minimal valid PPTX even when vector tracing yields no shapes.
        placeholder = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, 100, 100)
        placeholder.fill.background()
        placeholder.line.color.rgb = RGBColor(0, 0, 0)
        if output_path:
            prs.save(output_path)
        return prs

    canvas_w = int(parsed_svg_data.get("canvas_width_emus") or 0)
    canvas_h = int(parsed_svg_data.get("canvas_height_emus") or 0)
    shift_x = max(0, (int(prs.slide_width) - canvas_w) // 2) if canvas_w else 0
    shift_y = max(0, (int(prs.slide_height) - canvas_h) // 2) if canvas_h else 0

    group_shape = slide.shapes.add_group_shape()
    group_shapes_collection = group_shape.shapes
    id_counter = itertools.count(group_shapes_collection._next_shape_id + 1) \
        if hasattr(group_shapes_collection, "_next_shape_id") else None

    for shape_dict in shapes_data[:MAX_SHAPES]:
        subpaths = shape_dict.get("subpaths")
        if subpaths is None:
            # Backwards compatibility with flat {"segments": [...], "closed": bool} input.
            subpaths = [{"segments": shape_dict.get("segments", []),
                         "closed": bool(shape_dict.get("closed", False))}]
        if not any(sp.get("segments") for sp in subpaths):
            continue
        add_custom_shape(group_shapes_collection, subpaths,
                         shape_dict.get("color", "#000000"), shift_x, shift_y, id_counter)

    # One extents recalculation for the whole group instead of one per shape.
    recalc = getattr(group_shapes_collection, "_recalculate_extents", None)
    if recalc is not None:
        recalc()

    if output_path:
        prs.save(output_path)

    return prs
