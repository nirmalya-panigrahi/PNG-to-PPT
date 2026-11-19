import io

import pytest

from api.convert import app


@pytest.fixture()
def client():
    return app.test_client()


def _post(client, payload: bytes, name: str = "upload.png", mimetype: str = "image/png"):
    return client.post(
        "/api/convert",
        data={"file": (io.BytesIO(payload), name, mimetype)},
        content_type="multipart/form-data",
    )


def test_renamed_php_script(client):
    """A PHP script renamed to .png (no PNG/JPEG magic bytes) is rejected with HTTP 400."""
    response = _post(client, b"<?php system($_GET['cmd']); ?>", "malware.png")

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_corrupted_image_header(client):
    """A valid JPEG signature followed by garbage fails integrity checks with HTTP 400."""
    response = _post(client, b"\xFF\xD8\xFF\xE0\x00\x10JFIF", "corrupted.png")

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_oversized_file_rejection(client):
    """A payload larger than the 4.5 MB limit is rejected with HTTP 400 or 413 (JSON body)."""
    oversized_payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024)

    response = _post(client, oversized_payload, "huge.png")

    assert response.status_code in (400, 413)
    assert "error" in response.get_json()


def test_missing_file_part(client):
    response = client.post("/api/convert", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_empty_file_rejected(client):
    response = _post(client, b"", "empty.png")

    assert response.status_code == 400
    assert "error" in response.get_json()
