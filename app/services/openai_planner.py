from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import LessonOutline, LessonOutlineSection, RetrievalHit, SlideType, TeachingSpec
from app.models.schemas import AppModel


PLANNER_SYSTEM_PROMPT = """
你是教学课件策划助手，负责根据教学需求和证据生成课程大纲 LessonOutline。

要求：
1. 只能基于已给出的教学需求和证据生成，不要补写未提供的新事实。
2. 如果证据不足，要在 bullet_points 里明确写出“待补充”，不要假装完整。
3. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
4. sections 保持 4 到 6 个，结构要适合教学演示。
5. recommended_slide_type 只能使用：
   cover, agenda, concept, timeline, comparison, process, media, activity, summary, assignment
6. estimated_slides 必须是正整数。
7. summary 要简短说明这份大纲如何受证据和约束控制。
""".strip()

PLANNER_FALLBACK_SYSTEM_PROMPT = """
你是教学课件策划助手。请基于需求和证据返回一个 JSON 大纲。
只返回 JSON，不要解释，不要补写未提供的新事实。
sections 控制在 4 到 5 个。
recommended_slide_type 只能使用：
cover, agenda, concept, timeline, comparison, process, media, activity, summary, assignment
""".strip()


SLIDE_TYPE_ALIASES = {
    "cover": SlideType.COVER,
    "agenda": SlideType.AGENDA,
    "concept": SlideType.CONCEPT,
    "timeline": SlideType.TIMELINE,
    "comparison": SlideType.COMPARISON,
    "process": SlideType.PROCESS,
    "media": SlideType.MEDIA,
    "activity": SlideType.ACTIVITY,
    "summary": SlideType.SUMMARY,
    "assignment": SlideType.ASSIGNMENT,
    "封面": SlideType.COVER,
    "目录": SlideType.AGENDA,
    "概念": SlideType.CONCEPT,
    "时间线": SlideType.TIMELINE,
    "对比": SlideType.COMPARISON,
    "流程": SlideType.PROCESS,
    "媒体": SlideType.MEDIA,
    "活动": SlideType.ACTIVITY,
    "总结": SlideType.SUMMARY,
    "作业": SlideType.ASSIGNMENT,
}


class PlannerOutlineSectionDraft(AppModel):
    title: str
    goal: str
    bullet_points: list[str] = Field(default_factory=list)
    estimated_slides: int = Field(default=1, ge=1, le=8)
    recommended_slide_type: str = "concept"


class PlannerOutlineDraft(AppModel):
    title: str
    summary: str | None = None
    sections: list[PlannerOutlineSectionDraft] = Field(default_factory=list)
    design_keywords: list[str] = Field(default_factory=list)


def openai_planner_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.use_openai_planner
        and settings.planner_api_key
        and settings.planner_model
    )


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_retrieval_payload(hits: list[RetrievalHit], limit: int = 6) -> list[dict[str, str | float | None]]:
    payload: list[dict[str, str | float | None]] = []
    for hit in hits[:limit]:
        payload.append(
            {
                "source_type": hit.source_type,
                "source_title": hit.source_title or hit.source_filename or hit.page_label,
                "page_label": hit.page_label,
                "topic_hint": hit.topic_hint,
                "score": hit.score,
                "content": _normalize_text(hit.content)[:150],
            }
        )
    return payload


def build_outline_input(spec: TeachingSpec, retrieval_hits: list[RetrievalHit]) -> str:
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
        "请生成一份 LessonOutline。\n"
        "返回字段：title, summary, sections, design_keywords。\n"
        "其中 sections 每项字段：title, goal, bullet_points, estimated_slides, recommended_slide_type。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"已选证据：\n{json.dumps(_build_retrieval_payload(retrieval_hits), ensure_ascii=False)}\n"
    )


def _normalize_slide_type(value: str | None) -> SlideType:
    normalized = _normalize_text(value).lower()
    return SLIDE_TYPE_ALIASES.get(normalized, SlideType.CONCEPT)


def _clean_text_list(items: list[str], *, limit: int = 5) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        candidate = _normalize_text(item).strip("，,。；;：: ")
        if not candidate or candidate in cleaned:
            continue
        cleaned.append(candidate)
        if len(cleaned) >= limit:
            break
    return cleaned


def merge_outline_draft(draft: PlannerOutlineDraft) -> LessonOutline:
    sections = [
        LessonOutlineSection(
            title=_normalize_text(section.title) or "未命名章节",
            goal=_normalize_text(section.goal) or "待补充本节目标",
            bullet_points=_clean_text_list(section.bullet_points, limit=4) or ["待补充本节证据与要点"],
            estimated_slides=max(1, int(section.estimated_slides)),
            recommended_slide_type=_normalize_slide_type(section.recommended_slide_type),
        )
        for section in draft.sections
    ]
    if not sections:
        raise ValueError("Planner returned no outline sections")

    return LessonOutline(
        title=_normalize_text(draft.title) or "Untitled lesson outline",
        summary=_normalize_text(draft.summary) or None,
        sections=sections,
        design_keywords=_clean_text_list(draft.design_keywords, limit=6),
    )


def _post_outline_request(
    settings: Settings,
    *,
    system_prompt: str,
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    max_tokens: int,
) -> PlannerOutlineDraft:
    endpoint = (
        f"{settings.planner_base_url.rstrip('/')}/chat/completions"
        if settings.planner_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.planner_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_outline_input(spec, retrieval_hits)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.planner_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.planner_timeout_seconds) as client:
        response = client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    payload = json.loads(_strip_json_fence(raw_content))
    return PlannerOutlineDraft.model_validate(payload)


def _request_outline(settings: Settings, spec: TeachingSpec, retrieval_hits: list[RetrievalHit]) -> PlannerOutlineDraft:
    try:
        return _post_outline_request(
            settings,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            spec=spec,
            retrieval_hits=retrieval_hits,
            max_tokens=1200,
        )
    except Exception:
        reduced_hits = retrieval_hits[:1]
        return _post_outline_request(
            settings,
            system_prompt=PLANNER_FALLBACK_SYSTEM_PROMPT,
            spec=spec,
            retrieval_hits=reduced_hits,
            max_tokens=800,
        )


def generate_lesson_outline_with_openai(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    *,
    settings: Settings | None = None,
) -> LessonOutline:
    settings = settings or get_settings()
    draft = _request_outline(settings, spec, retrieval_hits)
    return merge_outline_draft(draft)
