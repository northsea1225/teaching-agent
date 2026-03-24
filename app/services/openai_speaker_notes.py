from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import RetrievalHit, SlidePlanItem, TeachingSpec
from app.models.schemas import AppModel


SPEAKER_NOTES_SYSTEM_PROMPT = """
你是教学课件讲稿润色助手，只负责润色 speaker_notes。

要求：
1. 只能基于给出的教学需求、当前页结构、当前页要点和当前页证据润色，不要补写未提供的新事实。
2. 不能改标题、目标、页面类型、关键要点、引用，也不能新增页面。
3. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
4. 每页 speaker_notes 最多 4 条，每条都应简短、自然、适合教师口播。
5. 如果证据不足，只允许重写现有表达或保留“待补充”，不要假装掌握了新材料。
6. 讲稿应优先帮助教师解释 key_points、串联证据和组织课堂提示，而不是重写页面文案。
""".strip()

SPEAKER_NOTES_FALLBACK_SYSTEM_PROMPT = """
你是教学课件讲稿润色助手。请只返回 JSON。
只润色 speaker_notes，不要改动其他字段，不要补写未提供的新事实。
""".strip()


class SpeakerNotesSlideDraft(AppModel):
    slide_number: int
    speaker_notes: list[str] = Field(default_factory=list)


class SpeakerNotesDeckDraft(AppModel):
    slides: list[SpeakerNotesSlideDraft] = Field(default_factory=list)


def openai_speaker_notes_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.use_openai_speaker_notes
        and settings.speaker_notes_api_key
        and settings.speaker_notes_model
    )


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_hit_payload(hits: list[RetrievalHit], limit: int = 4) -> list[dict[str, str | float | None]]:
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


def build_speaker_notes_input(
    spec: TeachingSpec,
    slides: list[SlidePlanItem],
    slide_hits_map: dict[int, list[RetrievalHit]],
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
    slide_payload = []
    for slide in slides:
        slide_payload.append(
            {
                "slide_number": slide.slide_number,
                "title": slide.title,
                "goal": slide.goal,
                "slide_type": slide.slide_type.value,
                "key_points": slide.key_points,
                "current_speaker_notes": slide.speaker_notes,
                "interaction_mode": slide.interaction_mode.value,
                "layout_hint": slide.layout_hint,
                "citations": [
                    {
                        "chunk_id": citation.chunk_id,
                        "page_label": citation.page_label,
                        "note": citation.note,
                        "source_type": citation.source_type,
                    }
                    for citation in slide.citations
                ],
                "evidence": _build_hit_payload(slide_hits_map.get(slide.slide_number, [])),
            }
        )

    return (
        "请只润色每一页的 speaker_notes。\n"
        "返回字段：slides。slides 每项字段：slide_number, speaker_notes。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"页面数据：\n{json.dumps(slide_payload, ensure_ascii=False)}\n"
    )


def _post_speaker_notes_request(
    settings: Settings,
    *,
    system_prompt: str,
    spec: TeachingSpec,
    slides: list[SlidePlanItem],
    slide_hits_map: dict[int, list[RetrievalHit]],
    max_tokens: int,
) -> SpeakerNotesDeckDraft:
    endpoint = (
        f"{settings.speaker_notes_base_url.rstrip('/')}/chat/completions"
        if settings.speaker_notes_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.speaker_notes_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_speaker_notes_input(spec, slides, slide_hits_map),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.speaker_notes_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.speaker_notes_timeout_seconds) as client:
        response = client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    parsed = json.loads(_strip_json_fence(raw_content))
    return SpeakerNotesDeckDraft.model_validate(parsed)


def _request_speaker_notes_polish(
    settings: Settings,
    spec: TeachingSpec,
    slides: list[SlidePlanItem],
    slide_hits_map: dict[int, list[RetrievalHit]],
) -> SpeakerNotesDeckDraft:
    try:
        return _post_speaker_notes_request(
            settings,
            system_prompt=SPEAKER_NOTES_SYSTEM_PROMPT,
            spec=spec,
            slides=slides,
            slide_hits_map=slide_hits_map,
            max_tokens=1800,
        )
    except Exception:
        reduced_hits_map = {
            slide_number: hits[:2]
            for slide_number, hits in slide_hits_map.items()
        }
        return _post_speaker_notes_request(
            settings,
            system_prompt=SPEAKER_NOTES_FALLBACK_SYSTEM_PROMPT,
            spec=spec,
            slides=slides,
            slide_hits_map=reduced_hits_map,
            max_tokens=1000,
        )


def polish_speaker_notes_with_openai(
    spec: TeachingSpec,
    slides: list[SlidePlanItem],
    slide_hits_map: dict[int, list[RetrievalHit]],
    *,
    settings: Settings | None = None,
) -> SpeakerNotesDeckDraft:
    settings = settings or get_settings()
    return _request_speaker_notes_polish(settings, spec, slides, slide_hits_map)
