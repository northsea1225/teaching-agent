from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models import (
    InteractionMode,
    LessonOutline,
    PlanningConfirmation,
    QualityReport,
    RetrievalHit,
    SessionState,
    SlidePlan,
    SlideType,
)
from app.services.confirmation import confirm_planning_constraints, refresh_planning_confirmation
from app.services.planner import (
    delete_slide_from_session,
    generate_outline_for_session,
    generate_slide_plan_for_session,
    insert_slide_into_session,
    move_slide_in_session,
    regenerate_slide_in_session,
    update_slide_in_session,
)
from app.services.quality import refresh_quality_report
from app.services.storage import session_store


router = APIRouter(prefix="/planner", tags=["planner"])


class OutlineRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_web_search: bool | None = None


class OutlineResponse(BaseModel):
    session_id: str
    outline: LessonOutline
    retrieval_hits: list[RetrievalHit]
    session: SessionState


class SlidePlanRequest(BaseModel):
    session_id: str
    store_namespace: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_web_search: bool | None = None


class SlidePlanResponse(BaseModel):
    session_id: str
    outline: LessonOutline
    slide_plan: SlidePlan
    retrieval_hits: list[RetrievalHit]
    session: SessionState


class SlidePlanMutationRequest(BaseModel):
    session_id: str


class SlidePlanMutationResponse(BaseModel):
    session_id: str
    slide_plan: SlidePlan
    session: SessionState


class PlanningConfirmationRequest(SlidePlanMutationRequest):
    note: str | None = None


class PlanningConfirmationResponse(BaseModel):
    session_id: str
    planning_confirmation: PlanningConfirmation
    quality_report: QualityReport | None = None
    session: SessionState


class UpdateSlideRequest(SlidePlanMutationRequest):
    slide_number: int = Field(ge=1)
    title: str | None = None
    goal: str | None = None
    slide_type: SlideType | None = None
    key_points: list[str] | None = None
    visual_brief: list[str] | None = None
    speaker_notes: list[str] | None = None
    interaction_mode: InteractionMode | None = None
    layout_hint: str | None = None
    revision_note: str | None = None


class MoveSlideRequest(SlidePlanMutationRequest):
    from_slide_number: int = Field(ge=1)
    to_position: int = Field(ge=1)


class DeleteSlideRequest(SlidePlanMutationRequest):
    slide_number: int = Field(ge=1)


class InsertSlideRequest(SlidePlanMutationRequest):
    position: int = Field(ge=1)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    slide_type: SlideType = SlideType.CONCEPT
    key_points: list[str] = Field(default_factory=list)
    visual_brief: list[str] = Field(default_factory=list)
    speaker_notes: list[str] = Field(default_factory=list)
    interaction_mode: InteractionMode | None = None
    layout_hint: str | None = None
    revision_note: str | None = None


class RegenerateSlideRequest(SlidePlanMutationRequest):
    slide_number: int = Field(ge=1)
    instructions: str | None = None


@router.post("/outline", response_model=OutlineResponse)
def create_outline(payload: OutlineRequest) -> OutlineResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")

    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")
    if payload.use_web_search is not None:
        session.web_search_enabled = payload.use_web_search

    updated_session = generate_outline_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
        use_web_search=session.web_search_enabled,
    )
    session_store.save(updated_session)

    assert updated_session.outline is not None
    return OutlineResponse(
        session_id=updated_session.session_id,
        outline=updated_session.outline,
        retrieval_hits=updated_session.retrieval_hits,
        session=updated_session,
    )


@router.post("/slide-plan", response_model=SlidePlanResponse)
def create_slide_plan(payload: SlidePlanRequest) -> SlidePlanResponse:
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")

    if not session.teaching_spec.subject or not session.teaching_spec.lesson_title:
        raise HTTPException(status_code=400, detail="More subject and lesson details are required")
    if payload.use_web_search is not None:
        session.web_search_enabled = payload.use_web_search

    updated_session = generate_slide_plan_for_session(
        session,
        store_namespace=payload.store_namespace,
        top_k=payload.top_k,
        use_web_search=session.web_search_enabled,
    )
    session_store.save(updated_session)

    assert updated_session.outline is not None
    assert updated_session.slide_plan is not None
    return SlidePlanResponse(
        session_id=updated_session.session_id,
        outline=updated_session.outline,
        slide_plan=updated_session.slide_plan,
        retrieval_hits=updated_session.retrieval_hits,
        session=updated_session,
    )


