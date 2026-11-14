import pytest
from utils.sanitizer import sanitize_svg_content, SVGSecurityError


def test_svg_with_image_tag_raises_error():
    """
    Test that an SVG containing a base64-encoded raster <image> fallback tag 
    is immediately rejected with an SVGSecurityError.
    """
    malicious_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect width="100" height="100" fill="red"/>
        <image href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" width="50" height="50"/>
    </svg>"""
    
    with pytest.raises(SVGSecurityError) as exc_info:
        sanitize_svg_content(malicious_svg)
    
    assert "image" in str(exc_info.value).lower()


def test_svg_with_script_tag_raises_error():
    """
    Test that an SVG containing an executable <script> tag 
    is rejected with an SVGSecurityError.
    """
    malicious_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <script>alert('XSS / Malicious payload');</script>
        <path d="M10 10 L90 90" fill="blue"/>
    </svg>"""
    
    with pytest.raises(SVGSecurityError):
        sanitize_svg_content(malicious_svg)


def test_svg_with_external_reference_raises_error():
    """
    Test that an SVG containing external xlink:href or href references 
    is rejected with an SVGSecurityError.
    """
    malicious_svg = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="100">
        <use xlink:href="http://malicious.com/exploit.svg#shape" x="0" y="0"/>
    </svg>"""
    
    with pytest.raises(SVGSecurityError):
        sanitize_svg_content(malicious_svg)


def test_clean_svg_passes_sanitization():
    """
    Test that a clean SVG containing pure vector paths and polygons 
    passes sanitization without raising any errors.
    """
    clean_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
        <path d="M10 10 L90 10 L90 90 Z" fill="#ff0000"/>
        <polygon points="20,20 80,20 50,80" fill="#00ff00"/>
    </svg>"""
    
    # Should not raise any exception
    sanitize_svg_content(clean_svg)