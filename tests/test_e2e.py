import io
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image
from api.convert import app


def create_sample_png() -> bytes:
    """Helper to generate a simple test PNG image in memory."""
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_end_to_end_png_to_pptx_conversion():
    """
    Integration test: Feeds a sample PNG through the Flask test client 
    (/api/convert), captures the .pptx response stream, unzips it in memory, 
    and inspects slide1.xml to assert that valid <a:custGeom> custom geometry 
    elements are present, verifying true DrawingML vector output.
    """
    client = app.test_client()
    png_bytes = create_sample_png()

    # Post multipart form-data request to the serverless endpoint
    response = client.post(
        "/api/convert",
        data={"file": (io.BytesIO(png_bytes), "test_icon.png")}
    )

    # Assert successful HTTP response and correct MIME type
    assert response.status_code == 200
    assert response.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    # Load binary .pptx response into an in-memory zip archive
    pptx_bytes = response.data
    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zf:
        slide_path = "ppt/slides/slide1.xml"
        assert slide_path in zf.namelist(), "ppt/slides/slide1.xml missing from generated PPTX archive"

        slide_xml_content = zf.read(slide_path)
        
    # Parse XML and verify DrawingML custom geometry tags (<a:custGeom>)
    root = ET.fromstring(slide_xml_content)
    
    cust_geom_elements = []
    for elem in root.iter():
        if elem.tag.endswith("custGeom") or "custGeom" in elem.tag:
            cust_geom_elements.append(elem)

    assert len(cust_geom_elements) > 0, (
        "E2E Verification Failed: No <a:custGeom> custom geometry elements "
        "were found in ppt/slides/slide1.xml."
    )