from pathlib import Path

from app.config import Settings
from app.models import LessonOutline, LessonOutlineSection, RetrievalHit, SlideType, TeachingSpec
from app.services.openai_planner import (
    PlannerOutlineDraft,
    PlannerOutlineSectionDraft,
    build_outline_input,
    merge_outline_draft,
    openai_planner_ready,
)
from app.services.openai_slide_planner import (
    SlidePlanDraft,
    SlidePlanSlideDraft,
    build_slide_plan_input,
    openai_slide_planner_ready,
)
from app.services.openai_speaker_notes import (
    SpeakerNotesDeckDraft,
    SpeakerNotesSlideDraft,
    build_speaker_notes_input,
    openai_speaker_notes_ready,
)


def test_build_outline_input_contains_spec_and_retrieval_hits() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            content="工业革命推动蒸汽机和工厂制度发展。",
            source_title="历史教材",
            source_type="knowledge-base",
        )
    ]

    prompt = build_outline_input(spec, hits)

    assert "工业革命" in prompt
    assert "理解蒸汽机与工厂制度的关系" in prompt
    assert "历史教材" in prompt


def test_merge_outline_draft_builds_valid_outline() -> None:
    draft = PlannerOutlineDraft(
        title="工业革命 lesson outline",
        summary="基于证据生成的约束版大纲。",
        sections=[
            PlannerOutlineSectionDraft(
                title="课程导入",
                goal="唤起已有认知",
                bullet_points=["工业革命背景", "蒸汽机线索"],
                estimated_slides=1,
                recommended_slide_type="cover",
            ),
            PlannerOutlineSectionDraft(
                title="核心概念",
                goal="理解蒸汽机与工厂制度的关系",
                bullet_points=["蒸汽机推动工厂制度形成"],
                estimated_slides=2,
                recommended_slide_type="concept",
            ),
        ],
        design_keywords=["学术", "简洁"],
    )

    outline = merge_outline_draft(draft)

    assert outline.title == "工业革命 lesson outline"
    assert outline.sections[0].recommended_slide_type.value == "cover"
    assert outline.sections[1].recommended_slide_type.value == "concept"
    assert outline.total_slides == 3


def test_openai_planner_ready_requires_dedicated_gateway_settings() -> None:
    disabled = Settings(
        app_name="Teaching Agent",
        app_env="test",
        debug=True,
        api_prefix="/api",
        openai_api_key="sk-dialog",
        openai_base_url="https://dialog.example/v1",
        default_chat_model="gpt-5.4",
        use_openai_dialog=True,
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
    enabled = Settings(
        **{
            **disabled.__dict__,
            "use_openai_planner": True,
            "planner_api_key": "sk-planner",
            "planner_base_url": "https://planner.example/v1",
            "planner_model": "gemini-3.1-pro-preview",
        }
    )
    slide_enabled = Settings(
        **{
            **disabled.__dict__,
            "use_openai_slide_planner": True,
            "slide_planner_api_key": "sk-slide",
            "slide_planner_base_url": "https://slide.example/v1",
            "slide_planner_model": "gemini-3.1-pro-preview",
        }
    )
    speaker_notes_enabled = Settings(
        **{
            **disabled.__dict__,
            "use_openai_speaker_notes": True,
            "speaker_notes_api_key": "sk-notes",
            "speaker_notes_base_url": "https://notes.example/v1",
            "speaker_notes_model": "gemini-3.1-pro-preview",
        }
    )

    assert openai_planner_ready(disabled) is False
    assert openai_planner_ready(enabled) is True
    assert openai_slide_planner_ready(disabled) is False
    assert openai_slide_planner_ready(slide_enabled) is True
    assert openai_speaker_notes_ready(disabled) is False
    assert openai_speaker_notes_ready(speaker_notes_enabled) is True


def test_build_slide_plan_input_contains_outline_and_hits() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
    )
    outline = LessonOutline(
        title="工业革命 lesson outline",
        sections=[
            LessonOutlineSection(
                title="核心概念",
                goal="理解蒸汽机与工厂制度的关系",
                bullet_points=["蒸汽机推动工厂制度形成"],
                estimated_slides=2,
                recommended_slide_type=SlideType.CONCEPT,
            )
        ],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            content="工业革命推动蒸汽机和工厂制度发展。",
            source_title="历史教材",
            source_type="knowledge-base",
        )
    ]

    prompt = build_slide_plan_input(spec, outline, hits)

    assert "工业革命 lesson outline" in prompt
    assert "核心概念" in prompt
    assert "历史教材" in prompt


def test_slide_plan_draft_model_accepts_valid_slide_payload() -> None:
    draft = SlidePlanDraft(
        title="工业革命 slide plan",
        theme_hint="学术",
        slides=[
            SlidePlanSlideDraft(
                section_title="课程导入",
                title="工业革命导入",
                goal="建立工业革命的整体认知",
                slide_type="cover",
                key_points=["工业革命背景", "课堂任务"],
                interaction_mode="none",
                layout_hint="左文右图",
            )
        ],
    )

    assert draft.title == "工业革命 slide plan"
    assert draft.slides[0].slide_type == "cover"


def test_build_speaker_notes_input_contains_current_notes_and_evidence() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
    )
    slide = SlidePlanSlideDraft(
        section_title="核心概念",
        title="蒸汽机与工厂制度",
        goal="说明蒸汽机如何改变生产组织",
        slide_type="concept",
        key_points=["蒸汽机提升生产效率", "工厂制度改变劳动组织"],
        speaker_notes=["先引导学生观察教材证据，再解释工厂制度变化。"],
        interaction_mode="none",
        layout_hint="左文右图",
    )
    from app.models import SlidePlanItem, SlideType, InteractionMode, RetrievalHit

    rendered_slide = SlidePlanItem(
        slide_number=2,
        title=slide.title,
        goal=slide.goal,
        slide_type=SlideType.CONCEPT,
        key_points=slide.key_points,
        speaker_notes=slide.speaker_notes,
        interaction_mode=InteractionMode.NONE,
    )
    hits = {
        2: [
            RetrievalHit(
                chunk_id="hist-1",
                content="蒸汽机推动工厂制度形成并提高生产效率。",
                source_title="历史教材",
                source_type="knowledge-base",
            )
        ]
    }

    prompt = build_speaker_notes_input(spec, [rendered_slide], hits)

    assert "蒸汽机与工厂制度" in prompt
    assert "先引导学生观察教材证据" in prompt
    assert "历史教材" in prompt


def test_speaker_notes_draft_model_accepts_valid_payload() -> None:
    draft = SpeakerNotesDeckDraft(
        slides=[
            SpeakerNotesSlideDraft(
                slide_number=2,
                speaker_notes=["先用教材证据导入，再点明蒸汽机与工厂制度的关系。"],
            )
        ]
    )

    assert draft.slides[0].slide_number == 2
    assert "蒸汽机" in draft.slides[0].speaker_notes[0]
