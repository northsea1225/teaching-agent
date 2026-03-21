from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import SessionState, SlidePlan, SvgDeckSpec
from app.services.storage import session_store
from app.services.svg import generate_svg_deck_for_session


router = APIRouter(prefix="/svg", tags=["svg"])


class SvgDeckRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    theme_id: str | None = None
    font_preset: str | None = None


class SvgDeckResponse(BaseModel):
    session_id: str
    slide_plan: SlidePlan
    svg_deck: SvgDeckSpec
    session: SessionState


@router.post("/deck", response_model=SvgDeckResponse)
def create_svg_deck(payload: SvgDeckRequest) -> SvgDeckResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")
    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")

    updated_session = generate_svg_deck_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
        theme_id=payload.theme_id,
        font_preset=payload.font_preset,
    )
    session_store.save(updated_session)

    assert updated_session.slide_plan is not None
    assert updated_session.svg_deck is not None
    return SvgDeckResponse(
        session_id=updated_session.session_id,
        slide_plan=updated_session.slide_plan,
        svg_deck=updated_session.svg_deck,
        session=updated_session,
    )
