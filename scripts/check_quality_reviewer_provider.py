from __future__ import annotations

import json

from app.config import get_settings
from app.models import Citation, InteractionMode, QualityIssue, RetrievalHit, SessionState, SlidePlan, SlidePlanItem, SlideType, TeachingSpec
from app.services.openai_quality_review import (
    openai_quality_review_ready,
    review_quality_with_openai,
)


def main() -> int:
    settings = get_settings()
    if not openai_quality_review_ready(settings):
        print("quality review provider is not enabled")
        return 1

    session = SessionState(
        title="Quality Review Demo",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            class_duration_minutes=45,
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
            additional_requirements=["只使用上传资料和检索命中", "加入材料分析和课堂讨论"],
        ),
        retrieval_hits=[
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
        ],
        slide_plan=SlidePlan(
            title="工业革命 slide plan",
            slides=[
                SlidePlanItem(
                    slide_number=1,
                    title="工业革命导入",
                    slide_type=SlideType.COVER,
                    goal="建立工业革命的整体认知",
                    key_points=["工业革命背景", "本课任务"],
                ),
                SlidePlanItem(
                    slide_number=2,
                    title="核心概念",
                    slide_type=SlideType.CONCEPT,
                    goal="理解蒸汽机与工厂制度的关系",
                    key_points=["蒸汽机推动工厂制度形成"],
                    citations=[Citation(asset_id="hist-1", chunk_id="hist-1", note="历史教材第12页")],
                ),
                SlidePlanItem(
                    slide_number=3,
                    title="课堂讨论",
                    slide_type=SlideType.ACTIVITY,
                    goal="讨论工业革命的社会影响",
                    interaction_mode=InteractionMode.DISCUSSION,
                    key_points=["结合史料讨论工业革命的社会影响"],
                    citations=[Citation(asset_id="hist-2", chunk_id="hist-2", note="课堂史料摘录")],
                ),
            ],
        ),
    )
    session.planning_confirmation.confirmed = True
    rule_issues = [
        QualityIssue(
            severity="low",
            code="missing_citation",
            message="该页缺少引用标签，建议补资料来源。",
            slide_number=1,
        )
    ]
    review = review_quality_with_openai(
        session,
        session.retrieval_hits,
        rule_issues,
        settings=settings,
    )
    print(
        json.dumps(
            {
                "summary": review.summary,
                "issues": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "slide_number": issue.slide_number,
                    }
                    for issue in review.issues
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
