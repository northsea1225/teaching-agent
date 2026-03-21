from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import InteractionMode, RetrievalHit, TeachingSpec
from app.services.planner import generate_lesson_outline, generate_slide_plan
from app.services.preview import generate_preview_deck


client = TestClient(app)


def _make_kb_dir() -> Path:
    settings = get_settings()
    path = settings.knowledge_base_dir / f"_preview_tests_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_generate_preview_deck_renders_html_document() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        interaction_preferences=[InteractionMode.DISCUSSION],
        style_preferences=["简洁", "可视化"],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            asset_id="history-asset",
            content="Industrial Revolution lessons benefit from timeline evidence and source analysis.",
            page_label="p2",
        )
    ]
    outline = generate_lesson_outline(spec, hits)
    slide_plan = generate_slide_plan(spec, outline, hits)
    preview = generate_preview_deck(slide_plan)

    assert preview.slides
    assert "<!DOCTYPE html>" in preview.html_document
    assert "工业革命 slide plan preview" in preview.html_document
    assert any("Speaker Notes" in slide.html for slide in preview.slides)


def test_preview_deck_endpoint_generates_preview() -> None:
    settings = get_settings()
    source_dir = _make_kb_dir()
    namespace = f"preview_api_{uuid4().hex}"

    try:
        (source_dir / "math.txt").write_text(
            "Linear function review lessons should include graph interpretation, common mistakes, and short quizzes.",
            encoding="utf-8",
        )

        ingest_response = client.post(
            "/api/kb/ingest",
            json={
                "source_dir": str(source_dir),
                "reset": True,
                "store_namespace": namespace,
            },
        )
        assert ingest_response.status_code == 200

        chat_response = client.post(
            "/api/chat/messages",
            json={
                "title": "Math Demo",
                "content": "我想做一节初中数学《一次函数》复习课，50分钟，增加练习和小测。",
            },
        )
        assert chat_response.status_code == 200
        session_id = chat_response.json()["session_id"]

        preview_response = client.post(
            "/api/preview/deck",
            json={
                "session_id": session_id,
                "store_namespace": namespace,
                "top_k": 3,
            },
        )
        assert preview_response.status_code == 200
        payload = preview_response.json()
        assert payload["outline"]["sections"]
        assert payload["slide_plan"]["slides"]
        assert payload["preview"]["slides"]
        assert "<!DOCTYPE html>" in payload["preview"]["html_document"]
        assert payload["session"]["stage"] == "preview"
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)
