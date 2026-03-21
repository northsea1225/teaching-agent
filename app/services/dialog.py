from __future__ import annotations

import re
from datetime import datetime, timezone

from app.config import get_settings
from app.models import (
    ClarificationQuestion,
    InteractionMode,
    LearningObjective,
    MessageRole,
    RetrievalHit,
    SessionMessage,
    SessionStage,
    SessionState,
    TeachingSpec,
)
from app.services.planner import fetch_retrieval_hits
from app.services.evidence import get_selected_retrieval_hits
from app.services.openai_dialog import (
    extract_teaching_spec_with_openai,
    openai_dialog_ready,
)


SUBJECT_KEYWORDS = {
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

STAGE_KEYWORDS = {
    "小学": "primary-school",
    "初中": "middle-school",
    "高中": "high-school",
    "大学": "college",
    "职业": "vocational",
    "幼儿": "kindergarten",
}

INTERACTION_KEYWORDS = {
    "讨论": InteractionMode.DISCUSSION,
    "小测": InteractionMode.QUIZ,
    "测验": InteractionMode.QUIZ,
    "练习": InteractionMode.EXERCISE,
    "实验": InteractionMode.EXPERIMENT,
    "辩论": InteractionMode.DEBATE,
    "项目": InteractionMode.PROJECT,
}

STYLE_KEYWORDS = ("简洁", "活泼", "学术", "探究式", "项目式", "可视化", "互动性强")
METHOD_KEYWORDS = ("讲授", "探究式", "项目式", "任务驱动", "合作学习", "翻转课堂", "讲练结合", "情境教学")
REQUIREMENT_TRIGGERS = (
    "加入",
    "增加",
    "保留",
    "突出",
    "强调",
    "不要",
    "不需要",
    "不扩展",
    "不引入",
    "仅使用",
    "只使用",
    "控制",
    "压缩",
    "减少",
    "围绕",
    "聚焦",
    "引用",
    "基于",
    "材料分析",
    "案例",
    "讨论",
    "项目",
    "小测",
    "练习",
    "实验",
    "作业",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_stage(content: str) -> str | None:
    for keyword, normalized in STAGE_KEYWORDS.items():
        if keyword in content:
            return normalized
    return None


def _extract_subject(content: str) -> str | None:
    for keyword, normalized in SUBJECT_KEYWORDS.items():
        if keyword in content:
            return normalized
    return None


def _extract_grade_level(content: str) -> str | None:
    patterns = [
        r"(高一|高二|高三)",
        r"(初一|初二|初三)",
        r"([一二三四五六]年级)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    return None


def _extract_duration_minutes(content: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(分钟|min)", content, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_lesson_title(content: str) -> str | None:
    for pattern in [r"《([^》]+)》", r"[“\"]([^”\"]+)[”\"]"]:
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()

    trigger_patterns = [
        r"(?:课题|主题|内容|讲授|讲解)[:：]?\s*([^\n，。；]{2,30})",
        r"(?:一节|一堂)([^\n，。；]{2,30})(?:课|教学)",
    ]
    for pattern in trigger_patterns:
        match = re.search(pattern, content)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate
    return None


def _extract_interaction_preferences(content: str) -> list[InteractionMode]:
    found: list[InteractionMode] = []
    for keyword, mode in INTERACTION_KEYWORDS.items():
        if keyword in content and mode not in found:
            found.append(mode)
    return found


def _extract_style_preferences(content: str) -> list[str]:
    styles: list[str] = []
    for keyword in STYLE_KEYWORDS:
        if keyword in content:
            styles.append(keyword)
    return styles


def _split_instruction_fragments(content: str) -> list[str]:
    fragments = re.split(r"[，,。；;\n]+", content)
    return [
        " ".join(fragment.split()).strip(" :：-")
        for fragment in fragments
        if " ".join(fragment.split()).strip(" :：-")
    ]


def _extract_learning_objectives(content: str) -> list[str]:
    objectives: list[str] = []
    patterns = [
        r"(?:教学目标|学习目标)[:：]?\s*([^\n。；]{4,60})",
        r"(?:希望学生|让学生)(?:能够|学会|理解|掌握)?([^\n。；]{4,50})",
        r"(?:学生能够|学生学会|学生理解|学生掌握)([^\n。；]{4,50})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            candidate = " ".join(match.group(1).split()).strip("，,。；; ")
            if len(candidate) >= 4 and candidate not in objectives:
                objectives.append(candidate)
    return objectives[:3]


def _extract_key_difficulties(content: str) -> list[str]:
    difficulties: list[str] = []
    for pattern in [r"(?:重点难点|重点|难点)[:：]?\s*([^\n。；]{4,60})"]:
        for match in re.finditer(pattern, content):
            candidate = " ".join(match.group(1).split()).strip("，,。；; ")
            if len(candidate) >= 4 and candidate not in difficulties:
                difficulties.append(candidate)
    return difficulties[:3]


def _extract_teaching_methods(content: str) -> list[str]:
    methods: list[str] = []
    for keyword in METHOD_KEYWORDS:
        if keyword in content and keyword not in methods:
            methods.append(keyword)
    return methods


def _extract_explicit_requirements(content: str) -> list[str]:
    requirements: list[str] = []
    for fragment in _split_instruction_fragments(content):
        lowered = fragment.lower()
        if len(fragment) < 4:
            continue
        if fragment.startswith(("我想做", "帮我做", "请帮我做", "我要做", "做一节", "准备一节")):
            continue
        if any(trigger in lowered for trigger in REQUIREMENT_TRIGGERS):
            if fragment not in requirements:
                requirements.append(fragment)
    return requirements[:6]


def _build_clarification_questions(spec: TeachingSpec) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    if not spec.education_stage:
        questions.append(
            ClarificationQuestion(
                prompt="请先确认适用学段，例如小学、初中或高中。",
                reason="不同学段决定内容深度和课件表达方式。",
            )
        )
    if not spec.subject:
        questions.append(
            ClarificationQuestion(
                prompt="请确认学科，例如语文、数学、英语或物理。",
                reason="学科决定知识组织方式和页面模板。",
            )
        )
    if not spec.lesson_title:
        questions.append(
            ClarificationQuestion(
                prompt="请说明本节课的课题或主题名称。",
                reason="课题是生成大纲和检索资料的核心锚点。",
            )
        )
    if not spec.learning_objectives:
        questions.append(
            ClarificationQuestion(
                prompt="这节课最希望学生学会什么？请给出 1 到 3 个教学目标。",
                reason="没有教学目标，大纲和教案会缺少方向。",
            )
        )
    if not spec.interaction_preferences:
        questions.append(
            ClarificationQuestion(
                prompt="你希望课堂加入什么互动形式，例如讨论、小测、实验或项目任务？",
                reason="互动形式会影响页面设计和课堂活动安排。",
            )
        )
    return questions


def _summarize_spec(spec: TeachingSpec) -> list[str]:
    summary: list[str] = []
    if spec.education_stage:
        summary.append(f"学段: {spec.education_stage}")
    if spec.grade_level:
        summary.append(f"年级: {spec.grade_level}")
    if spec.subject:
        summary.append(f"学科: {spec.subject}")
    if spec.lesson_title:
        summary.append(f"课题: {spec.lesson_title}")
    if spec.class_duration_minutes:
        summary.append(f"时长: {spec.class_duration_minutes} 分钟")
    if spec.style_preferences:
        summary.append(f"风格: {', '.join(spec.style_preferences)}")
    if spec.interaction_preferences:
        summary.append(
            "互动: " + ", ".join(mode.value for mode in spec.interaction_preferences)
        )
    return summary


def _build_assistant_message(spec: TeachingSpec, retrieval_hits: list[RetrievalHit]) -> str:
    lines = ["已提取到当前教学需求："]
    summary = _summarize_spec(spec)
    if summary:
        lines.extend(f"- {item}" for item in summary)
    else:
        lines.append("- 当前信息还比较少。")

    if retrieval_hits:
        source_types = {hit.source_type or "knowledge-base" for hit in retrieval_hits}
        source_labels: list[str] = []
        if "knowledge-base" in source_types:
            source_labels.append("本地知识库")
        if "web" in source_types:
            source_labels.append("联网搜索")
        if "session-file" in source_types:
            source_labels.append("当前上传资料")
        lines.append("")
        source_text = "、".join(source_labels) if source_labels else "检索结果"
        lines.append(f"已从{source_text}中整理出 {len(retrieval_hits)} 条相关内容，前两条参考如下：")
        for hit in retrieval_hits[:2]:
            preview = " ".join(hit.content.split())[:80]
            lines.append(f"- {preview}")

    if spec.unresolved_questions:
        lines.append("")
        lines.append("还需要继续确认：")
        lines.extend(
            f"{index}. {question.prompt}"
            for index, question in enumerate(spec.unresolved_questions, start=1)
        )
    else:
        lines.append("")
        lines.append("关键信息已基本完整，可以进入课程大纲和页级策划阶段。")
    return "\n".join(lines)


def _merge_spec(existing: TeachingSpec | None, content: str) -> TeachingSpec:
    spec = existing.model_copy(deep=True) if existing else TeachingSpec()
    spec.education_stage = spec.education_stage or _extract_stage(content)
    spec.subject = spec.subject or _extract_subject(content)
    spec.grade_level = spec.grade_level or _extract_grade_level(content)
    spec.lesson_title = spec.lesson_title or _extract_lesson_title(content)

    duration = _extract_duration_minutes(content)
    if duration:
        spec.class_duration_minutes = duration

    for mode in _extract_interaction_preferences(content):
        if mode not in spec.interaction_preferences:
            spec.interaction_preferences.append(mode)

    for style in _extract_style_preferences(content):
        if style not in spec.style_preferences:
            spec.style_preferences.append(style)

    for method in _extract_teaching_methods(content):
        if method not in spec.teaching_methods:
            spec.teaching_methods.append(method)

    for objective in _extract_learning_objectives(content):
        if all(existing_objective.description != objective for existing_objective in spec.learning_objectives):
            spec.learning_objectives.append(LearningObjective(description=objective))

    for difficulty in _extract_key_difficulties(content):
        if difficulty not in spec.key_difficulties:
            spec.key_difficulties.append(difficulty)

    for requirement in _extract_explicit_requirements(content):
        if requirement not in spec.additional_requirements:
            spec.additional_requirements.append(requirement)

    spec.unresolved_questions = _build_clarification_questions(spec)
    spec.confirmed = not spec.unresolved_questions
    explicit_signal_count = sum(
        bool(value)
        for value in [
            spec.education_stage,
            spec.subject,
            spec.lesson_title,
            spec.learning_objectives,
            spec.key_difficulties,
            spec.additional_requirements,
        ]
    )
    spec.confidence = min(0.95, 0.3 + explicit_signal_count * 0.1 + (0.1 if spec.confirmed else 0.0))
    spec.updated_at = utc_now()
    return spec


def process_user_message(
    session: SessionState,
    content: str,
    *,
    use_web_search: bool | None = None,
) -> tuple[SessionState, str]:
    settings = get_settings()
    session.messages.append(SessionMessage(role=MessageRole.USER, content=content))
    if use_web_search is not None:
        session.web_search_enabled = use_web_search

    if openai_dialog_ready(settings):
        try:
            session.teaching_spec = extract_teaching_spec_with_openai(
                session.teaching_spec,
                content,
                settings=settings,
            )
        except Exception:
            session.teaching_spec = _merge_spec(session.teaching_spec, content)
    else:
        session.teaching_spec = _merge_spec(session.teaching_spec, content)
    retrieval_hits = []
    if session.teaching_spec.subject and session.teaching_spec.lesson_title:
        retrieval_hits = fetch_retrieval_hits(
            session.teaching_spec,
            session=session,
            use_web_search=session.web_search_enabled,
        )
    session.retrieval_hits = retrieval_hits
    selected_hits = get_selected_retrieval_hits(session, retrieval_hits)
    session.stage = (
        SessionStage.PLANNING
        if session.teaching_spec.confirmed
        else SessionStage.CLARIFICATION
    )
    assistant_message = _build_assistant_message(session.teaching_spec, selected_hits)
    session.messages.append(
        SessionMessage(role=MessageRole.ASSISTANT, content=assistant_message)
    )
    session.last_summary = assistant_message
    session.updated_at = utc_now()
    return session, assistant_message
