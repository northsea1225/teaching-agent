from __future__ import annotations

from app.config import get_settings
from app.models import QualityIssue, QualityReport, SessionState, SlideType
from app.models.session import utc_now
from app.services.evidence import get_selected_retrieval_hits
from app.services.openai_quality_review import (
    openai_quality_review_ready,
    review_quality_with_openai,
)


SEVERITY_PENALTY = {
    "critical": 30,
    "high": 18,
    "medium": 10,
    "low": 4,
}

CONTENT_SLIDE_TYPES = {
    SlideType.CONCEPT,
    SlideType.TIMELINE,
    SlideType.COMPARISON,
    SlideType.PROCESS,
    SlideType.MEDIA,
    SlideType.SUMMARY,
}
PLACEHOLDER_MARKERS = ("待补充", "未明确", "仅使用已确认需求", "不补写未提供的延伸内容")
TEMPLATE_LEAK_MARKERS = (
    "参照模板中的内容输入文本",
    "这里可放教材",
    "这里可放资料",
    "这里可放",
)
GENERIC_OBJECTIVE_MARKERS = (
    "是交给学生这节课的内容",
    "本节课的内容",
    "这节课的内容",
    "理解本课内容",
    "掌握本课内容",
)
SUBJECT_NOISE_KEYWORDS = {
    "history": ("nahco3", "cl2", "试剂", "蒸馏水", "饱和食盐水", "红纸编号", "次氯酸", "分液漏斗", "输入法", "五笔", "函数"),
    "humanities": ("nahco3", "cl2", "试剂", "蒸馏水", "饱和食盐水", "红纸编号", "次氯酸", "分液漏斗", "输入法", "五笔"),
}
ACTIVITY_STRUCTURE_KEYWORDS = (
    "任务",
    "讨论",
    "练习",
    "小测",
    "实验",
    "辩论",
    "项目",
    "输出",
    "作业",
    "反馈",
    "discussion",
    "task",
    "project",
    "quiz",
    "practice",
    "deliverable",
    "submit",
)
SUMMARY_STRUCTURE_KEYWORDS = ("回扣目标", "总结", "迁移", "反思", "takeaway", "exit")


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    origin: str = "rule",
    slide_number: int | None = None,
) -> QualityIssue:
    return QualityIssue(
        severity=severity,
        code=code,
        message=message,
        origin=origin,
        slide_number=slide_number,
    )


def _contains_keyword(texts: list[str], keywords: tuple[str, ...]) -> bool:
    lowered_texts = [text.lower() for text in texts if text]
    return any(keyword.lower() in text for keyword in keywords for text in lowered_texts)


def _subject_family(subject: str | None) -> str:
    if subject in {"math", "physics", "chemistry", "biology", "science"}:
        return "stem"
    if subject in {"history", "geography", "politics", "chinese"}:
        return "humanities"
    if subject in {"english"}:
        return "language"
    return "general"


def _subject_noise_markers(subject: str | None) -> tuple[str, ...]:
    family = _subject_family(subject)
    if subject and subject in SUBJECT_NOISE_KEYWORDS:
        return SUBJECT_NOISE_KEYWORDS[subject]
    return SUBJECT_NOISE_KEYWORDS.get(family, ())


def _is_requirement_anchored_slide(session: SessionState, slide_type: SlideType, slide_texts: list[str]) -> bool:
    if session.teaching_spec is None:
        return False

    combined = " ".join(text.lower() for text in slide_texts if text)
    if slide_type == SlideType.SUMMARY:
        anchors = [objective.description for objective in session.teaching_spec.learning_objectives]
        if session.teaching_spec.lesson_title:
            anchors.append(session.teaching_spec.lesson_title)
        if session.teaching_spec.lesson_topic:
            anchors.append(session.teaching_spec.lesson_topic)
        return any(anchor and anchor.lower() in combined for anchor in anchors)

    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT, SlideType.COMPARISON}:
        anchors = list(session.teaching_spec.additional_requirements)
        return any(anchor and anchor.lower() in combined for anchor in anchors)

    return False


def _merge_ai_quality_issues(
    issues: list[QualityIssue],
    ai_review_issues: list[QualityIssue],
) -> list[QualityIssue]:
    merged = list(issues)
    existing_keys = {(issue.code, issue.slide_number, issue.message) for issue in issues}
    for issue in ai_review_issues:
        key = (issue.code, issue.slide_number, issue.message)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        merged.append(issue)
    return merged


