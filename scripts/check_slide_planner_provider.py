from __future__ import annotations

import json

from app.config import get_settings
from app.models import LessonOutline, LessonOutlineSection, RetrievalHit, SlideType, TeachingSpec
from app.services.openai_slide_planner import (
    generate_slide_plan_draft_with_openai,
    openai_slide_planner_ready,
)


def main() -> int:
    settings = get_settings()
    if not openai_slide_planner_ready(settings):
        print("slide planner provider is not enabled")
        return 1

    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        class_duration_minutes=45,
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        additional_requirements=["只使用上传资料和检索命中", "加入材料分析和课堂讨论"],
    )
    outline = LessonOutline(
        title="工业革命 lesson outline",
        summary="基于证据生成的大纲。",
        sections=[
            LessonOutlineSection(
                title="课程导入",
                goal="建立工业革命的整体认知",
                bullet_points=["工业革命背景", "课时任务"],
                estimated_slides=1,
                recommended_slide_type=SlideType.COVER,
            ),
            LessonOutlineSection(
                title="核心概念",
                goal="理解蒸汽机与工厂制度的关系",
                bullet_points=["蒸汽机推动生产效率提升", "工厂制度改变劳动组织"],
                estimated_slides=2,
                recommended_slide_type=SlideType.CONCEPT,
            ),
            LessonOutlineSection(
                title="史料分析与讨论",
                goal="基于材料分析工业革命的社会影响",
                bullet_points=["材料分析", "课堂讨论"],
                estimated_slides=2,
                recommended_slide_type=SlideType.ACTIVITY,
            ),
        ],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
            source_type="knowledge-base",
            source_title="历史教材第12页",
        ),
        RetrievalHit(
            chunk_id="hist-2",
            content="史料材料显示工厂制度改变了劳动组织方式，并带来新的社会问题。",
            source_type="session-file",
            source_title="课堂史料摘录",
        ),
    ]
    draft = generate_slide_plan_draft_with_openai(spec, outline, hits, settings=settings)
    print(
        json.dumps(
            {
                "title": draft.title,
                "theme_hint": draft.theme_hint,
                "slide_count": len(draft.slides),
                "slides": [
                    {
                        "section_title": slide.section_title,
                        "title": slide.title,
                        "goal": slide.goal,
                        "slide_type": slide.slide_type,
                        "interaction_mode": slide.interaction_mode,
                        "key_points": slide.key_points,
                    }
                    for slide in draft.slides
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
