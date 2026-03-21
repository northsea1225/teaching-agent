from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shutil

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.services.storage import session_store


client = TestClient(app)


def setup_function() -> None:
    session_store.reset()


def _cleanup_session(session_id: str) -> None:
    settings = get_settings()
    shutil.rmtree(settings.raw_data_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.parsed_data_dir / session_id, ignore_errors=True)


def _build_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_upload_pdf_creates_session_and_parsed_file() -> None:
    response = client.post(
        "/api/files/upload",
        files={
            "file": (
                "lesson.pdf",
                _build_pdf_bytes("Courseware sample content"),
                "application/pdf",
            )
        },
        data={"title": "Upload Demo"},
    )
    assert response.status_code == 200
    payload = response.json()
    session_id = payload["session_id"]
    try:
        assert payload["file"]["resource_type"] == "pdf"
        assert payload["file"]["parse_status"] == "completed"
        assert payload["file"]["parsed_path"]
        assert payload["session"]["uploaded_files"][0]["filename"] == "lesson.pdf"
    finally:
        _cleanup_session(session_id)


def test_upload_image_uses_existing_session() -> None:
    session_response = client.post("/api/chat/sessions", json={"title": "Image Session"})
    session_id = session_response.json()["session_id"]

    image_buffer = BytesIO()
    image = Image.new("RGB", (200, 100), color="blue")
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    response = client.post(
        "/api/files/upload",
        files={"file": ("diagram.png", image_buffer.getvalue(), "image/png")},
        data={"session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.json()
    try:
        assert payload["session_id"] == session_id
        assert payload["file"]["resource_type"] == "image"
        assert payload["file"]["metadata"]["width"] == 200
    finally:
        _cleanup_session(session_id)
