from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import ClarificationQuestion, InteractionMode, LearningObjective, TeachingSpec
from app.models.schemas import AppModel
from app.utils.prompts import DIALOG_STRUCTURING_SYSTEM_PROMPT


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DialogClarificationDraft(AppModel):
    prompt: str
    reason: str
    required: bool = True


class DialogExtraction(AppModel):
    education_stage: str | None = None
    subject: str | None = None
    grade_level: str | None = None
    textbook_version: str | None = None
    lesson_title: str | None = None
    lesson_topic: str | None = None
    class_duration_minutes: int | None = Field(default=None, ge=1, le=180)
    learning_objectives: list[str] = Field(default_factory=list)
    key_difficulties: list[str] = Field(default_factory=list)
    teaching_methods: list[str] = Field(default_factory=list)
    interaction_preferences: list[str] = Field(default_factory=list)
    style_preferences: list[str] = Field(default_factory=list)
    additional_requirements: list[str] = Field(default_factory=list)
    unresolved_questions: list[DialogClarificationDraft] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confirmed: bool = False


SUBJECT_NORMALIZATION = {
    "语文": "chinese",
    "数学": "math",
    "英语": "english",
    "物理": "physics",
    "化学": "chemistry",
    "生物": "biology",
    "历史": "history",
    "地理": "geography",
    "政治": "politics",
    "信息技术": "information-technology",
    "科学": "science",
    "music": "music",
    "art": "art",
}

STAGE_NORMALIZATION = {
    "小学": "primary-school",
    "初中": "middle-school",
    "高中": "high-school",
    "大学": "college",
    "职业": "vocational",
    "幼儿": "kindergarten",
}

BOUNDARY_REQUIREMENT_MARKERS = (
    "资料边界",
    "内容来源",
    "来源范围",
    "只使用",
    "仅使用",
    "上传资料",
    "上传文件",
    "本地知识库",
    "检索命中",
    "联网搜索",
    "联网结果",
    "网页资料",
    "网站资料",
    "课外",
    "不要扩展",
    "不扩展",
    "不引入",
    "不使用",
)


def openai_dialog_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.use_openai_dialog and settings.openai_api_key.strip())


