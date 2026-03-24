from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import RetrievalHit, SlidePlanItem, TeachingSpec
from app.models.schemas import AppModel


SLIDE_REGENERATION_SYSTEM_PROMPT = """
你是教学课件单页改写助手，负责只重写当前这一页。

要求：
1. 只能基于给出的教学需求、当前页内容、当前页证据和修改指令生成，不要补写未提供的新事实。
2. 不要改动整套课件结构，只处理当前页。
3. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
4. slide_type 只能使用：
   cover, agenda, concept, timeline, comparison, process, media, activity, summary, assignment
5. interaction_mode 只能使用：
   none, discussion, quiz, exercise, experiment, debate, project
6. key_points / visual_brief / speaker_notes 每项最多 4 条。
7. 如果当前页证据不足，要优先保留原页内容，并在 revision_notes 里明确提示，不要自己扩写新知识。
8. revision_notes 只写约束、修改方向或风险提示。
9. 如果修改指令明确要求改成讨论页、活动页、任务页或练习页，要同步调整 slide_type，而不是只改 interaction_mode。
""".strip()

SLIDE_REGENERATION_FALLBACK_SYSTEM_PROMPT = """
你是教学课件单页改写助手。请基于当前页和已给证据返回 JSON。
只返回 JSON，不要解释，不要补写未提供的新事实。
""".strip()


class SlideRegenerationDraft(AppModel):
    title: str | None = None
    goal: str | None = None
    slide_type: str | None = None
    key_points: list[str] = Field(default_factory=list)
    visual_brief: list[str] = Field(default_factory=list)
    speaker_notes: list[str] = Field(default_factory=list)
    interaction_mode: str | None = None
    layout_hint: str | None = None
    revision_notes: list[str] = Field(default_factory=list)


def openai_slide_regenerator_ready(settings: Settings | None = None) -> bool:
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


def _build_retrieval_payload(hits: list[RetrievalHit], limit: int = 4) -> list[dict[str, str | float | None]]:
    payload: list[dict[str, str | float | None]] = []
    for hit in hits[:limit]:
        payload.append(
            {
                "chunk_id": hit.chunk_id,
                "source_type": hit.source_type,
                "source_title": hit.source_title or hit.source_filename or hit.page_label,
                "page_label": hit.page_label,
                "topic_hint": hit.topic_hint,
                "score": hit.score,
                "content": _normalize_text(hit.content)[:180],
            }
        )
    return payload


def _build_current_slide_payload(slide: SlidePlanItem) -> dict[str, object]:
    return {
        "slide_number": slide.slide_number,
        "slide_type": slide.slide_type.value,
        "title": slide.title,
        "goal": slide.goal,
        "template_id": slide.template_id,
        "key_points": slide.key_points,
        "visual_brief": slide.visual_brief,
        "speaker_notes": slide.speaker_notes,
        "interaction_mode": slide.interaction_mode.value,
        "layout_hint": slide.layout_hint,
        "revision_notes": slide.revision_notes,
        "citations": [
            {
                "asset_id": citation.asset_id,
                "chunk_id": citation.chunk_id,
                "page_label": citation.page_label,
                "note": citation.note,
                "source_type": citation.source_type,
                "source_url": citation.source_url,
            }
            for citation in slide.citations
        ],
    }


def build_slide_regeneration_input(
    spec: TeachingSpec,
    current_slide: SlidePlanItem,
    retrieval_hits: list[RetrievalHit],
    *,
    instructions: str | None = None,
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
        "interaction_preferences": [item.value for item in spec.interaction_preferences],
        "style_preferences": spec.style_preferences,
        "additional_requirements": spec.additional_requirements,
    }
    return (
        "请只重写当前这一页，不要改动整套课件结构。\n"
        "返回字段：title, goal, slide_type, key_points, visual_brief, speaker_notes, "
        "interaction_mode, layout_hint, revision_notes。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"当前页：\n{json.dumps(_build_current_slide_payload(current_slide), ensure_ascii=False)}\n\n"
        f"当前页证据：\n{json.dumps(_build_retrieval_payload(retrieval_hits), ensure_ascii=False)}\n\n"
        f"修改指令：{_normalize_text(instructions) or '在当前证据范围内优化本页表达与结构。'}\n"
    )


def _post_slide_regeneration_request(
    settings: Settings,
    *,
    system_prompt: str,
    spec: TeachingSpec,
    current_slide: SlidePlanItem,
    retrieval_hits: list[RetrievalHit],
    instructions: str | None,
    max_tokens: int,
) -> SlideRegenerationDraft:
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
            {
                "role": "user",
                "content": build_slide_regeneration_input(
                    spec,
                    current_slide,
                    retrieval_hits,
                    instructions=instructions,
                ),
            },
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
    parsed = json.loads(_strip_json_fence(raw_content))
    return SlideRegenerationDraft.model_validate(parsed)


def _request_slide_regeneration(
    settings: Settings,
    spec: TeachingSpec,
    current_slide: SlidePlanItem,
    retrieval_hits: list[RetrievalHit],
    *,
    instructions: str | None = None,
) -> SlideRegenerationDraft:
    try:
        return _post_slide_regeneration_request(
            settings,
            system_prompt=SLIDE_REGENERATION_SYSTEM_PROMPT,
            spec=spec,
            current_slide=current_slide,
            retrieval_hits=retrieval_hits,
            instructions=instructions,
            max_tokens=1200,
        )
    except Exception:
        return _post_slide_regeneration_request(
            settings,
            system_prompt=SLIDE_REGENERATION_FALLBACK_SYSTEM_PROMPT,
            spec=spec,
            current_slide=current_slide,
            retrieval_hits=retrieval_hits[:2],
            instructions=instructions,
            max_tokens=800,
        )


def generate_slide_regeneration_draft_with_openai(
    spec: TeachingSpec,
    current_slide: SlidePlanItem,
    retrieval_hits: list[RetrievalHit],
    *,
    instructions: str | None = None,
    settings: Settings | None = None,
) -> SlideRegenerationDraft:
    settings = settings or get_settings()
    return _request_slide_regeneration(
        settings,
        spec,
        current_slide,
        retrieval_hits,
        instructions=instructions,
    )
