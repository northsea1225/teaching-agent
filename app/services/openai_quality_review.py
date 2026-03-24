from __future__ import annotations

import json
import re

import httpx
from pydantic import Field

from app.config import Settings, get_settings
from app.models import QualityIssue, RetrievalHit, SessionState
from app.models.schemas import AppModel


QUALITY_REVIEW_SYSTEM_PROMPT = """
你是教学课件质量审稿助手，负责基于当前会话资料给出补充性质量意见。

要求：
1. 规则检查已经跑过，你只补充规则未必能覆盖的风险，不要机械重复已有问题。
2. 只能依据输入里的教学需求、证据、逐页策划和规则问题生成意见，不要补写新事实。
3. 输出必须是 JSON 对象，不要输出 Markdown，不要输出解释文字。
4. issues 最多返回 4 条。
5. severity 只能使用 low, medium, high。
6. code 使用简短 snake_case，例如 goal_coverage_gap, evidence_alignment_gap。
7. slide_number 只有在问题明显落在某一页时才填写。
8. summary 用一句话概括当前课件最需要优先修的方向。
""".strip()

QUALITY_REVIEW_FALLBACK_SYSTEM_PROMPT = """
你是教学课件质量审稿助手。请基于输入返回 JSON 格式的补充审稿意见。
只返回 JSON，不要解释，不要重复已有规则问题。
""".strip()


class AIQualityIssueDraft(AppModel):
    severity: str
    code: str
    message: str
    slide_number: int | None = None


class AIQualityReviewDraft(AppModel):
    summary: str | None = None
    issues: list[AIQualityIssueDraft] = Field(default_factory=list)


def openai_quality_review_ready(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(
        settings.use_openai_quality_review
        and settings.quality_review_api_key
        and settings.quality_review_model
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
                "chunk_id": hit.chunk_id,
                "source_type": hit.source_type,
                "source_title": hit.source_title or hit.source_filename or hit.page_label,
                "topic_hint": hit.topic_hint,
                "score": hit.score,
                "content": _normalize_text(hit.content)[:160],
            }
        )
    return payload


def _build_slide_payload(session: SessionState) -> list[dict[str, object]]:
    if session.slide_plan is None:
        return []

    payload: list[dict[str, object]] = []
    for slide in session.slide_plan.slides:
        payload.append(
            {
                "slide_number": slide.slide_number,
                "slide_type": slide.slide_type.value,
                "title": slide.title,
                "goal": slide.goal,
                "key_points": slide.key_points,
                "interaction_mode": slide.interaction_mode.value,
                "citation_count": len(slide.citations),
                "revision_notes": slide.revision_notes,
            }
        )
    return payload


def _build_rule_issue_payload(issues: list[QualityIssue], limit: int = 8) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for issue in issues[:limit]:
        payload.append(
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "slide_number": issue.slide_number,
            }
        )
    return payload


def build_quality_review_input(
    session: SessionState,
    selected_hits: list[RetrievalHit],
    rule_issues: list[QualityIssue],
) -> str:
    spec = session.teaching_spec
    spec_payload = {
        "education_stage": spec.education_stage if spec else None,
        "subject": spec.subject if spec else None,
        "grade_level": spec.grade_level if spec else None,
        "lesson_title": spec.lesson_title if spec else None,
        "lesson_topic": spec.lesson_topic if spec else None,
        "class_duration_minutes": spec.class_duration_minutes if spec else None,
        "learning_objectives": [item.description for item in spec.learning_objectives] if spec else [],
        "key_difficulties": spec.key_difficulties if spec else [],
        "interaction_preferences": [item.value for item in spec.interaction_preferences] if spec else [],
        "additional_requirements": spec.additional_requirements if spec else [],
    }
    confirmation_payload = {
        "confirmed": session.planning_confirmation.confirmed,
        "missing_items": session.planning_confirmation.missing_items,
        "guidance": session.planning_confirmation.guidance[:4],
    }
    return (
        "请补充审查当前课件的结构与内容质量。\n"
        "返回字段：summary, issues。\n"
        "issues 每项字段：severity, code, message, slide_number。\n\n"
        f"教学需求：\n{json.dumps(spec_payload, ensure_ascii=False)}\n\n"
        f"约束确认：\n{json.dumps(confirmation_payload, ensure_ascii=False)}\n\n"
        f"已选证据：\n{json.dumps(_build_retrieval_payload(selected_hits), ensure_ascii=False)}\n\n"
        f"逐页策划：\n{json.dumps(_build_slide_payload(session), ensure_ascii=False)}\n\n"
        f"规则检查已发现问题：\n{json.dumps(_build_rule_issue_payload(rule_issues), ensure_ascii=False)}\n"
    )


def _post_quality_review_request(
    settings: Settings,
    *,
    system_prompt: str,
    session: SessionState,
    selected_hits: list[RetrievalHit],
    rule_issues: list[QualityIssue],
    max_tokens: int,
) -> AIQualityReviewDraft:
    endpoint = (
        f"{settings.quality_review_base_url.rstrip('/')}/chat/completions"
        if settings.quality_review_base_url
        else "https://api.openai.com/v1/chat/completions"
    )
    payload = {
        "model": settings.quality_review_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_quality_review_input(session, selected_hits, rule_issues),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.quality_review_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=settings.quality_review_timeout_seconds) as client:
        response = client.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    parsed = json.loads(_strip_json_fence(raw_content))
    return AIQualityReviewDraft.model_validate(parsed)


def _request_quality_review(
    settings: Settings,
    session: SessionState,
    selected_hits: list[RetrievalHit],
    rule_issues: list[QualityIssue],
) -> AIQualityReviewDraft:
    try:
        return _post_quality_review_request(
            settings,
            system_prompt=QUALITY_REVIEW_SYSTEM_PROMPT,
            session=session,
            selected_hits=selected_hits,
            rule_issues=rule_issues,
            max_tokens=900,
        )
    except Exception:
        return _post_quality_review_request(
            settings,
            system_prompt=QUALITY_REVIEW_FALLBACK_SYSTEM_PROMPT,
            session=session,
            selected_hits=selected_hits[:4],
            rule_issues=rule_issues[:5],
            max_tokens=600,
        )


def review_quality_with_openai(
    session: SessionState,
    selected_hits: list[RetrievalHit],
    rule_issues: list[QualityIssue],
    *,
    settings: Settings | None = None,
) -> AIQualityReviewDraft:
    settings = settings or get_settings()
    return _request_quality_review(settings, session, selected_hits, rule_issues)
