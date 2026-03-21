from app.models import (
    ClarificationQuestion,
    InteractionMode,
    LessonOutline,
    LessonOutlineSection,
    ResourceType,
    SlidePlan,
    SlidePlanItem,
    SlideType,
    TeachingSpec,
    build_empty_session,
)


def test_teaching_spec_flags_clarification_when_questions_exist() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="Industrial Revolution",
        unresolved_questions=[
            ClarificationQuestion(
                prompt="What is the lesson duration?",
                reason="The deck length depends on class time.",
            )
        ],
    )
    assert spec.needs_clarification is True


def test_lesson_outline_computes_total_slides() -> None:
    outline = LessonOutline(
        title="Linear Function lesson",
        sections=[
            LessonOutlineSection(
                title="Introduction",
                goal="Set context",
                estimated_slides=1,
                recommended_slide_type=SlideType.COVER,
            ),
            LessonOutlineSection(
                title="Core concept",
                goal="Explain linear functions",
                estimated_slides=3,
                recommended_slide_type=SlideType.CONCEPT,
            ),
        ],
    )
    assert outline.total_slides == 4


def test_slide_plan_computes_total_slides() -> None:
    plan = SlidePlan(
        title="English reading lesson deck",
        slides=[
            SlidePlanItem(
                slide_number=1,
                slide_type=SlideType.COVER,
                title="Reading Strategies",
                goal="Introduce the lesson",
            ),
            SlidePlanItem(
                slide_number=2,
                slide_type=SlideType.ACTIVITY,
                title="Quick quiz",
                goal="Check prior knowledge",
                interaction_mode=InteractionMode.QUIZ,
            ),
        ],
    )
    assert plan.total_slides == 2


def test_empty_session_defaults_are_safe() -> None:
    session = build_empty_session("Cross-subject demo")
    assert session.title == "Cross-subject demo"
    assert session.stage.value == "intake"
    assert session.uploaded_files == []


def test_reference_asset_enum_round_trip() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="Industrial Revolution",
        references=[
            {
                "name": "reference.pdf",
                "resource_type": ResourceType.PDF,
            }
        ],
    )
    assert spec.references[0].resource_type == ResourceType.PDF
