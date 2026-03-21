from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import LessonOutline, PreviewDeck, SessionState, SlidePlan
from app.services.preview import generate_preview_for_session
from app.services.storage import session_store


router = APIRouter(prefix="/preview", tags=["preview"])


class PreviewRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PreviewResponse(BaseModel):
    session_id: str
    outline: LessonOutline
    slide_plan: SlidePlan
    preview: PreviewDeck
    session: SessionState


@router.post("/deck", response_model=PreviewResponse)
def create_preview(payload: PreviewRequest) -> PreviewResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")
    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")

    updated_session = generate_preview_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
    )
    session_store.save(updated_session)

    assert updated_session.outline is not None
    assert updated_session.slide_plan is not None
    assert updated_session.preview_deck is not None
    return PreviewResponse(
        session_id=updated_session.session_id,
        outline=updated_session.outline,
        slide_plan=updated_session.slide_plan,
        preview=updated_session.preview_deck,
        session=updated_session,
    )
