import os
import pytest
import requests
import io

BASE_URL = os.environ.get("TEST_SERVER_URL", "http://localhost:5000")
CONVERT_ENDPOINT = f"{BASE_URL}/api/convert"


def test_renamed_php_script():
    """
    Test that a malicious file (PHP script renamed with a .png extension 
    and fake/missing PNG magic bytes) is rejected instantly with an HTTP 400.
    """
    malicious_content = b"<?php system($_GET['cmd']); ?>"
    files = {
        "file": ("malware.png", io.BytesIO(malicious_content), "image/png")
    }
    
    response = requests.post(CONVERT_ENDPOINT, files=files)
    
    # Expect a client error status code (400 Bad Request)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_corrupted_image_header():
    """
    Test that an image with corrupted or missing PNG magic bytes 
    is rejected instantly with an HTTP 400.
    """
    corrupted_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"  # JPEG header, not PNG
    files = {
        "file": ("corrupted.png", io.BytesIO(corrupted_content), "image/png")
    }
    
    response = requests.post(CONVERT_ENDPOINT, files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_oversized_file_rejection():
    """
    Test that an oversized file (> 4.5 MB limit) is rejected 
    instantly with an HTTP 400 or 413 error.
    """
    # Create a dummy chunk larger than 4.5 MB (e.g., 5 MB of zeros)
    # Note: Valid PNG header bytes prepended to test size check specifically
    png_header = b"\x89PNG\r\n\x1a\n"
    oversized_payload = png_header + b"\x00" * (5 * 1024 * 1024)
    
    files = {
        "file": ("huge.png", io.BytesIO(oversized_payload), "image/png")
    }
    
    response = requests.post(CONVERT_ENDPOINT, files=files)
    
    assert response.status_code in (400, 413)
    data = response.json()
    assert "error" in data