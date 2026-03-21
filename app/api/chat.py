from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.models import SessionState, TeachingSpec
from app.services.dialog import process_user_message
from app.services.storage import session_store


router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    title: str = "Untitled Session"


class ChatMessageRequest(BaseModel):
    session_id: str | None = None
    title: str = "Untitled Session"
    content: str = Field(min_length=1)
    use_web_search: bool | None = None


class ChatMessageResponse(BaseModel):
    session_id: str
    stage: str
    assistant_message: str
    teaching_spec: TeachingSpec | None
    session: SessionState


@router.post("/sessions", response_model=SessionState)
def create_session(payload: CreateSessionRequest) -> SessionState:
    return session_store.create_session(title=payload.title)


@router.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/messages", response_model=ChatMessageResponse)
def post_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    session = session_store.get(payload.session_id) if payload.session_id else None
    if session is None:
        session = session_store.create_session(title=payload.title)

    session, assistant_message = process_user_message(
        session,
        payload.content,
        use_web_search=payload.use_web_search,
    )
    session_store.save(session)

    return ChatMessageResponse(
        session_id=session.session_id,
        stage=session.stage.value,
        assistant_message=assistant_message,
        teaching_spec=session.teaching_spec,
        session=session,
    )
