from fastapi.testclient import TestClient
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import session_store
from app.config import get_settings
from app.models import RetrievalHit
import shutil
from uuid import uuid4


client = TestClient(app)


def setup_function() -> None:
    session_store.reset()


def _make_kb_dir():
    settings = get_settings()
    path = settings.knowledge_base_dir / f"_chat_tests_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_create_session_endpoint() -> None:
    response = client.post("/api/chat/sessions", json={"title": "Cross-subject Session"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Cross-subject Session"
    assert payload["stage"] == "intake"


def test_post_message_extracts_fields_for_language_subject() -> None:
    settings = get_settings()
    source_dir = _make_kb_dir()
    namespace = f"chat_api_{uuid4().hex}"
    (source_dir / "english.txt").write_text(
        "Environment Protection includes sustainability, discussion prompts, and collaborative tasks.",
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

    response = client.post(
        "/api/chat/messages",
        json={
            "title": "Demo",
            "content": '我想做一节高中英语"Environment Protection"课程，40分钟，加入讨论和项目任务，风格简洁。',
        },
    )
    try:
        assert response.status_code == 200
        payload = response.json()
        assert payload["stage"] == "clarification"
        assert payload["teaching_spec"]["education_stage"] == "high-school"
        assert payload["teaching_spec"]["subject"] == "english"
        assert payload["teaching_spec"]["lesson_title"] == "Environment Protection"
        assert payload["teaching_spec"]["class_duration_minutes"] == 40
        assert "discussion" in payload["assistant_message"]
        assert payload["session"]["messages"][0]["role"] == "user"
        assert payload["session"]["messages"][1]["role"] == "assistant"
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_existing_session_can_be_reused() -> None:
    create_response = client.post("/api/chat/sessions", json={"title": "History Session"})
    session_id = create_response.json()["session_id"]

    response = client.post(
        "/api/chat/messages",
        json={
            "session_id": session_id,
            "content": "这是一节初中历史课，主题是《工业革命》，希望有讨论活动。",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["teaching_spec"]["subject"] == "history"
    assert payload["teaching_spec"]["lesson_title"] == "工业革命"


def test_post_message_extracts_fields_for_math_subject() -> None:
    response = client.post(
        "/api/chat/messages",
        json={
            "title": "Math Demo",
            "content": "请帮我准备一节初中数学《一次函数》复习课，50分钟，增加练习和小测。",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["teaching_spec"]["education_stage"] == "middle-school"
    assert payload["teaching_spec"]["subject"] == "math"
    assert payload["teaching_spec"]["lesson_title"] == "一次函数"
    assert payload["teaching_spec"]["class_duration_minutes"] == 50


def test_post_message_can_enable_web_search(monkeypatch) -> None:
    def fake_search_web_hits(query: str, top_k: int) -> list[RetrievalHit]:
        assert "工业革命" in query
        return [
            RetrievalHit(
                chunk_id="web:history-1",
                asset_id="https://example.com/history/industrial-revolution",
                content="Industrial Revolution timeline with steam engine, factory system, and urbanization.",
                score=9.5,
                page_label="example.com",
                source_type="web",
                source_url="https://example.com/history/industrial-revolution",
                source_title="Industrial Revolution timeline",
            )
        ]

    monkeypatch.setattr("app.services.planner.search_web_hits", fake_search_web_hits)

    response = client.post(
        "/api/chat/messages",
        json={
            "title": "History Web Search Demo",
            "content": "我想做一节初中历史《工业革命》课程，45分钟，加入材料分析和讨论。",
            "use_web_search": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["web_search_enabled"] is True
    assert any(hit["source_type"] == "web" for hit in payload["session"]["retrieval_hits"])
    assert "联网搜索" in payload["assistant_message"]


def test_post_message_extracts_only_explicit_constraints() -> None:
    response = client.post(
        "/api/chat/messages",
        json={
            "title": "History Tight Constraints",
            "content": "我想做一节初中历史《工业革命》课程，45分钟，教学目标：理解蒸汽机与工厂制度的关系。不要扩展到未提供的课外史实，只使用上传资料。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    spec = payload["teaching_spec"]

    assert any(
        objective["description"] == "理解蒸汽机与工厂制度的关系"
        for objective in spec["learning_objectives"]
    )
    assert "不要扩展到未提供的课外史实" in spec["additional_requirements"]
    assert "只使用上传资料" in spec["additional_requirements"]
    assert "我想做一节初中历史《工业革命》课程，45分钟，教学目标：理解蒸汽机与工厂制度的关系。不要扩展到未提供的课外史实，只使用上传资料。" not in spec["additional_requirements"]
