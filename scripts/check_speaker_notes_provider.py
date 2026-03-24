from __future__ import annotations

import json

from app.config import get_settings
from app.models import InteractionMode, RetrievalHit, SlidePlanItem, SlideType, TeachingSpec
from app.services.openai_speaker_notes import (
    openai_speaker_notes_ready,
    polish_speaker_notes_with_openai,
)


def main() -> None:
    settings = get_settings()
    if not openai_speaker_notes_ready(settings):
        raise SystemExit("speaker notes provider is not configured")

    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        class_duration_minutes=45,
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        additional_requirements=["只使用上传资料和检索命中"],
    )
    slide = SlidePlanItem(
        slide_number=2,
        title="蒸汽机与工厂制度",
        goal="说明蒸汽机如何推动工厂制度形成",
        slide_type=SlideType.CONCEPT,
        key_points=["蒸汽机提高生产效率", "工厂制度改变劳动组织"],
        speaker_notes=["先带学生观察教材证据，再说明工厂制度变化。"],
        interaction_mode=InteractionMode.NONE,
    )
    hits = {
        2: [
            RetrievalHit(
                chunk_id="hist-1",
                content="蒸汽机推动工厂制度形成，并显著提升生产效率。",
                source_type="knowledge-base",
                source_title="历史教材",
                topic_hint="蒸汽机与工厂制度",
            )
        ]
    }

    draft = polish_speaker_notes_with_openai(
        spec,
        [slide],
        hits,
        settings=settings,
    )
    print(
        json.dumps(
            draft.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