def _get_session_for_mutation(session_id: str) -> SessionState:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.teaching_spec is None:
        raise HTTPException(status_code=400, detail="Teaching spec is not available yet")
    return session


def _mutation_response(session: SessionState) -> SlidePlanMutationResponse:
    assert session.slide_plan is not None
    return SlidePlanMutationResponse(
        session_id=session.session_id,
        slide_plan=session.slide_plan,
        session=session,
    )


@router.post("/confirmation/refresh", response_model=PlanningConfirmationResponse)
def refresh_confirmation(payload: SlidePlanMutationRequest) -> PlanningConfirmationResponse:
    session = _get_session_for_mutation(payload.session_id)
    session = refresh_planning_confirmation(session)
    session = refresh_quality_report(session)
    session_store.save(session)
    return PlanningConfirmationResponse(
        session_id=session.session_id,
        planning_confirmation=session.planning_confirmation,
        quality_report=session.quality_report,
        session=session,
    )


@router.post("/confirmation/confirm", response_model=PlanningConfirmationResponse)
def confirm_confirmation(payload: PlanningConfirmationRequest) -> PlanningConfirmationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = confirm_planning_constraints(session, note=payload.note)
        session = refresh_quality_report(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return PlanningConfirmationResponse(
        session_id=session.session_id,
        planning_confirmation=session.planning_confirmation,
        quality_report=session.quality_report,
        session=session,
    )


@router.post("/slide-plan/update", response_model=SlidePlanMutationResponse)
def update_slide(payload: UpdateSlideRequest) -> SlidePlanMutationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = update_slide_in_session(
            session,
            payload.slide_number,
            title=payload.title,
            goal=payload.goal,
            slide_type=payload.slide_type,
            key_points=payload.key_points,
            visual_brief=payload.visual_brief,
            speaker_notes=payload.speaker_notes,
            interaction_mode=payload.interaction_mode,
            layout_hint=payload.layout_hint,
            revision_note=payload.revision_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return _mutation_response(session)


@router.post("/slide-plan/move", response_model=SlidePlanMutationResponse)
def move_slide(payload: MoveSlideRequest) -> SlidePlanMutationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = move_slide_in_session(
            session,
            payload.from_slide_number,
            payload.to_position,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return _mutation_response(session)


@router.post("/slide-plan/delete", response_model=SlidePlanMutationResponse)
def delete_slide(payload: DeleteSlideRequest) -> SlidePlanMutationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = delete_slide_from_session(session, payload.slide_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return _mutation_response(session)


@router.post("/slide-plan/insert", response_model=SlidePlanMutationResponse)
def insert_slide(payload: InsertSlideRequest) -> SlidePlanMutationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = insert_slide_into_session(
            session,
            payload.position,
            title=payload.title,
            goal=payload.goal,
            slide_type=payload.slide_type,
            interaction_mode=payload.interaction_mode,
            key_points=payload.key_points or None,
            visual_brief=payload.visual_brief or None,
            speaker_notes=payload.speaker_notes or None,
            layout_hint=payload.layout_hint,
            revision_note=payload.revision_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return _mutation_response(session)


@router.post("/slide-plan/regenerate-slide", response_model=SlidePlanMutationResponse)
def regenerate_slide(payload: RegenerateSlideRequest) -> SlidePlanMutationResponse:
    session = _get_session_for_mutation(payload.session_id)
    try:
        session = regenerate_slide_in_session(
            session,
            payload.slide_number,
            instructions=payload.instructions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.save(session)
    return _mutation_response(session)