def build_quality_report(session: SessionState) -> QualityReport:
    issues: list[QualityIssue] = []
    selected_hits = get_selected_retrieval_hits(session)

    if not session.planning_confirmation.confirmed:
        issues.append(
            _issue(
                "high",
                "planning_confirmation_pending",
                "关键约束还未确认，建议确认后再导出正式稿。",
            )
        )

    if session.teaching_spec is None:
        issues.append(_issue("critical", "missing_teaching_spec", "当前没有结构化教学需求。"))
    elif not session.teaching_spec.learning_objectives or all(
        any(marker in objective.description for marker in GENERIC_OBJECTIVE_MARKERS)
        for objective in session.teaching_spec.learning_objectives
    ):
        issues.append(
            _issue(
                "high",
                "generic_learning_objective",
                "当前学习目标过于空泛，容易导致整套课件只剩模板化表达。",
            )
        )
    if not selected_hits:
        issues.append(_issue("medium", "low_evidence", "当前没有命中任何参考资料，内容容易漂移。"))
    elif session.teaching_spec is not None:
        noise_markers = _subject_noise_markers(session.teaching_spec.subject)
        contaminated_hits = [
            hit
            for hit in selected_hits[:5]
            if _contains_keyword([hit.content, hit.source_title or "", hit.page_label or ""], noise_markers)
            or _contains_keyword([hit.content, hit.source_title or ""], TEMPLATE_LEAK_MARKERS)
        ]
        if contaminated_hits:
            issues.append(
                _issue(
                    "critical",
                    "retrieval_contamination",
                    "当前检索命中混入了异学科或模板残留内容，继续导出会明显跑偏。",
                )
            )

    if session.slide_plan is None:
        issues.append(_issue("critical", "missing_slide_plan", "当前还没有逐页策划。"))
    else:
        lesson_title = session.teaching_spec.lesson_title if session.teaching_spec else None
        noise_markers = _subject_noise_markers(session.teaching_spec.subject if session.teaching_spec else None)
        if len(selected_hits) < 2 and session.slide_plan.total_slides and session.slide_plan.total_slides > 5:
            issues.append(
                _issue(
                    "medium",
                    "evidence_slide_ratio_low",
                    "当前证据较少但页面较多，建议压缩页数或补充资料后再导出。",
                )
            )
        for slide in session.slide_plan.slides:
            slide_texts = [*slide.key_points, *slide.visual_brief, *slide.speaker_notes, *slide.revision_notes]
            placeholder_present = any(
                marker in text
                for marker in PLACEHOLDER_MARKERS
                for text in slide.key_points
            )
            template_leak_present = any(
                marker in text
                for marker in TEMPLATE_LEAK_MARKERS
                for text in slide_texts
            )
            cross_subject_present = bool(noise_markers) and _contains_keyword(slide_texts, noise_markers)
            if not slide.key_points:
                issues.append(_issue("high", "empty_key_points", "页面没有关键要点。", slide_number=slide.slide_number))
            if len(slide.key_points) > 4:
                issues.append(_issue("low", "dense_key_points", "页面关键要点偏多，建议压缩。", slide_number=slide.slide_number))
            if template_leak_present:
                issues.append(
                    _issue(
                        "critical",
                        "template_placeholder_leak",
                        "页面仍残留模板占位词，说明策划结果不可直接用于正式导出。",
                        slide_number=slide.slide_number,
                    )
                )
            if cross_subject_present:
                issues.append(
                    _issue(
                        "critical",
                        "cross_subject_contamination",
                        "页面出现异学科内容污染，当前课件主题已被错误资料带偏。",
                        slide_number=slide.slide_number,
                    )
                )
            if slide.slide_type in CONTENT_SLIDE_TYPES and not slide.citations:
                requirement_anchored = (not selected_hits) and _is_requirement_anchored_slide(
                    session,
                    slide.slide_type,
                    slide_texts,
                )
                issues.append(
                    _issue(
                        "low" if (placeholder_present or requirement_anchored) else "high",
                        "missing_citation" if (placeholder_present or requirement_anchored) else "unsupported_content_risk",
                        "该页缺少引用标签，建议补资料来源。"
                        if (placeholder_present or requirement_anchored)
                        else "该页没有引用却在展开内容，存在幻觉风险，建议回退为待补充或补资料来源。",
                        slide_number=slide.slide_number,
                    )
                )
            if any("待补充" in point for point in slide.key_points):
                issues.append(
                    _issue(
                        "low",
                        "placeholder_present",
                        "该页仍包含待补充提示，说明证据不足或约束未补齐。",
                        slide_number=slide.slide_number,
                    )
                )
            if slide.slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
                has_activity_structure = _contains_keyword(slide_texts, ACTIVITY_STRUCTURE_KEYWORDS)
                if slide.interaction_mode.value == "none" and not placeholder_present:
                    issues.append(
                        _issue(
                            "high",
                            "activity_missing_interaction",
                            "活动页没有明确互动方式，结构容易空转。",
                            slide_number=slide.slide_number,
                        )
                    )
                if not has_activity_structure:
                    issues.append(
                        _issue(
                            "low" if placeholder_present else "high",
                            "activity_placeholder_only" if placeholder_present else "activity_structure_weak",
                            "活动页缺少任务、输出或互动步骤，建议补充活动结构。",
                            slide_number=slide.slide_number,
                        )
                    )
            if slide.slide_type == SlideType.SUMMARY and session.teaching_spec and session.teaching_spec.learning_objectives:
                objective_texts = [objective.description for objective in session.teaching_spec.learning_objectives[:2]]
                objective_linked = _contains_keyword(slide_texts, SUMMARY_STRUCTURE_KEYWORDS) or any(
                    objective in " ".join(slide_texts)
                    for objective in objective_texts
                    if objective
                )
                if not objective_linked:
                    issues.append(
                        _issue(
                            "high",
                            "summary_goal_unlinked",
                            "总结页没有明确回扣学习目标，结构不完整。",
                            slide_number=slide.slide_number,
                        )
                    )
            if slide.slide_type == SlideType.COVER and lesson_title and lesson_title not in slide.title:
                issues.append(
                    _issue(
                        "high",
                        "cover_title_mismatch",
                        "封面标题没有直接使用已确认课题。",
                        slide_number=slide.slide_number,
                    )
                )

    if session.svg_deck is None:
        issues.append(_issue("medium", "missing_svg_deck", "当前还没有 SVG 中间稿。"))
    else:
        if not session.svg_deck.finalized:
            issues.append(_issue("medium", "svg_not_finalized", "SVG 还没有经过 finalize 处理。"))
        if session.slide_plan is not None:
            for slide, svg_slide in zip(session.slide_plan.slides, session.svg_deck.slides):
                if slide.template_id and svg_slide.template_id and slide.template_id != svg_slide.template_id:
                    issues.append(
                        _issue(
                            "medium",
                            "template_mismatch",
                            "逐页策划模板和 SVG 模板不一致。",
                            slide_number=slide.slide_number,
                        )
                    )

    ai_review_summary: str | None = None
    settings = get_settings()
    if (
        session.teaching_spec is not None
        and session.slide_plan is not None
        and session.planning_confirmation.confirmed
        and openai_quality_review_ready(settings)
    ):
        try:
            ai_review = review_quality_with_openai(
                session,
                selected_hits,
                issues,
                settings=settings,
            )
            ai_review_summary = ai_review.summary
            ai_issues = [
                _issue(
                    issue.severity if issue.severity in {"low", "medium", "high", "critical"} else "medium",
                    issue.code,
                    issue.message,
                    origin="ai",
                    slide_number=issue.slide_number,
                )
                for issue in ai_review.issues
            ]
            issues = _merge_ai_quality_issues(issues, ai_issues)
        except Exception:
            ai_review_summary = None

    score = 100
    for issue in issues:
        score -= SEVERITY_PENALTY.get(issue.severity, 6)
    score = max(0, score)

    if any(issue.severity == "critical" for issue in issues):
        status = "blocked"
    elif any(issue.severity == "high" for issue in issues):
        status = "review"
    elif issues:
        status = "warning"
    else:
        status = "ready"

    if not issues:
        summary = "当前课件链路已通过基础质量检查，可继续导出和展示。"
    else:
        summary = f"发现 {len(issues)} 个质量检查项，当前状态为 {status}。"
    if ai_review_summary:
        summary = f"{summary} AI审稿：{ai_review_summary}"

    return QualityReport(
        status=status,
        score=score,
        summary=summary,
        issues=issues,
        checked_at=utc_now(),
    )


def refresh_quality_report(session: SessionState) -> SessionState:
    session.quality_report = build_quality_report(session)
    return session
