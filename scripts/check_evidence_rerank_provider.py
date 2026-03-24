from __future__ import annotations

import json

from app.config import get_settings
from app.models import RetrievalHit, TeachingSpec
from app.services.openai_evidence_rerank import (
    openai_evidence_rerank_ready,
    rerank_retrieval_hits_with_openai,
)


def main() -> int:
    settings = get_settings()
    if not openai_evidence_rerank_ready(settings):
        print("evidence rerank provider is not enabled")
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
            topic_hint="工业革命教材",
        ),
        RetrievalHit(
            chunk_id="hist-2",
            content="工人生活与工厂纪律变化也影响了社会结构。",
            source_type="session-file",
            source_title="课堂史料摘录",
            topic_hint="工人处境史料",
        ),
        RetrievalHit(
            chunk_id="noise-1",
            content="NaHCO3 受热分解并生成新的物质。",
            source_type="knowledge-base",
            source_title="化学练习册第57页",
            topic_hint="化学练习",
        ),
    ]
    ranked_hits = rerank_retrieval_hits_with_openai(spec, hits, top_k=2, settings=settings)
    print(
        json.dumps(
            {
                "selected_count": len(ranked_hits),
                "hits": [
                    {
                        "chunk_id": hit.chunk_id,
                        "topic_hint": hit.topic_hint,
                        "score": hit.score,
                        "source_title": hit.source_title,
                    }
                    for hit in ranked_hits
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
