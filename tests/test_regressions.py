import io
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from utils.ppt_builder import build_presentation_from_svg
from utils.svg_parser import parse_and_normalize_svg, parse_transform
from utils.tracer import _looks_like_svg, trace_image_to_svg

A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def test_tracer_accepts_xml_prolog_and_comment():
    """vtracer output starts with <?xml ...?> and a comment, which must still count as SVG."""
    svg = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generator: VTracer -->\n<svg width="1" height="1"/>'
    assert _looks_like_svg(svg)
    assert _looks_like_svg("<svg/>")
    assert not _looks_like_svg("<html><svg/></html>")
    assert not _looks_like_svg("not svg")


def test_trace_real_image_returns_svg():
    svg = trace_image_to_svg(Image.new("RGB", (64, 64), (200, 30, 30)))
    assert "<svg" in svg


def test_parse_transform_translate_and_scale():
    assert parse_transform("translate(10,20)") == (1, 0, 0, 1, 10, 20)
    assert parse_transform("translate(5)") == (1, 0, 0, 1, 5, 0)
    assert parse_transform("scale(2)") == (2, 0, 0, 2, 0, 0)


def test_parser_applies_path_translate():
    """vtracer positions every path via transform="translate(x,y)"; it must be honoured."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
        '<path d="M0 0 L10 0 L10 10 L0 10 Z" fill="#ff0000" transform="translate(50,0)"/>'
        '<path d="M0 0 L10 0 L10 10 L0 10 Z" fill="#00ff00"/>'
        "</svg>"
    )
    data = parse_and_normalize_svg(svg)
    moved, origin = data["shapes"]
    assert moved["segments"][0]["start"][0] > origin["segments"][0]["start"][0]


def test_parser_inherits_group_transform():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<g transform="translate(40,0)"><path d="M0 0 L10 0 L10 10 L0 10 Z" fill="#000"/></g>'
        '<path d="M0 0 L10 0 L10 10 L0 10 Z" fill="#000"/>'
        "</svg>"
    )
    grouped, plain = parse_and_normalize_svg(svg)["shapes"]
    assert grouped["segments"][0]["start"][0] > plain["segments"][0]["start"][0]


def test_parser_keeps_subpaths_for_holes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<path d="M0 0 L50 0 L50 50 L0 50 Z M10 10 L40 10 L40 40 L10 40 Z" fill="#000"/>'
        "</svg>"
    )
    (shape,) = parse_and_normalize_svg(svg)["shapes"]
    assert len(shape["subpaths"]) == 2


def test_parser_converts_arcs_to_cubics():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<path d="M10 50 A40 40 0 0 1 90 50 A40 40 0 0 1 10 50 Z" fill="#000"/>'
        "</svg>"
    )
    (shape,) = parse_and_normalize_svg(svg)["shapes"]
    assert all(seg["type"] == "C" for seg in shape["segments"])


def test_builder_emits_cubic_beziers_and_saves_valid_pptx(tmp_path):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<path d="M10 50 C10 10 90 10 90 50 C90 90 10 90 10 50 Z" fill="#336699"/>'
        "</svg>"
    )
    out = tmp_path / "out.pptx"
    build_presentation_from_svg(parse_and_normalize_svg(svg), output_path=str(out))

    with zipfile.ZipFile(out) as zf:
        root = ET.fromstring(zf.read("ppt/slides/slide1.xml"))

    assert list(root.iter(f"{A_NS}custGeom"))
    assert list(root.iter(f"{A_NS}cubicBezTo")), "Bezier curves must not be flattened to lines"
    fills = [e.get("val") for e in root.iter(f"{A_NS}srgbClr")]
    assert "336699" in fills


def test_builder_handles_empty_shape_list(tmp_path):
    out = tmp_path / "empty.pptx"
    build_presentation_from_svg({"shapes": []}, output_path=str(out))
    assert out.exists()


def test_multicolour_image_end_to_end():
    from api.convert import app
    from PIL import ImageDraw

    img = Image.new("RGB", (300, 200), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, 140, 140), fill=(220, 40, 40))
    d.rectangle((170, 40, 280, 120), fill=(30, 90, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    resp = app.test_client().post("/api/convert", data={"file": (io.BytesIO(buf.getvalue()), "x.png")})
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        xml = zf.read("ppt/slides/slide1.xml").decode()
    assert "DC2828" in xml.upper() or "DC2828" in xml.upper().replace(" ", "")
    assert xml.count("<a:custGeom>") >= 2
