from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import RetrievalHit, SessionState
from app.services.evidence import (
    get_selected_retrieval_hits,
    refresh_session_retrieval_hits,
    set_excluded_retrieval_hits,
)
from app.services.storage import session_store


router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceRefreshRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=8, ge=1, le=30)
    use_web_search: bool | None = None


class EvidenceSelectionRequest(BaseModel):
    session_id: str
    excluded_chunk_ids: list[str] = Field(default_factory=list)


class EvidenceResponse(BaseModel):
    session_id: str
    retrieval_hits: list[RetrievalHit]
    selected_hits: list[RetrievalHit]
    selected_count: int
    total_count: int
    session: SessionState


def _build_response(session: SessionState) -> EvidenceResponse:
    selected_hits = get_selected_retrieval_hits(session)
    return EvidenceResponse(
        session_id=session.session_id,
        retrieval_hits=session.retrieval_hits,
        selected_hits=selected_hits,
        selected_count=len(selected_hits),
        total_count=len(session.retrieval_hits),
        session=session,
    )


@router.post("/refresh", response_model=EvidenceResponse)
def refresh_evidence(payload: EvidenceRefreshRequest) -> EvidenceResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")

    try:
        session = refresh_session_retrieval_hits(
            session,
            store_namespace=payload.store_namespace,
            top_k=payload.top_k,
            use_web_search=payload.use_web_search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_store.save(session)
    return _build_response(session)


@router.post("/selection", response_model=EvidenceResponse)
def update_evidence_selection(payload: EvidenceSelectionRequest) -> EvidenceResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session = set_excluded_retrieval_hits(session, payload.excluded_chunk_ids)
    session_store.save(session)
    return _build_response(session)
