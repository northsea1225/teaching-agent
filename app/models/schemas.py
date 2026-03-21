from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ResourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    URL = "url"


class InteractionMode(str, Enum):
    NONE = "none"
    DISCUSSION = "discussion"
    QUIZ = "quiz"
    EXERCISE = "exercise"
    EXPERIMENT = "experiment"
    DEBATE = "debate"
    PROJECT = "project"


class SlideType(str, Enum):
    COVER = "cover"
    AGENDA = "agenda"
    CONCEPT = "concept"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    PROCESS = "process"
    MEDIA = "media"
    ACTIVITY = "activity"
    SUMMARY = "summary"
    ASSIGNMENT = "assignment"


class ReferenceAsset(AppModel):
    asset_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    resource_type: ResourceType
    source_path: str | None = None
    usage_hint: str | None = None
    topic_scope: str | None = None
    notes: str | None = None


class ClarificationQuestion(AppModel):
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    reason: str
    required: bool = True


class LearningObjective(AppModel):
    objective_id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    category: str = "general"


class KnowledgePoint(AppModel):
    point_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    importance: str = "core"
    prerequisites: list[str] = Field(default_factory=list)


class RetrievalHit(AppModel):
    chunk_id: str
    asset_id: str | None = None
    content: str
    score: float | None = None
    page_label: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_path: str | None = None
    source_filename: str | None = None
    subject_tag: str | None = None
    stage_tag: str | None = None
    topic_hint: str | None = None


class ParsedAsset(AppModel):
    parsed_id: str = Field(default_factory=lambda: str(uuid4()))
    resource_type: ResourceType
    source_path: str
    extracted_text: str = ""
    text_preview: str = ""
    page_count: int | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class TeachingSpec(AppModel):
    spec_id: str = Field(default_factory=lambda: str(uuid4()))
    education_stage: str | None = None
    subject: str | None = None
    grade_level: str | None = None
    textbook_version: str | None = None
    lesson_title: str | None = None
    lesson_topic: str | None = None
    language: str = "zh-CN"
    class_duration_minutes: PositiveInt = 45
    lesson_count: PositiveInt = 1
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    core_knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    key_difficulties: list[str] = Field(default_factory=list)
    teaching_methods: list[str] = Field(default_factory=list)
    interaction_preferences: list[InteractionMode] = Field(default_factory=list)
    assessment_methods: list[str] = Field(default_factory=list)
    style_preferences: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=lambda: ["pptx", "docx"])
    references: list[ReferenceAsset] = Field(default_factory=list)
    additional_requirements: list[str] = Field(default_factory=list)
    unresolved_questions: list[ClarificationQuestion] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def needs_clarification(self) -> bool:
        return (not self.confirmed) or bool(self.unresolved_questions)


class LessonOutlineSection(AppModel):
    section_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    goal: str
    bullet_points: list[str] = Field(default_factory=list)
    estimated_slides: PositiveInt = 1
    recommended_slide_type: SlideType | None = None


class LessonOutline(AppModel):
    outline_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    summary: str | None = None
    sections: list[LessonOutlineSection] = Field(default_factory=list)
    total_slides: PositiveInt | None = None
    design_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_total_slides(self) -> "LessonOutline":
        estimated_total = sum(section.estimated_slides for section in self.sections)
        if self.total_slides is None:
            self.total_slides = estimated_total or 1
        elif self.total_slides < estimated_total:
            raise ValueError("total_slides cannot be smaller than section estimates")
        return self


class Citation(AppModel):
    asset_id: str
    chunk_id: str | None = None
    page_label: str | None = None
    note: str | None = None
    source_type: str | None = None
    source_url: str | None = None


class SlidePlanItem(AppModel):
    slide_number: PositiveInt
    slide_type: SlideType
    title: str
    goal: str
    template_id: str | None = None
    key_points: list[str] = Field(default_factory=list)
    visual_brief: list[str] = Field(default_factory=list)
    speaker_notes: list[str] = Field(default_factory=list)
    interaction_mode: InteractionMode = InteractionMode.NONE
    citations: list[Citation] = Field(default_factory=list)
    layout_hint: str | None = None
    revision_notes: list[str] = Field(default_factory=list)


class SlidePlan(AppModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    theme_hint: str | None = None
    slides: list[SlidePlanItem] = Field(default_factory=list)
    total_slides: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_total_slides(self) -> "SlidePlan":
        if self.total_slides is None:
            self.total_slides = len(self.slides) or 1
        elif self.total_slides < len(self.slides):
            raise ValueError("total_slides cannot be smaller than the number of slides")
        return self


class PreviewSlide(AppModel):
    slide_number: PositiveInt
    slide_type: SlideType
    title: str
    html: str
    text_blocks: list[str] = Field(default_factory=list)


class PreviewDeck(AppModel):
    preview_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    theme_hint: str | None = None
    slides: list[PreviewSlide] = Field(default_factory=list)
    html_document: str = ""
    generated_at: datetime = Field(default_factory=utc_now)


class ExportArtifact(AppModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    resource_type: ResourceType
    path: str
    summary: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)


class SvgBlockSpec(AppModel):
    block_id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    title: str | None = None
    text_lines: list[str] = Field(default_factory=list)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    accent_color: str | None = None
    background_fill: str = "#ffffff"
    stroke_color: str | None = None
    text_color: str = "#213446"
    title_size: int = Field(default=22, ge=12, le=48)
    body_size: int = Field(default=18, ge=10, le=36)
    corner_radius: int = Field(default=28, ge=0, le=80)
    shape_variant: str = "card"


class SvgSlideSpec(AppModel):
    slide_number: PositiveInt
    title: str
    slide_type: SlideType
    template_id: str | None = None
    width: int = Field(default=1280, gt=0)
    height: int = Field(default=720, gt=0)
    background: str = "#f7fbff"
    accent_color: str = "#16324f"
    soft_color: str = "#d7e6f5"
    text_color: str = "#17202a"
    layout_name: str = "grid"
    style_preset: str = "editorial"
    title_font_family: str = "Segoe UI"
    body_font_family: str = "Segoe UI"
    blocks: list[SvgBlockSpec] = Field(default_factory=list)
    markup: str = ""


class SvgDeckSpec(AppModel):
    deck_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    theme_hint: str | None = None
    theme_id: str = "academy"
    font_preset: str = "classroom"
    finalized: bool = False
    title_font_family: str = "Segoe UI"
    body_font_family: str = "Segoe UI"
    slides: list[SvgSlideSpec] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
