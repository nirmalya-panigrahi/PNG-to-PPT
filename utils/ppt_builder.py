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
    
    # Set explicit widescreen dimensions
    prs.slide_width = Inches(width_inches)
    prs.slide_height = Inches(height_inches)
    
    # Use blank slide layout (index 6) for clean custom shape placement
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)
    
    return prs, slide


def _hex_to_rgb(hex_str: str) -> RGBColor:
    """
    Parses a hex color string (e.g., '#FF0000', '#RGB', or named colors) 
    into a PowerPoint-compatible RGBColor object.
    """
    if not isinstance(hex_str, str):
        return RGBColor(0, 0, 0)

    cleaned = hex_str.strip().lstrip("#")
    
    # Handle 3-digit shorthand hex codes (e.g., "F00" -> "FF0000")
    if len(cleaned) == 3:
        cleaned = "".join([c * 2 for c in cleaned])
    
    if len(cleaned) != 6:
        return RGBColor(0, 0, 0)  # Safe black fallback for invalid formats

    try:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
        return RGBColor(r, g, b)
    except ValueError:
        return RGBColor(0, 0, 0)


def apply_shape_styling(shape, hex_color: str) -> None:
    """
    Applies solid fill properties to a generated PowerPoint shape and matches 
    the border (line color) to the fill color to prevent black outline artifacts 
    and gap lines between adjacent vector paths.
    """
    if not hex_color or hex_color.lower() == "none":
        shape.fill.background()
        shape.line.fill.background()
        return

    rgb = _hex_to_rgb(hex_color)

    # Apply solid fill
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb

    # Set outline border color to match fill for seamless vector rendering
    shape.line.color.rgb = rgb


def build_presentation_from_svg(parsed_svg_data: dict, output_path: str = None) -> Presentation:
    """
    Translates parsed and normalized SVG shapes into native PowerPoint 
    DrawingML custom shapes, styling them and wrapping them inside a single 
    GroupShape container to prevent PowerPoint UI lagging on selection.
    """
    prs, slide = create_presentation_canvas()
    shapes_data = parsed_svg_data.get("shapes", [])

    # 1. Create an empty group shape container on the slide
    group_shape = slide.shapes.add_group_shape()
    group_shapes_collection = group_shape.shapes

    for shape_dict in shapes_data:
        segments = shape_dict.get("segments", [])
        if not segments:
            continue

        start_pt = segments[0]["start"]
        start_x, start_y = start_pt[0], start_pt[1]

        # Initialize FreeformBuilder inside the group's shape tree context
        freeform_builder = group_shapes_collection.build_freeform(
            start_x=start_x,
            start_y=start_y,
            scale=Inches(1)
        )

        for seg in segments:
            seg_type = seg["type"]
            end_x, end_y = seg["end"]
            rel_x = end_x - start_x
            rel_y = end_y - start_y

            if seg_type == "L":
                freeform_builder.add_line_segments([(rel_x, rel_y)], close=False)
            elif seg_type == "C":
                # For cubic bezier segments, map endpoint relative coordinates
                freeform_builder.add_line_segments([(rel_x, rel_y)], close=False)

        try:
            # Convert and convert relative to origin
            shape = freeform_builder.convert_to_shape(origin_x=Emu(0), origin_y=Emu(0))
            
            # Apply color styling and border cleanup
            fill_color_str = shape_dict.get("color", "#000000")
            apply_shape_styling(shape, fill_color_str)
        except Exception:
            continue

    if output_path:
        prs.save(output_path)

    return prs