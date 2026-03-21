from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import LessonOutline, RetrievalHit, TeachingSpec
from app.models.schemas import AppModel


SLIDE_PLAN_SYSTEM_PROMPT = """
你是教学课件逐页策划助手，负责根据教学需求、课程大纲和已选证据生成 SlidePlan 草案。

要求：
1. 只能基于给出的教学需求、课程大纲和证据生成，不要补写未提供的新事实。
2. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
3. slides 必须覆盖课程大纲的核心章节，页数尽量贴近 outline.total_slides。
4. slide_type 只能使用：
   cover, agenda, concept, timeline, comparison, process, media, activity, summary, assignment
5. interaction_mode 只能使用：
   none, discussion, quiz, exercise, experiment, debate, project
6. key_points / visual_brief / speaker_notes 每项最多 4 条；证据不足时用“待补充”明确标注，不要假装完整。
7. layout_hint 用简短中文说明页面布局重点。
8. revision_notes 只写约束或风险提示，不要写解释段落。
""".strip()

SLIDE_PLAN_FALLBACK_SYSTEM_PROMPT = """
你是教学课件逐页策划助手。请基于需求、课程大纲和证据返回 JSON。
只返回 JSON，不要解释，不要补写未提供的新事实。
slide_type 只能使用：
cover, agenda, concept, timeline, comparison, process, media, activity, summary, assignment
interaction_mode 只能使用：
none, discussion, quiz, exercise, experiment, debate, project
""".strip()


class SlidePlanSlideDraft(AppModel):
    section_title: str | None = None
    title: str
    goal: str
    slide_type: str = "concept"
    key_points: list[str] = Field(default_factory=list)
    visual_brief: list[str] = Field(default_factory=list)
    speaker_notes: list[str] = Field(default_factory=list)
    interaction_mode: str = "none"
    layout_hint: str | None = None
    revision_notes: list[str] = Field(default_factory=list)


class SlidePlanDraft(AppModel):
    title: str
    theme_hint: str | None = None
    slides: list[SlidePlanSlideDraft] = Field(default_factory=list)


def openai_slide_planner_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.use_openai_slide_planner
        and settings.slide_planner_api_key
        and settings.slide_planner_model
    )


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_outline_payload(outline: LessonOutline) -> dict[str, object]:
    return {
        "title": outline.title,
        "summary": outline.summary,
        "total_slides": outline.total_slides,
        "design_keywords": outline.design_keywords,
        "sections": [
            {
                "title": section.title,
                "goal": section.goal,
                "bullet_points": section.bullet_points,
                "estimated_slides": section.estimated_slides,
                "recommended_slide_type": (
                    section.recommended_slide_type.value
                    if section.recommended_slide_type
                    else None
                ),
            }
            for section in outline.sections
        ],
    }


def _build_retrieval_payload(hits: list[RetrievalHit], limit: int = 8) -> list[dict[str, str | float | None]]:
    payload: list[dict[str, str | float | None]] = []
    for hit in hits[:limit]:
        payload.append(
            {
                "source_type": hit.source_type,
                "source_title": hit.source_title or hit.source_filename or hit.page_label,
                "page_label": hit.page_label,
                "topic_hint": hit.topic_hint,
                "score": hit.score,
                "content": _normalize_text(hit.content)[:180],
            }
        )
    return payload


def build_slide_plan_input(
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit],
) -> str:
    spec_payload = {
        "education_stage": spec.education_stage,
        "subject": spec.subject,
        "grade_level": spec.grade_level,
        "lesson_title": spec.lesson_title,
        "lesson_topic": spec.lesson_topic,
        "class_duration_minutes": spec.class_duration_minutes,
        "learning_objectives": [item.description for item in spec.learning_objectives],
        "key_difficulties": spec.key_difficulties,
        "teaching_methods": spec.teaching_methods,
        "interaction_preferences": [item.value for item in spec.interaction_preferences],
        "style_preferences": spec.style_preferences,
        "additional_requirements": spec.additional_requirements,
    }
    return (
        "请生成一份 SlidePlan 草案。\n"
        "返回字段：title, theme_hint, slides。\n"
        "其中 slides 每项字段：section_title, title, goal, slide_type, key_points, visual_brief, "
        "speaker_notes, interaction_mode, layout_hint, revision_notes。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"课程大纲：\n{json.dumps(_build_outline_payload(outline), ensure_ascii=False)}\n\n"
        f"已选证据：\n{json.dumps(_build_retrieval_payload(retrieval_hits), ensure_ascii=False)}\n"
    )


def _post_slide_plan_request(
    settings: Settings,
    *,
    system_prompt: str,
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit],
    max_tokens: int,
) -> SlidePlanDraft:
    endpoint = (
        f"{settings.slide_planner_base_url.rstrip('/')}/chat/completions"
        if settings.slide_planner_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.slide_planner_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_slide_plan_input(spec, outline, retrieval_hits)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.slide_planner_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.slide_planner_timeout_seconds) as client:
        response = client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    payload = json.loads(_strip_json_fence(raw_content))
    return SlidePlanDraft.model_validate(payload)


def _request_slide_plan(
    settings: Settings,
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit],
) -> SlidePlanDraft:
    try:
        return _post_slide_plan_request(
            settings,
            system_prompt=SLIDE_PLAN_SYSTEM_PROMPT,
            spec=spec,
            outline=outline,
            retrieval_hits=retrieval_hits,
            max_tokens=2400,
        )
    except Exception:
        return _post_slide_plan_request(
            settings,
            system_prompt=SLIDE_PLAN_FALLBACK_SYSTEM_PROMPT,
            spec=spec,
            outline=outline,
            retrieval_hits=retrieval_hits[:3],
            max_tokens=1400,
        )


def generate_slide_plan_draft_with_openai(
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit],
    *,
    settings: Settings | None = None,
) -> SlidePlanDraft:
    settings = settings or get_settings()
    return _request_slide_plan(settings, spec, outline, retrieval_hits)
