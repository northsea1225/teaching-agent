from __future__ import annotations

import json

from app.config import get_settings
from app.models import Citation, RetrievalHit, SlidePlanItem, SlideType, TeachingSpec
from app.services.openai_slide_regenerator import (
    generate_slide_regeneration_draft_with_openai,
    openai_slide_regenerator_ready,
)


def main() -> int:
    settings = get_settings()
    if not openai_slide_regenerator_ready(settings):
        print("slide regenerator provider is not enabled")
        return 1

    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        class_duration_minutes=45,
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        additional_requirements=["只使用上传资料和检索命中", "加入材料分析和课堂讨论"],
    )
    current_slide = SlidePlanItem(
        slide_number=3,
        title="工业革命核心线索",
        slide_type=SlideType.CONCEPT,
        goal="说明蒸汽机与工厂制度的关系",
        key_points=["蒸汽机推动工厂制度形成", "工厂制度改变劳动组织方式"],
        speaker_notes=["围绕教材第12页讲解蒸汽机与工厂制度的关系。"],
        citations=[
            Citation(asset_id="hist-1", chunk_id="hist-1", note="历史教材第12页"),
        ],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            asset_id="hist-1",
            content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
            source_type="knowledge-base",
            source_title="历史教材第12页",
            topic_hint="蒸汽机与工厂制度",
        ),
        RetrievalHit(
            chunk_id="hist-2",
            asset_id="hist-2",
            content="史料材料显示工厂制度改变了劳动组织方式，并带来新的社会问题。",
            source_type="session-file",
            source_title="课堂史料摘录",
            topic_hint="工厂制度社会影响",
        ),
    ]
    draft = generate_slide_regeneration_draft_with_openai(
        spec,
        current_slide,
        hits,
        instructions="改成更清楚的讨论页，但不要扩展课外史实。",
        settings=settings,
    )
    print(
        json.dumps(
            {
                "title": draft.title,
                "goal": draft.goal,
                "slide_type": draft.slide_type,
                "interaction_mode": draft.interaction_mode,
                "key_points": draft.key_points,
                "visual_brief": draft.visual_brief,
                "speaker_notes": draft.speaker_notes,
                "revision_notes": draft.revision_notes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
