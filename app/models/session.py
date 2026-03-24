from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import Field

from app.models.schemas import (
    AppModel,
    ExportArtifact,
    LessonOutline,
    PreviewDeck,
    ResourceType,
    RetrievalHit,
    SlidePlan,
    SvgDeckSpec,
    TeachingSpec,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStage(str, Enum):
    INTAKE = "intake"
    CLARIFICATION = "clarification"
    PLANNING = "planning"
    PREVIEW = "preview"
    EXPORT = "export"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class SessionFile(AppModel):
    file_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    resource_type: ResourceType
    path: str | None = None
    parsed_path: str | None = None
    summary: str | None = None
    parse_status: str = "pending"
    parse_error: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    uploaded_at: datetime = Field(default_factory=utc_now)


class SessionMessage(AppModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class ConfirmationItem(AppModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    status: str = "missing"
    detail: str | None = None
    required: bool = True


class PlanningConfirmation(AppModel):
    confirmed: bool = False
    required: bool = True
    summary: str | None = None
    items: list[ConfirmationItem] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    confirmed_note: str | None = None
    confirmed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class QualityIssue(AppModel):
    issue_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: str
    code: str
    message: str
    origin: str = "rule"
    slide_number: int | None = None


class QualityReport(AppModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    score: int = 0
    summary: str | None = None
    issues: list[QualityIssue] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utc_now)


class SessionState(AppModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "Untitled Session"
    stage: SessionStage = SessionStage.INTAKE
    subject_family: str | None = None
    workspace_path: str | None = None
    web_search_enabled: bool = False
    uploaded_files: list[SessionFile] = Field(default_factory=list)
    messages: list[SessionMessage] = Field(default_factory=list)
    teaching_spec: TeachingSpec | None = None
    planning_confirmation: PlanningConfirmation = Field(default_factory=PlanningConfirmation)
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    excluded_retrieval_chunk_ids: list[str] = Field(default_factory=list)
    outline: LessonOutline | None = None
    slide_plan: SlidePlan | None = None
    svg_theme_id: str = "academy"
    svg_font_preset: str = "classroom"
    svg_deck: SvgDeckSpec | None = None
    preview_deck: PreviewDeck | None = None
    quality_report: QualityReport | None = None
    export_artifacts: list[ExportArtifact] = Field(default_factory=list)
    last_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


def build_empty_session(title: str = "Untitled Session") -> SessionState:
    return SessionState(title=title)
