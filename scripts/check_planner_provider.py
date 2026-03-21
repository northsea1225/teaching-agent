from __future__ import annotations

import json

from app.config import get_settings
from app.models import RetrievalHit, TeachingSpec
from app.services.openai_planner import generate_lesson_outline_with_openai, openai_planner_ready


def main() -> int:
    settings = get_settings()
    if not openai_planner_ready(settings):
        print("planner provider is not enabled")
        return 1

    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        class_duration_minutes=45,
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        additional_requirements=["只使用上传资料和检索命中", "加入材料分析和课堂讨论"],
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
    outline = generate_lesson_outline_with_openai(spec, hits, settings=settings)
    print(
        json.dumps(
            {
                "title": outline.title,
                "summary": outline.summary,
                "section_count": len(outline.sections),
                "sections": [
                    {
                        "title": section.title,
                        "goal": section.goal,
                        "estimated_slides": section.estimated_slides,
                        "recommended_slide_type": (
                            section.recommended_slide_type.value
                            if section.recommended_slide_type
                            else None
                        ),
                        "bullet_points": section.bullet_points,
                    }
                    for section in outline.sections
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
