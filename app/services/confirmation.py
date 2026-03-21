from __future__ import annotations

from app.models import ConfirmationItem, PlanningConfirmation, SessionState
from app.models.session import utc_now
from app.services.evidence import get_selected_retrieval_hits


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


def _item(label: str, detail: str | None, *, required: bool = True) -> ConfirmationItem:
    status = "confirmed" if detail else "missing"
    return ConfirmationItem(label=label, detail=detail, status=status, required=required)


def _extract_boundary_requirements(session: SessionState) -> list[str]:
    spec = session.teaching_spec
    if spec is None:
        return []

    boundary_notes: list[str] = []
    for requirement in spec.additional_requirements:
        normalized = " ".join(str(requirement or "").split()).strip()
        lowered = normalized.lower()
        if not normalized:
            continue
        if any(marker.lower() in lowered for marker in BOUNDARY_REQUIREMENT_MARKERS):
            if normalized not in boundary_notes:
                boundary_notes.append(normalized)
    return boundary_notes[:3]


def _build_boundary_detail(
    session: SessionState,
    uploaded_names: str | None,
    retrieval_scope: str | None,
) -> str | None:
    parts: list[str] = []
    boundary_notes = _extract_boundary_requirements(session)

    if boundary_notes:
        parts.append("约束：" + "；".join(boundary_notes))

    runtime_parts: list[str] = ["本地知识库：默认启用"]
    if uploaded_names:
        runtime_parts.append(f"已上传：{uploaded_names}")
    if retrieval_scope:
        runtime_parts.append(retrieval_scope)
    if session.web_search_enabled:
        runtime_parts.append("联网补充搜索：已开启")
    else:
        runtime_parts.append("联网补充搜索：未开启")

    if runtime_parts:
        prefix = "当前" if boundary_notes else "当前来源"
        parts.append(f"{prefix}：" + "；".join(runtime_parts))

    return "；".join(part for part in parts if part) or None


def build_planning_confirmation(session: SessionState) -> PlanningConfirmation:
    spec = session.teaching_spec
    if spec is None:
        return PlanningConfirmation(
            summary="当前还没有结构化教学需求，先提交教师需求再确认约束。",
            missing_items=["教学需求"],
            guidance=["先提交课题、学科、学段和课时信息。"],
            updated_at=utc_now(),
        )

    uploaded_names = ", ".join(file.filename for file in session.uploaded_files[:3]) or None
    selected_hits = get_selected_retrieval_hits(session)
    retrieval_scope = (
        f"已保留 {len(selected_hits)} / {len(session.retrieval_hits)} 条参考资料"
        if session.retrieval_hits
        else ("已上传资料待使用" if session.uploaded_files else None)
    )
    boundary_detail = _build_boundary_detail(session, uploaded_names, retrieval_scope)

    items = [
        _item("学段", spec.education_stage),
        _item("学科", spec.subject),
        _item("课题", spec.lesson_title or spec.lesson_topic),
        _item("课时", f"{spec.class_duration_minutes} 分钟" if spec.class_duration_minutes else None),
        _item(
            "学习目标",
            "；".join(objective.description for objective in spec.learning_objectives[:3]) or None,
        ),
        _item("重点难点", "；".join(spec.key_difficulties[:3]) or None),
        _item(
            "互动方式",
            "；".join(mode.value for mode in spec.interaction_preferences[:3]) or None,
            required=False,
        ),
        _item(
            "资料边界",
            boundary_detail,
        ),
        _item("输出格式", "、".join(spec.required_outputs) if spec.required_outputs else None, required=False),
    ]

    missing_items = [item.label for item in items if item.required and item.status == "missing"]
    blocking_missing = [item for item in missing_items if item in {"学段", "学科", "课题", "学习目标"}]
    guidance: list[str] = []
    if "学习目标" in missing_items:
        guidance.append("先补学习目标，再生成大纲和导出件。")
    if "资料边界" in missing_items:
        guidance.append("请明确写出允许使用的资料范围。默认会优先使用本地知识库。")
    elif boundary_detail and not session.uploaded_files and not session.retrieval_hits:
        guidance.append("当前将默认优先使用本地知识库；如需更强约束，可再上传资料或开启联网补充搜索。")
    if not guidance:
        guidance.append("确认后再继续生成，可以显著减少大纲和课件偏题。")

    confirmed = session.planning_confirmation.confirmed and not blocking_missing
    if confirmed and missing_items:
        summary = f"关键约束已确认，仍有待补充项：{'、'.join(missing_items)}。"
    elif missing_items:
        summary = f"还有 {len(missing_items)} 项关键约束未确认：{'、'.join(missing_items)}。"
    else:
        summary = "关键约束已齐，可以进入大纲、SVG 和导出阶段。"

    return PlanningConfirmation(
        confirmed=confirmed,
        required=True,
        summary=summary,
        items=items,
        missing_items=missing_items,
        guidance=guidance,
        confirmed_note=session.planning_confirmation.confirmed_note,
        confirmed_at=session.planning_confirmation.confirmed_at if confirmed else None,
        updated_at=utc_now(),
    )


def refresh_planning_confirmation(session: SessionState) -> SessionState:
    session.planning_confirmation = build_planning_confirmation(session)
    return session


def confirm_planning_constraints(session: SessionState, note: str | None = None) -> SessionState:
    session = refresh_planning_confirmation(session)
    blocking_missing = [
        item
        for item in session.planning_confirmation.missing_items
        if item in {"学科", "课题", "学段", "学习目标"}
    ]
    if blocking_missing:
        raise ValueError(f"仍缺少关键确认项：{'、'.join(blocking_missing)}")

    session.planning_confirmation.confirmed = True
    session.planning_confirmation.confirmed_note = note
    session.planning_confirmation.confirmed_at = utc_now()
    session.planning_confirmation.summary = "约束已确认，后续生成将优先遵守当前需求和证据边界。"
    session.planning_confirmation.updated_at = utc_now()
    session.updated_at = utc_now()
    return session
