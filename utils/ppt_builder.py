from pptx import Presentation
from pptx.util import Inches, Emu
from pptx.dml.color import RGBColor


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
    shape.line.color.rgb = rgb


def build_presentation_from_svg(parsed_svg_data: dict, output_path: str = None) -> Presentation:
    """
    Translates parsed and normalized SVG shapes into native PowerPoint
    DrawingML custom shapes, styling them and wrapping them inside a single
    GroupShape container to prevent PowerPoint UI lagging on selection.
    """
    prs, slide = create_presentation_canvas()
    shapes_data = parsed_svg_data.get("shapes", [])

    if not shapes_data:
        # Gracefully produce a minimal valid PPTX even when vector tracing yields no shapes.
        placeholder = slide.shapes.add_shape(1, 0, 0, 100, 100)
        placeholder.fill.background()
        placeholder.line.color.rgb = RGBColor(0, 0, 0)
        if output_path:
            prs.save(output_path)
        return prs

    group_shape = slide.shapes.add_group_shape()
    group_shapes_collection = group_shape.shapes

    for shape_dict in shapes_data[:200]:
        segments = shape_dict.get("segments", [])
        if not segments:
            continue

        points = []
        for seg in segments:
            start_x, start_y = seg["start"]
            end_x, end_y = seg["end"]
            points.append((int(round(start_x)), int(round(start_y))))
            points.append((int(round(end_x)), int(round(end_y))))

        if len(points) < 2:
            continue

        start_x, start_y = points[0]
        freeform_builder = group_shapes_collection.build_freeform(
            start_x=start_x,
            start_y=start_y,
            scale=1,
        )

        freeform_builder.add_vertices(points[1:], close=bool(shape_dict.get("closed", False)))

        try:
            shape = freeform_builder.convert_to_shape(origin_x=Emu(0), origin_y=Emu(0))
            fill_color_str = shape_dict.get("color", "#000000")
            apply_shape_styling(shape, fill_color_str)
        except Exception:
            continue

    if output_path:
        prs.save(output_path)

    return prs
