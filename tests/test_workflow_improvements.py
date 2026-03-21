from __future__ import annotations

from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import RetrievalHit, SessionStage, SessionState, TeachingSpec
from app.services.confirmation import build_planning_confirmation
from app.services.storage import session_store
from app.services.svg import generate_svg_deck_for_session


client = TestClient(app)


def _cleanup_workspace(session_id: str) -> None:
    settings = get_settings()
    shutil.rmtree(settings.workspaces_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.exports_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.raw_data_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.parsed_data_dir / session_id, ignore_errors=True)


def test_session_store_persists_workspace_snapshot() -> None:
    session = session_store.create_session("Workspace Snapshot Demo")
    workspace_path = Path(session.workspace_path or "")

    try:
        assert workspace_path.exists()
        assert (workspace_path / "session.json").exists()
        assert (workspace_path / "manifests" / "project_manifest.json").exists()
        assert (workspace_path / "reports" / "planning_confirmation.json").exists()
    finally:
        _cleanup_workspace(session.session_id)


def test_confirmation_confirm_endpoint_marks_session_confirmed() -> None:
    session = SessionState(
        title="Confirmation API Demo",
        stage=SessionStage.CLARIFICATION,
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            class_duration_minutes=45,
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
            additional_requirements=["加入材料分析"],
        ),
    )
    session_store.save(session)

    try:
        response = client.post(
            "/api/planner/confirmation/confirm",
            json={
                "session_id": session.session_id,
                "note": "按当前约束继续生成",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["planning_confirmation"]["confirmed"] is True
        assert payload["session"]["planning_confirmation"]["confirmed_note"] == "按当前约束继续生成"
        assert payload["quality_report"]["status"] in {"blocked", "warning", "review", "ready"}
    finally:
        _cleanup_workspace(session.session_id)


def test_confirmation_uses_explicit_boundary_requirement_even_without_hits() -> None:
    session = SessionState(
        title="Boundary Requirement Demo",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            class_duration_minutes=45,
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
            additional_requirements=["只使用上传资料和检索命中，不要扩展到未提供的课外史实"],
        ),
    )

    confirmation = build_planning_confirmation(session)
    boundary_item = next(item for item in confirmation.items if item.label == "资料边界")

    assert boundary_item.status == "confirmed"
    assert "只使用上传资料和检索命中" in (boundary_item.detail or "")
    assert "本地知识库：默认启用" in (boundary_item.detail or "")
    assert "资料边界" not in confirmation.missing_items


def test_confirmation_defaults_boundary_to_local_knowledge_base() -> None:
    session = SessionState(
        title="Default KB Boundary Demo",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            class_duration_minutes=45,
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        ),
    )

    confirmation = build_planning_confirmation(session)
    boundary_item = next(item for item in confirmation.items if item.label == "资料边界")

    assert boundary_item.status == "confirmed"
    assert boundary_item.detail == "当前来源：本地知识库：默认启用；联网补充搜索：未开启"
    assert "资料边界" not in confirmation.missing_items


def test_confirmation_boundary_combines_explicit_constraint_and_runtime_scope() -> None:
    session = SessionState(
        title="Boundary Runtime Demo",
        web_search_enabled=True,
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            class_duration_minutes=45,
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
            additional_requirements=["只使用上传资料、本地知识库和检索命中"],
        ),
        retrieval_hits=[
            RetrievalHit(
                chunk_id="hist-1",
                content="工业革命推动蒸汽机和工厂制度发展。",
                source_type="knowledge-base",
                source_title="历史教材",
            )
        ],
    )

    confirmation = build_planning_confirmation(session)
    boundary_item = next(item for item in confirmation.items if item.label == "资料边界")

    assert boundary_item.status == "confirmed"
    assert "约束：" in (boundary_item.detail or "")
    assert "当前：" in (boundary_item.detail or "")
    assert "本地知识库：默认启用" in (boundary_item.detail or "")
    assert "联网补充搜索：已开启" in (boundary_item.detail or "")


def test_quality_report_endpoint_returns_workspace_quality_state() -> None:
    session = SessionState(
        title="Quality Report Demo",
        teaching_spec=TeachingSpec(
            education_stage="high-school",
            subject="english",
            lesson_title="Environment Protection",
            class_duration_minutes=40,
            learning_objectives=[{"description": "围绕环境议题组织阅读与讨论"}],
        ),
    )
    session_store.save(session)

    try:
        response = client.post(
            "/api/quality/report",
            json={"session_id": session.session_id},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["quality_report"]["status"] in {"warning", "review", "blocked", "ready"}
        assert payload["session"]["workspace_path"]
    finally:
        _cleanup_workspace(session.session_id)


def test_svg_generation_assigns_template_ids_and_finalizes_markup() -> None:
    session = SessionState(
        title="SVG Finalize Demo",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="science",
            lesson_title="生态系统",
            class_duration_minutes=45,
            learning_objectives=[{"description": "说明生态系统的组成与相互作用"}],
            key_difficulties=["理解生产者、消费者与分解者的关系"],
        ),
    )
    session_store.save(session)

    try:
        updated = generate_svg_deck_for_session(session, top_k=3)
        assert updated.svg_deck is not None
        assert updated.svg_deck.finalized is True
        assert all(slide.template_id for slide in updated.svg_deck.slides)
        assert all("<title>" in slide.markup for slide in updated.svg_deck.slides)
        assert all("template:" in slide.markup for slide in updated.svg_deck.slides)
    finally:
        _cleanup_workspace(session.session_id)
