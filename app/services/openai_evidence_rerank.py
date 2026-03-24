from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import RetrievalHit, TeachingSpec
from app.models.schemas import AppModel


EVIDENCE_RERANK_SYSTEM_PROMPT = """
你是教学证据重排助手，负责从候选资料里挑出最适合当前课程生成的证据。

要求：
1. 只能使用输入里给出的 chunk_id，不要编造新的 chunk_id。
2. 只保留最相关的证据，优先贴合课题、学科、学段和已确认约束。
3. 如果候选里有弱相关、模板残留、跨学科噪声，要主动丢弃。
4. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
5. selected_evidence 最多保留 target_top_k 条。
6. focus 只写这条证据对当前课程的作用，不要补写新事实；尽量控制在 18 个中文字符或 12 个英文词以内。
""".strip()

EVIDENCE_RERANK_FALLBACK_SYSTEM_PROMPT = """
你是教学证据重排助手。请从候选证据中挑出最相关的 chunk_id，并给出简短 focus。
只返回 JSON，不要解释，不要编造新 chunk_id。
""".strip()


class EvidenceSelection(AppModel):
    chunk_id: str
    focus: str | None = None


class EvidenceRerankDraft(AppModel):
    selected_evidence: list[EvidenceSelection] = Field(default_factory=list)


def openai_evidence_rerank_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.use_openai_evidence_rerank
        and settings.evidence_rerank_api_key
        and settings.evidence_rerank_model
    )


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_candidate_payload(hits: list[RetrievalHit]) -> list[dict[str, str | float | None]]:
    payload: list[dict[str, str | float | None]] = []
    for hit in hits:
        payload.append(
            {
                "chunk_id": hit.chunk_id,
                "source_type": hit.source_type,
                "source_title": hit.source_title or hit.source_filename or hit.page_label,
                "page_label": hit.page_label,
                "subject_tag": hit.subject_tag,
                "stage_tag": hit.stage_tag,
                "topic_hint": hit.topic_hint,
                "score": hit.score,
                "content": _normalize_text(hit.content)[:180],
            }
        )
    return payload


def build_evidence_rerank_input(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    *,
    top_k: int,
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
        "请对候选证据做重排，并只保留最适合后续课件生成的证据。\n"
        "返回字段：selected_evidence。\n"
        "selected_evidence 每项字段：chunk_id, focus。\n"
        f"最多保留 {top_k} 条。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"候选证据：\n{json.dumps(_build_candidate_payload(retrieval_hits), ensure_ascii=False)}\n"
    )


def _merge_focus_hint(existing: str | None, focus: str | None) -> str | None:
    normalized_existing = _normalize_text(existing)
    normalized_focus = _normalize_text(focus)
    if not normalized_existing:
        return normalized_focus or None
    if not normalized_focus:
        return normalized_existing
    if normalized_focus in normalized_existing:
        return normalized_existing
    if normalized_existing in normalized_focus:
        return normalized_focus
    merged = f"{normalized_existing} / {normalized_focus}"
    return merged[:48]


def _post_evidence_rerank_request(
    settings: Settings,
    *,
    system_prompt: str,
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    top_k: int,
    max_tokens: int,
) -> EvidenceRerankDraft:
    endpoint = (
        f"{settings.evidence_rerank_base_url.rstrip('/')}/chat/completions"
        if settings.evidence_rerank_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.evidence_rerank_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_evidence_rerank_input(spec, retrieval_hits, top_k=top_k),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.evidence_rerank_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.evidence_rerank_timeout_seconds) as client:
        response = client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    parsed = json.loads(_strip_json_fence(raw_content))
    return EvidenceRerankDraft.model_validate(parsed)


def _request_evidence_rerank(
    settings: Settings,
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    *,
    top_k: int,
) -> EvidenceRerankDraft:
    try:
        return _post_evidence_rerank_request(
            settings,
            system_prompt=EVIDENCE_RERANK_SYSTEM_PROMPT,
            spec=spec,
            retrieval_hits=retrieval_hits,
            top_k=top_k,
            max_tokens=900,
        )
    except Exception:
        return _post_evidence_rerank_request(
            settings,
            system_prompt=EVIDENCE_RERANK_FALLBACK_SYSTEM_PROMPT,
            spec=spec,
            retrieval_hits=retrieval_hits[: max(top_k + 1, 3)],
            top_k=top_k,
            max_tokens=600,
        )


def rerank_retrieval_hits_with_openai(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    *,
    top_k: int,
    settings: Settings | None = None,
) -> list[RetrievalHit]:
    settings = settings or get_settings()
    if not retrieval_hits:
        return []

    draft = _request_evidence_rerank(settings, spec, retrieval_hits, top_k=top_k)
    hit_by_id = {hit.chunk_id: hit for hit in retrieval_hits}
    selected: list[RetrievalHit] = []
    selected_ids: set[str] = set()

    for rank, item in enumerate(draft.selected_evidence):
        if item.chunk_id in selected_ids:
            continue
        hit = hit_by_id.get(item.chunk_id)
        if hit is None:
            continue
        selected_ids.add(item.chunk_id)
        selected.append(
            hit.model_copy(
                update={
                    "topic_hint": _merge_focus_hint(hit.topic_hint, item.focus),
                    "score": float(hit.score or 0.0) + max(top_k - rank, 1) * 0.25,
                }
            )
        )

    if not selected:
        raise ValueError("Evidence rerank returned no usable hits")

    for hit in retrieval_hits:
        if hit.chunk_id in selected_ids:
            continue
        selected.append(hit)
        if len(selected) >= top_k:
            break

    return selected[:top_k]
