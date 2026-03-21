from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.models import RetrievalHit
from app.services.rag import LocalKnowledgeBase


router = APIRouter(prefix="/kb", tags=["knowledge-base"])


class IngestRequest(BaseModel):
    source_dir: str | None = None
    include_parsed_assets: bool = False
    session_id: str | None = None
    reset: bool = False
    store_namespace: str | None = None


class IngestResponse(BaseModel):
    store_dir: str
    stats: dict[str, int | str | list[str]]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    store_namespace: str | None = None
    subject_filter: list[str] = Field(default_factory=list)
    stage_filter: list[str] = Field(default_factory=list)
    topic_keywords: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    hits: list[RetrievalHit]
    count: int


@router.post("/ingest", response_model=IngestResponse)
def ingest_knowledge_base(payload: IngestRequest) -> IngestResponse:
    kb = LocalKnowledgeBase(namespace=payload.store_namespace)
    stats = kb.ingest_default_sources(
        source_dir=payload.source_dir,
        include_parsed_assets=payload.include_parsed_assets,
        session_id=payload.session_id,
        reset=payload.reset,
    )
    return IngestResponse(store_dir=str(kb.store_dir), stats=stats)


@router.post("/search", response_model=SearchResponse)
def search_knowledge_base(payload: SearchRequest) -> SearchResponse:
    kb = LocalKnowledgeBase(namespace=payload.store_namespace)
    hits = kb.search(
        payload.query,
        top_k=payload.top_k,
        subject_filter=payload.subject_filter or None,
        stage_filter=payload.stage_filter or None,
        topic_keywords=payload.topic_keywords or None,
    )
    return SearchResponse(hits=hits, count=len(hits))