def _normalize_subject(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    return SUBJECT_NORMALIZATION.get(candidate, candidate.lower())


def _normalize_stage(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    return STAGE_NORMALIZATION.get(candidate, candidate.lower())


def _normalize_text_list(items: list[str], limit: int = 8) -> list[str]:
    normalized: list[str] = []
    for item in items:
        candidate = " ".join((item or "").split()).strip("，,。；;：: ")
        if not candidate or candidate in normalized:
            continue
        normalized.append(candidate)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_interaction_modes(items: list[str]) -> list[InteractionMode]:
    normalized: list[InteractionMode] = []
    for item in items:
        value = (item or "").strip().lower()
        if not value:
            continue
        try:
            mode = InteractionMode(value)
        except ValueError:
            continue
        if mode not in normalized:
            normalized.append(mode)
    return normalized


def _is_boundary_requirement(value: str) -> bool:
    lowered = value.lower()
    return any(marker.lower() in lowered for marker in BOUNDARY_REQUIREMENT_MARKERS)


def _merge_requirement_items(
    existing_items: list[str],
    extracted_items: list[str],
    *,
    limit: int = 8,
) -> list[str]:
    new_boundary_items = [item for item in extracted_items if _is_boundary_requirement(item)]
    preserved_boundary_items = (
        new_boundary_items
        if new_boundary_items
        else [item for item in existing_items if _is_boundary_requirement(item)]
    )

    merged: list[str] = []
    for item in extracted_items:
        if item not in merged:
            merged.append(item)
    for item in preserved_boundary_items:
        if item not in merged:
            merged.append(item)
        if len(merged) >= limit:
            break
    return merged[:limit]


def _strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_message_content(message_content: object) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        chunks: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            elif hasattr(item, "type") and getattr(item, "type", None) == "text":
                chunks.append(str(getattr(item, "text", "")))
        return "\n".join(chunk for chunk in chunks if chunk)
    return str(message_content or "")


def build_dialog_input(existing: TeachingSpec | None, content: str) -> str:
    existing_payload = {
        "education_stage": existing.education_stage if existing else None,
        "subject": existing.subject if existing else None,
        "grade_level": existing.grade_level if existing else None,
        "textbook_version": existing.textbook_version if existing else None,
        "lesson_title": existing.lesson_title if existing else None,
        "lesson_topic": existing.lesson_topic if existing else None,
        "class_duration_minutes": existing.class_duration_minutes if existing else None,
        "learning_objectives": [item.description for item in (existing.learning_objectives if existing else [])],
        "key_difficulties": list(existing.key_difficulties if existing else []),
        "teaching_methods": list(existing.teaching_methods if existing else []),
        "interaction_preferences": [item.value for item in (existing.interaction_preferences if existing else [])],
        "style_preferences": list(existing.style_preferences if existing else []),
        "additional_requirements": list(existing.additional_requirements if existing else []),
    }
    compact_existing = {key: value for key, value in existing_payload.items() if value}
    return (
        "请把教师输入整理成一个 JSON 对象，只返回 JSON。\n"
        "字段固定为：education_stage, subject, grade_level, textbook_version, lesson_title, "
        "lesson_topic, class_duration_minutes, learning_objectives, key_difficulties, "
        "teaching_methods, interaction_preferences, style_preferences, additional_requirements, "
        "unresolved_questions, confidence, confirmed。\n"
        "其中 unresolved_questions 的每一项格式为 {\"prompt\": \"\", \"reason\": \"\", \"required\": true}。\n"
        "没有明确提到的信息请留空、空数组或 false，不要猜测，不要输出额外说明。\n\n"
        f"当前已知结构：\n{json.dumps(compact_existing, ensure_ascii=False)}\n\n"
        f"教师最新输入：\n{content.strip()}\n"
    )


def merge_extraction_into_spec(
    existing: TeachingSpec | None,
    extraction: DialogExtraction,
) -> TeachingSpec:
    spec = existing.model_copy(deep=True) if existing else TeachingSpec()

    normalized_stage = _normalize_stage(extraction.education_stage)
    normalized_subject = _normalize_subject(extraction.subject)
    if normalized_stage:
        spec.education_stage = normalized_stage
    if normalized_subject:
        spec.subject = normalized_subject
    if extraction.grade_level:
        spec.grade_level = extraction.grade_level
    if extraction.textbook_version:
        spec.textbook_version = extraction.textbook_version
    if extraction.lesson_title:
        spec.lesson_title = extraction.lesson_title
    if extraction.lesson_topic:
        spec.lesson_topic = extraction.lesson_topic
    if extraction.class_duration_minutes:
        spec.class_duration_minutes = extraction.class_duration_minutes

    objective_items = _normalize_text_list(extraction.learning_objectives, limit=5)
    if objective_items:
        spec.learning_objectives = [
            LearningObjective(description=item)
            for item in objective_items
        ]

    difficulty_items = _normalize_text_list(extraction.key_difficulties, limit=5)
    if difficulty_items:
        spec.key_difficulties = difficulty_items

    method_items = _normalize_text_list(extraction.teaching_methods, limit=6)
    if method_items:
        spec.teaching_methods = method_items

    style_items = _normalize_text_list(extraction.style_preferences, limit=6)
    if style_items:
        spec.style_preferences = style_items

    existing_requirement_items = _normalize_text_list(spec.additional_requirements, limit=8)
    requirement_items = _normalize_text_list(extraction.additional_requirements, limit=8)
    if requirement_items:
        spec.additional_requirements = _merge_requirement_items(
            existing_requirement_items,
            requirement_items,
            limit=8,
        )

    interaction_items = _normalize_interaction_modes(extraction.interaction_preferences)
    if interaction_items:
        spec.interaction_preferences = interaction_items

    spec.unresolved_questions = [
        ClarificationQuestion(
            prompt=item.prompt,
            reason=item.reason,
            required=item.required,
        )
        for item in extraction.unresolved_questions
    ]
    spec.confirmed = extraction.confirmed and not spec.unresolved_questions
    spec.confidence = extraction.confidence
    spec.updated_at = utc_now()
    return spec


def _request_dialog_extraction(
    settings: Settings,
    existing: TeachingSpec | None,
    content: str,
) -> DialogExtraction:
    endpoint = (
        f"{settings.openai_base_url.rstrip('/')}/chat/completions"
        if settings.openai_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.openai_dialog_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": DIALOG_STRUCTURING_SYSTEM_PROMPT},
            {"role": "user", "content": build_dialog_input(existing, content)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=settings.openai_dialog_timeout_seconds) as client:
        response = client.post(
            endpoint,
            headers=headers,
            json=payload,
        )
    response.raise_for_status()
    body = response.json()
    raw_content = _extract_message_content(body["choices"][0]["message"]["content"])
    payload = json.loads(_strip_json_fence(raw_content))
    return DialogExtraction.model_validate(payload)


def extract_teaching_spec_with_openai(
    existing: TeachingSpec | None,
    content: str,
    *,
    settings: Settings | None = None,
) -> TeachingSpec:
    settings = settings or get_settings()
    extraction = _request_dialog_extraction(settings, existing, content)
    return merge_extraction_into_spec(existing, extraction)
