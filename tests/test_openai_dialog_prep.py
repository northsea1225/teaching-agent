from pathlib import Path

from app.config import Settings
from app.models import TeachingSpec
from app.services.openai_dialog import (
    DialogClarificationDraft,
    DialogExtraction,
    build_dialog_input,
    merge_extraction_into_spec,
    openai_dialog_ready,
)


def test_build_dialog_input_includes_existing_spec_and_latest_message() -> None:
    existing = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
    )

    prompt = build_dialog_input(
        existing,
        "教学目标：理解蒸汽机与工厂制度的关系。加入材料分析和讨论。",
    )

    assert "工业革命" in prompt
    assert "history" in prompt
    assert "教学目标：理解蒸汽机与工厂制度的关系" in prompt


def test_merge_extraction_into_spec_builds_teaching_spec() -> None:
    extraction = DialogExtraction(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        class_duration_minutes=45,
        learning_objectives=[
            "理解蒸汽机与工厂制度的关系",
            "说明工业革命对城市化的影响",
        ],
        key_difficulties=["区分技术进步与社会结构变化之间的关系"],
        teaching_methods=["材料分析", "课堂讨论"],
        interaction_preferences=["discussion"],
        style_preferences=["学术", "简洁"],
        additional_requirements=["只使用上传资料和检索命中"],
        unresolved_questions=[
            DialogClarificationDraft(
                prompt="请确认是否需要加入课堂练习。",
                reason="互动环节还不够明确。",
            )
        ],
        confidence=0.82,
        confirmed=False,
    )

    spec = merge_extraction_into_spec(None, extraction)

    assert spec.subject == "history"
    assert spec.lesson_title == "工业革命"
    assert spec.class_duration_minutes == 45
    assert spec.learning_objectives[0].description == "理解蒸汽机与工厂制度的关系"
    assert spec.interaction_preferences[0].value == "discussion"
    assert spec.additional_requirements == ["只使用上传资料和检索命中"]
    assert spec.unresolved_questions[0].prompt == "请确认是否需要加入课堂练习。"
    assert spec.confirmed is False
    assert spec.confidence == 0.82


def test_merge_extraction_normalizes_cn_subject_and_stage() -> None:
    extraction = DialogExtraction(
        education_stage="初中",
        subject="历史",
        lesson_title="工业革命",
        interaction_preferences=["discussion"],
    )

    spec = merge_extraction_into_spec(None, extraction)

    assert spec.education_stage == "middle-school"
    assert spec.subject == "history"


def test_merge_extraction_preserves_existing_boundary_requirement() -> None:
    existing = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["只使用上传资料和检索命中，不要扩展到未提供的课外史实"],
    )
    extraction = DialogExtraction(
        additional_requirements=["加入材料分析和课堂讨论"],
    )

    spec = merge_extraction_into_spec(existing, extraction)

    assert "加入材料分析和课堂讨论" in spec.additional_requirements
    assert any("只使用上传资料和检索命中" in item for item in spec.additional_requirements)


def test_merge_extraction_replaces_boundary_requirement_when_new_one_is_explicit() -> None:
    existing = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["只使用上传资料和检索命中，不要扩展到未提供的课外史实"],
    )
    extraction = DialogExtraction(
        additional_requirements=["仅使用本地知识库和当前命中资料，不使用联网搜索"],
    )

    spec = merge_extraction_into_spec(existing, extraction)

    assert any("仅使用本地知识库和当前命中资料" in item for item in spec.additional_requirements)
    assert not any(
        item == "只使用上传资料和检索命中，不要扩展到未提供的课外史实"
        for item in spec.additional_requirements
    )


def test_openai_dialog_ready_requires_key_and_switch() -> None:
    disabled_settings = Settings(
        app_name="Teaching Agent",
        app_env="test",
        debug=True,
        api_prefix="/api",
        openai_api_key="",
        openai_base_url="",
        default_chat_model="gpt-5.4",
        use_openai_dialog=False,
        openai_dialog_model="gpt-5.4",
        openai_dialog_reasoning_effort="medium",
        openai_dialog_timeout_seconds=30.0,
        use_openai_planner=False,
        planner_api_key="",
        planner_base_url="",
        planner_model="",
        planner_timeout_seconds=45.0,
        use_openai_evidence_rerank=False,
        evidence_rerank_api_key="",
        evidence_rerank_base_url="",
        evidence_rerank_model="",
        evidence_rerank_timeout_seconds=45.0,
        use_openai_quality_review=False,
        quality_review_api_key="",
        quality_review_base_url="",
        quality_review_model="",
        quality_review_timeout_seconds=45.0,
        use_openai_slide_planner=False,
        slide_planner_api_key="",
        slide_planner_base_url="",
        slide_planner_model="",
        slide_planner_timeout_seconds=60.0,
        use_openai_speaker_notes=False,
        speaker_notes_api_key="",
        speaker_notes_base_url="",
        speaker_notes_model="",
        speaker_notes_timeout_seconds=60.0,
        embeddings_backend="local",
        embeddings_api_key="",
        embeddings_base_url="",
        embeddings_model="text-embedding-3-small",
        embeddings_dimensions=None,
        local_embedding_dim=256,
        transcribe_model="gpt-4o-mini-transcribe",
        rag_chunk_size=400,
        rag_chunk_overlap=80,
        rag_default_top_k=5,
        web_search_enabled=False,
        web_search_provider="duckduckgo",
        web_search_default_top_k=3,
        web_search_timeout_seconds=8.0,
        project_root=Path("."),
        data_dir=Path("data"),
        raw_data_dir=Path("data/raw"),
        parsed_data_dir=Path("data/parsed"),
        knowledge_base_dir=Path("data/kb"),
        vector_store_dir=Path("vector_store"),
        exports_dir=Path("exports"),
        workspaces_dir=Path("data/workspaces"),
    )
    enabled_settings = Settings(
        **{
            **disabled_settings.__dict__,
            "openai_api_key": "sk-test",
            "use_openai_dialog": True,
            "openai_base_url": "https://example.com/v1",
            "openai_dialog_model": "gemini-3.1-pro-preview",
        }
    )

    assert openai_dialog_ready(disabled_settings) is False
    assert openai_dialog_ready(enabled_settings) is True
