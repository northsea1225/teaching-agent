from __future__ import annotations

from datetime import datetime, timezone
import re

from app.config import get_settings
from app.models import (
    Citation,
    InteractionMode,
    LessonOutline,
    LessonOutlineSection,
    RetrievalHit,
    SessionStage,
    SessionState,
    SlidePlan,
    SlidePlanItem,
    SlideType,
    TeachingSpec,
)
from app.services.rag import LocalKnowledgeBase, chunk_text
from app.services.evidence import get_selected_retrieval_hits
from app.services.openai_planner import (
    generate_lesson_outline_with_openai,
    openai_planner_ready,
)
from app.services.openai_evidence_rerank import (
    openai_evidence_rerank_ready,
    rerank_retrieval_hits_with_openai,
)
from app.services.openai_slide_planner import (
    SlidePlanDraft,
    SlidePlanSlideDraft,
    generate_slide_plan_draft_with_openai,
    openai_slide_planner_ready,
)
from app.services.openai_slide_regenerator import (
    SlideRegenerationDraft,
    generate_slide_regeneration_draft_with_openai,
    openai_slide_regenerator_ready,
)
from app.services.openai_speaker_notes import (
    polish_speaker_notes_with_openai,
    openai_speaker_notes_ready,
)
from app.services.storage import load_parsed_asset
from app.services.template_registry import select_template_id
from app.services.web_search import search_web_hits


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_retrieval_query(spec: TeachingSpec) -> str:
    parts = [
        spec.education_stage,
        spec.grade_level,
        spec.subject,
        spec.lesson_title,
        spec.lesson_topic,
    ]
    if spec.learning_objectives:
        parts.extend(objective.description for objective in spec.learning_objectives[:2])
    if spec.additional_requirements:
        parts.extend(spec.additional_requirements[:2])
    return " ".join(part for part in parts if part)


def _query_terms(spec: TeachingSpec) -> list[str]:
    candidates = [
        spec.lesson_title,
        spec.lesson_topic,
        spec.subject,
        spec.education_stage,
        spec.grade_level,
    ]
    candidates.extend(spec.additional_requirements[:3])

    terms: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        normalized = " ".join(str(candidate).split()).strip()
        if not normalized:
            continue
        if normalized not in terms:
            terms.append(normalized)
        for token in re.split(r"[\s,.;:，。；：/]+", normalized):
            token = token.strip()
            if len(token) >= 2 and token not in terms:
                terms.append(token)
    return terms


def _anchor_terms(text: str | None) -> list[str]:
    if not text:
        return []
    normalized = " ".join(str(text).split()).strip()
    if not normalized:
        return []

    terms = [normalized]
    for token in re.split(r"[\s,.;:，。；：/]+", normalized):
        token = token.strip()
        if len(token) >= 2 and token not in terms:
            terms.append(token)
    return terms


def _score_text_match(text: str, query_terms: list[str]) -> float:
    if not text:
        return 0.0

    haystack = text.lower()
    score = 0.0
    for term in query_terms:
        needle = term.lower().strip()
        if len(needle) < 2:
            continue
        if needle in haystack:
            score += 3.5 if len(needle) >= 4 else 2.0
        elif " " in needle:
            matched_tokens = sum(1 for token in needle.split() if len(token) >= 2 and token in haystack)
            if matched_tokens:
                score += matched_tokens * 0.8
    return score


def _hit_source_text(hit: RetrievalHit) -> str:
    parts = [hit.source_title, hit.page_label, hit.source_url]
    return " ".join(part.strip() for part in parts if part and part.strip())


def _fetch_session_asset_hits(
    session: SessionState | None,
    spec: TeachingSpec,
    top_k: int,
) -> list[RetrievalHit]:
    if session is None or not session.uploaded_files:
        return []

    query = build_retrieval_query(spec)
    query_terms = _query_terms(spec)
    scored_hits: list[RetrievalHit] = []

    for session_file in session.uploaded_files:
        if session_file.parse_status != "completed" or not session_file.parsed_path:
            continue

        parsed_asset = load_parsed_asset(session_file.parsed_path)
        if parsed_asset is None:
            continue

        source_text = parsed_asset.extracted_text.strip() or parsed_asset.text_preview.strip()
        if not source_text:
            continue

        chunks = chunk_text(source_text, 320, 60)
        if not chunks:
            chunks = [source_text[:320]]

        for chunk_index, chunk in enumerate(chunks, start=1):
            content = " ".join(chunk.split()).strip()
            if not content:
                continue
            score = _score_text_match(content, query_terms)
            score += _score_text_match(parsed_asset.text_preview, query_terms) * 0.5
            score += _score_text_match(session_file.filename, query_terms) * 0.3
            if score <= 0:
                continue

            scored_hits.append(
                RetrievalHit(
                    chunk_id=f"session-file:{session_file.file_id}:{chunk_index}",
                    asset_id=session_file.file_id,
                    content=content,
                    score=10.0 + score,
                    page_label=session_file.filename,
                    source_type="session-file",
                    source_title=session_file.filename,
                )
            )

    scored_hits.sort(key=lambda item: item.score or 0.0, reverse=True)
    return scored_hits[:top_k]


def _merge_hits(
    session_hits: list[RetrievalHit],
    kb_hits: list[RetrievalHit],
    web_hits: list[RetrievalHit],
    top_k: int,
) -> list[RetrievalHit]:
    merged: list[RetrievalHit] = []
    seen: set[tuple[str | None, str]] = set()

    for hit in session_hits + web_hits + kb_hits:
        content = " ".join(hit.content.split())
        key = (hit.asset_id or hit.source_url, content[:120])
        if not content or key in seen:
            continue
        seen.add(key)
        merged.append(hit)
        if len(merged) >= top_k:
            break
    return merged


def _rerank_hits(
    spec: TeachingSpec,
    hits: list[RetrievalHit],
    *,
    top_k: int,
) -> list[RetrievalHit]:
    hits = _sanitize_hits_for_spec(spec, hits)
    if not hits:
        return []

    query_terms = _query_terms(spec)
    anchor_terms = _anchor_terms(spec.lesson_title or spec.lesson_topic)
    support_terms = list(_subject_support_markers(spec))
    ranked: list[tuple[float, int, bool, RetrievalHit]] = []

    for index, hit in enumerate(hits):
        content = " ".join(hit.content.split()).strip()
        source_text = _hit_source_text(hit)
        combined_text = f"{content} {source_text}".strip()
        score = float(hit.score or 0.0)
        score += _score_text_match(content, query_terms)
        score += _score_text_match(source_text, query_terms) * 1.2
        if support_terms:
            score += _score_text_match(combined_text, support_terms) * 0.4

        anchor_match_count = sum(
            1
            for term in anchor_terms
            if len(term) >= 2 and term.lower() in combined_text.lower()
        )
        score += anchor_match_count * 5.0
        if anchor_terms and anchor_match_count == 0:
            score -= 3.5

        if hit.source_type == "session-file":
            score += 3.5
        elif hit.source_type == "knowledge-base":
            score += 2.0
        elif hit.source_type == "web":
            score += 0.5
        if hit.source_type == "knowledge-base" and not hit.source_title:
            score -= 1.5

        ranked.append((score, index, anchor_match_count > 0, hit))

    ranked.sort(key=lambda item: (item[2], item[0], -item[1]), reverse=True)
    return [item[3] for item in ranked[:top_k]]


def _rerank_hits_with_model(
    spec: TeachingSpec,
    hits: list[RetrievalHit],
    *,
    top_k: int,
    settings=None,
) -> list[RetrievalHit]:
    base_ranked = _rerank_hits(spec, hits, top_k=top_k)
    if not base_ranked:
        return []

    resolved_settings = settings or get_settings()
    if not openai_evidence_rerank_ready(resolved_settings):
        return base_ranked

    try:
        return rerank_retrieval_hits_with_openai(
            spec,
            base_ranked,
            top_k=top_k,
            settings=resolved_settings,
        )
    except Exception:
        return base_ranked


def fetch_retrieval_hits(
    spec: TeachingSpec,
    session: SessionState | None = None,
    store_namespace: str | None = None,
    top_k: int = 5,
    use_web_search: bool | None = None,
) -> list[RetrievalHit]:
    settings = get_settings()
    query = build_retrieval_query(spec).strip()
    candidate_top_k = max(top_k * 3, 8)
    session_hits = _fetch_session_asset_hits(session, spec, top_k=candidate_top_k)
    resolved_web_search = (
        use_web_search
        if use_web_search is not None
        else (session.web_search_enabled if session is not None else settings.web_search_enabled)
    )
    if not query:
        return _rerank_hits_with_model(
            spec,
            session_hits,
            top_k=top_k,
            settings=settings,
        )

    try:
        kb = LocalKnowledgeBase(namespace=store_namespace)
        topic_keywords = [
            item
            for item in [
                spec.lesson_title,
                spec.lesson_topic,
            ]
            if item
        ]
        try:
            kb_hits = kb.search(
                query,
                top_k=candidate_top_k,
                subject_filter=[spec.subject] if spec.subject else None,
                stage_filter=[spec.education_stage] if spec.education_stage else None,
                topic_keywords=topic_keywords or None,
            )
        except TypeError:
            kb_hits = kb.search(query, top_k=candidate_top_k)
    except Exception:
        kb_hits = []
    web_hits = (
        search_web_hits(query, top_k=max(settings.web_search_default_top_k, candidate_top_k))
        if resolved_web_search
        else []
    )
    merged_hits = _merge_hits(session_hits, kb_hits, web_hits, top_k=candidate_top_k)
    return _rerank_hits_with_model(
        spec,
        merged_hits,
        top_k=top_k,
        settings=settings,
    )


def _subject_family(subject: str | None) -> str:
    if subject in {"math", "physics", "chemistry", "biology", "science"}:
        return "stem"
    if subject in {"history", "geography", "politics", "chinese"}:
        return "humanities"
    if subject in {"english"}:
        return "language"
    return "general"


PLACEHOLDER_TEMPLATE_MARKERS = (
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
    "history": (
        "nahco3",
        "cl2",
        "cacl",
        "试剂",
        "蒸馏水",
        "饱和食盐水",
        "红纸编号",
        "次氯酸",
        "分液漏斗",
        "氟利昂",
        "聚氨酯",
        "二氧化硅",
        "输入法",
        "五笔",
        "函数",
    ),
    "humanities": (
        "nahco3",
        "cl2",
        "试剂",
        "蒸馏水",
        "饱和食盐水",
        "红纸编号",
        "次氯酸",
        "分液漏斗",
        "输入法",
        "五笔",
    ),
}
SUBJECT_SUPPORT_KEYWORDS = {
    "history": ("历史", "史料", "革命", "工业", "工厂", "蒸汽", "城市化", "制度", "社会", "工人"),
    "humanities": ("历史", "史料", "材料", "案例", "文本", "观点", "社会", "制度"),
}


def _normalize_compact_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _is_generic_objective_text(text: str) -> bool:
    normalized = _normalize_compact_text(text)
    if not normalized:
        return True
    return _contains_any_marker(normalized, GENERIC_OBJECTIVE_MARKERS)


def _subject_noise_markers(spec: TeachingSpec) -> tuple[str, ...]:
    family = _subject_family(spec.subject)
    if spec.subject and spec.subject in SUBJECT_NOISE_KEYWORDS:
        return SUBJECT_NOISE_KEYWORDS[spec.subject]
    return SUBJECT_NOISE_KEYWORDS.get(family, ())


def _subject_support_markers(spec: TeachingSpec) -> tuple[str, ...]:
    family = _subject_family(spec.subject)
    if spec.subject and spec.subject in SUBJECT_SUPPORT_KEYWORDS:
        return SUBJECT_SUPPORT_KEYWORDS[spec.subject]
    return SUBJECT_SUPPORT_KEYWORDS.get(family, ())


def _text_looks_cross_subject(spec: TeachingSpec, text: str) -> bool:
    normalized = _normalize_compact_text(text)
    if not normalized:
        return False

    noise_markers = _subject_noise_markers(spec)
    if not noise_markers or not _contains_any_marker(normalized, noise_markers):
        return False

    anchor_terms = _anchor_terms(spec.lesson_title or spec.lesson_topic)
    lowered = normalized.lower()
    if any(term.lower() in lowered for term in anchor_terms if len(term) >= 2):
        return False

    support_markers = _subject_support_markers(spec)
    if support_markers and _contains_any_marker(normalized, support_markers):
        return False

    return True


def _sanitize_text_items(
    spec: TeachingSpec,
    items: list[str],
    *,
    limit: int | None = None,
) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        normalized = _normalize_compact_text(item)
        if not normalized:
            continue
        if _contains_any_marker(normalized, PLACEHOLDER_TEMPLATE_MARKERS):
            continue
        if _text_looks_cross_subject(spec, normalized):
            continue
        cleaned.append(normalized)
    return _unique_texts(cleaned, limit=limit)


def _sanitize_hits_for_spec(
    spec: TeachingSpec,
    hits: list[RetrievalHit],
) -> list[RetrievalHit]:
    filtered: list[RetrievalHit] = []
    seen: set[tuple[str | None, str]] = set()

    for hit in hits:
        combined = _normalize_compact_text(
            " ".join(
                part
                for part in [hit.content, hit.source_title, hit.page_label, hit.source_url]
                if part
            )
        )
        if not combined:
            continue
        if _contains_any_marker(combined, PLACEHOLDER_TEMPLATE_MARKERS):
            continue
        if _text_looks_cross_subject(spec, combined):
            continue

        dedupe_key = (hit.asset_id or hit.source_url, combined[:160])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(hit)

    return filtered


def _build_retrieval_notes(hits: list[RetrievalHit], limit: int = 3) -> list[str]:
    return _evidence_notes_from_hits(hits, limit=limit)


MISSING_OBJECTIVE_NOTE = "当前需求未明确学习目标，先补充本课目标后再细化页面内容。"
MISSING_KNOWLEDGE_NOTE = "待补充本节核心知识证据，当前不自动扩展知识点。"
MISSING_MATERIAL_NOTE = "待补充教材、讲义或网页资料后，再细化材料分析与案例。"
MISSING_ACTIVITY_NOTE = "当前需求里未明确互动细节，建议先补充活动形式后再细化。"
MISSING_SUMMARY_NOTE = "请基于已确认目标回收重点，不新增未检索到的新知识。"
STRICT_CONSTRAINT_NOTE = "仅使用已确认需求和检索命中，不补写未提供的延伸内容。"

ACTIVITY_KEYWORDS = (
    "讨论",
    "活动",
    "任务",
    "练习",
    "实验",
    "辩论",
    "项目",
    "discussion",
    "task",
    "project",
    "quiz",
    "practice",
)
MATERIAL_KEYWORDS = (
    "材料",
    "史料",
    "图",
    "图表",
    "文本",
    "案例",
    "示例",
    "网页",
    "资料",
    "讲义",
    "source",
    "chart",
    "image",
    "document",
)


def _split_evidence_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [
        " ".join(part.split()).strip("，,、:：- ")
        for part in parts
        if " ".join(part.split()).strip("，,、:：- ")
    ]


def _evidence_notes_from_hits(
    hits: list[RetrievalHit],
    *,
    limit: int = 3,
    keywords: tuple[str, ...] | None = None,
    include_source: bool = False,
) -> list[str]:
    notes: list[str] = []
    lowered_keywords = tuple(keyword.lower() for keyword in keywords or ())

    for hit in hits:
        source_label = hit.source_title or hit.page_label or hit.source_type or "资料"
        for sentence in _split_evidence_sentences(hit.content):
            lowered_sentence = sentence.lower()
            if lowered_keywords and not any(keyword in lowered_sentence for keyword in lowered_keywords):
                continue
            snippet = sentence[:88]
            note = f"{source_label}：{snippet}" if include_source else snippet
            if note not in notes:
                notes.append(note)
            if len(notes) >= limit:
                return notes
    return notes


def _has_substantive_evidence(notes: list[str], missing_note: str) -> bool:
    return any(note and missing_note not in note for note in notes)


def _knowledge_point_notes(spec: TeachingSpec, limit: int = 3) -> list[str]:
    notes: list[str] = []
    for point in spec.core_knowledge_points:
        if point.description:
            notes.append(f"{point.title}：{point.description}")
        else:
            notes.append(point.title)
    return _unique_texts(notes, limit=limit)


def _build_requirement_notes(spec: TeachingSpec, limit: int = 4) -> list[str]:
    notes: list[str] = []
    notes.extend(
        objective.description
        for objective in spec.learning_objectives
        if not _is_generic_objective_text(objective.description)
    )
    notes.extend(_knowledge_point_notes(spec, limit=limit))
    notes.extend(
        f"重点难点：{item}" if not str(item).startswith("重点难点") else str(item)
        for item in spec.key_difficulties
    )
    notes.extend(spec.additional_requirements)
    if spec.teaching_methods:
        notes.append(f"教学方式优先：{', '.join(spec.teaching_methods[:2])}")
    if spec.assessment_methods:
        notes.append(f"评价方式：{', '.join(spec.assessment_methods[:2])}")
    notes = _sanitize_text_items(spec, notes, limit=max(limit - 1, 1))
    notes.append(STRICT_CONSTRAINT_NOTE)
    return _unique_texts(notes, limit=limit)


def _build_objective_notes(spec: TeachingSpec) -> list[str]:
    objective_notes = [
        objective.description
        for objective in spec.learning_objectives
        if not _is_generic_objective_text(objective.description)
    ]
    if objective_notes:
        return _unique_texts(objective_notes[:3], limit=3)

    fallback_notes: list[str] = []
    if spec.lesson_title:
        fallback_notes.append(f"本课课题：{spec.lesson_title}")
    elif spec.lesson_topic:
        fallback_notes.append(f"本课主题：{spec.lesson_topic}")
    fallback_notes.append(MISSING_OBJECTIVE_NOTE)
    fallback_notes.extend(spec.additional_requirements[:2])
    if spec.key_difficulties:
        fallback_notes.append(f"优先澄清并解决：{spec.key_difficulties[0]}")
    fallback_notes.extend(_knowledge_point_notes(spec, limit=1))
    if fallback_notes:
        return _sanitize_text_items(spec, fallback_notes, limit=3) or [MISSING_OBJECTIVE_NOTE]
    return [MISSING_OBJECTIVE_NOTE]


def _build_activity_notes(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit] | None = None,
) -> list[str]:
    notes: list[str] = []
    if spec.interaction_preferences:
        notes.extend(f"设计 {mode.value} 环节" for mode in spec.interaction_preferences)
    interaction_keywords = ("讨论", "项目", "小测", "练习", "实验", "辩论", "任务", "quiz", "project")
    notes.extend(
        item
        for item in spec.additional_requirements
        if any(keyword in item.lower() for keyword in interaction_keywords)
    )
    notes.extend(_evidence_notes_from_hits(retrieval_hits or [], limit=2, keywords=ACTIVITY_KEYWORDS))
    if spec.assessment_methods:
        notes.append(f"用 {', '.join(spec.assessment_methods[:2])} 检查课堂理解")
    if notes:
        sanitized = _sanitize_text_items(spec, notes, limit=3)
        if sanitized:
            return sanitized
    return [MISSING_ACTIVITY_NOTE]


def _build_knowledge_notes(
    spec: TeachingSpec,
    retrieval_notes: list[str],
    limit: int = 3,
) -> list[str]:
    notes = _knowledge_point_notes(spec, limit=limit)
    evidence_notes = retrieval_notes[:limit]
    if evidence_notes:
        notes.extend(evidence_notes)
    if spec.key_difficulties:
        notes.append(f"重点难点：{spec.key_difficulties[0]}")
    notes = _sanitize_text_items(spec, notes, limit=limit)
    return notes or [MISSING_KNOWLEDGE_NOTE]


def _build_material_notes(
    spec: TeachingSpec,
    retrieval_notes: list[str],
    retrieval_hits: list[RetrievalHit] | None = None,
    limit: int = 3,
) -> list[str]:
    notes: list[str] = []
    material_evidence = _evidence_notes_from_hits(
        retrieval_hits or [],
        limit=limit,
        keywords=MATERIAL_KEYWORDS,
        include_source=True,
    )
    if material_evidence:
        notes.extend(material_evidence)
    elif retrieval_notes:
        notes.extend(retrieval_notes[:limit])
    material_keywords = ("材料", "案例", "图", "图表", "史料", "文本", "示例", "网页", "资料", "讲义")
    notes.extend(
        item
        for item in spec.additional_requirements
        if any(keyword in item for keyword in material_keywords)
    )
    notes.extend(reference.name for reference in spec.references[:2])
    notes = _sanitize_text_items(spec, notes, limit=limit)
    return notes or [MISSING_MATERIAL_NOTE]


def _build_summary_notes(spec: TeachingSpec, limit: int = 3) -> list[str]:
    notes: list[str] = []
    notes.extend(f"回收难点：{item}" for item in spec.key_difficulties[:2])
    if spec.assessment_methods:
        notes.append(f"通过 {', '.join(spec.assessment_methods[:2])} 检查目标达成度")
    notes.extend(
        item
        for item in spec.additional_requirements
        if any(keyword in item for keyword in ("作业", "小测", "总结", "迁移", "复盘", "练习"))
    )
    if spec.learning_objectives:
        for objective in spec.learning_objectives:
            if not _is_generic_objective_text(objective.description):
                notes.append(f"回扣目标：{objective.description}")
                break
    notes = _sanitize_text_items(spec, notes, limit=limit)
    return notes or [MISSING_SUMMARY_NOTE]


def _estimate_section_slides(
    slide_type: SlideType,
    base_slides: int,
    *,
    evidence_ready: bool,
    activity_ready: bool,
) -> int:
    if base_slides <= 1:
        return 1
    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        return base_slides if activity_ready else 1
    if slide_type in {SlideType.CONCEPT, SlideType.PROCESS, SlideType.COMPARISON, SlideType.MEDIA, SlideType.TIMELINE}:
        return base_slides if evidence_ready else 1
    return base_slides


def _section_templates(subject_family: str) -> list[dict[str, object]]:
    if subject_family == "stem":
        return [
            {"title": "导入与目标", "goal": "建立问题情境并明确学习目标", "slides": 1, "type": SlideType.COVER},
            {"title": "概念与规律", "goal": "梳理核心概念、公式或规律", "slides": 2, "type": SlideType.CONCEPT},
            {"title": "例题与方法", "goal": "通过典型例题展示解题方法", "slides": 2, "type": SlideType.PROCESS},
            {"title": "练习与互动", "goal": "通过互动任务完成理解检验", "slides": 2, "type": SlideType.ACTIVITY},
            {"title": "总结与作业", "goal": "总结关键方法并布置作业", "slides": 1, "type": SlideType.SUMMARY},
        ]
    if subject_family == "humanities":
        return [
            {"title": "导入与目标", "goal": "建立背景与学习问题", "slides": 1, "type": SlideType.COVER},
            {"title": "核心内容梳理", "goal": "梳理重要事件、观点或文本线索", "slides": 2, "type": SlideType.CONCEPT},
            {"title": "材料与案例分析", "goal": "结合资料进行分析和比较", "slides": 2, "type": SlideType.COMPARISON},
            {"title": "课堂讨论", "goal": "围绕关键问题组织讨论与表达", "slides": 2, "type": SlideType.ACTIVITY},
            {"title": "总结与延伸", "goal": "回收观点并布置延伸任务", "slides": 1, "type": SlideType.SUMMARY},
        ]
    if subject_family == "language":
        return [
            {"title": "Lead-in and goals", "goal": "Build context and clarify learning goals", "slides": 1, "type": SlideType.COVER},
            {"title": "Input and vocabulary", "goal": "Introduce key language input and vocabulary", "slides": 2, "type": SlideType.CONCEPT},
            {"title": "Language focus", "goal": "Highlight grammar, structure, or reading strategies", "slides": 2, "type": SlideType.PROCESS},
            {"title": "Task and interaction", "goal": "Use speaking, discussion, or project tasks", "slides": 2, "type": SlideType.ACTIVITY},
            {"title": "Reflection and homework", "goal": "Summarize and assign follow-up practice", "slides": 1, "type": SlideType.SUMMARY},
        ]
    return [
        {"title": "导入与目标", "goal": "明确主题、目标与输出要求", "slides": 1, "type": SlideType.COVER},
        {"title": "核心知识", "goal": "梳理本节核心知识内容", "slides": 2, "type": SlideType.CONCEPT},
        {"title": "案例与材料", "goal": "结合资料展示案例和关键证据", "slides": 2, "type": SlideType.MEDIA},
        {"title": "互动与练习", "goal": "通过互动活动检验理解", "slides": 2, "type": SlideType.ACTIVITY},
        {"title": "总结与作业", "goal": "完成总结、迁移与作业安排", "slides": 1, "type": SlideType.SUMMARY},
    ]


def _chunk_points(points: list[str], target_chunks: int) -> list[list[str]]:
    if target_chunks <= 1:
        return [points[:]]
    if not points:
        return [[] for _ in range(target_chunks)]

    normalized_target = max(1, target_chunks)
    chunk_size = max(1, (len(points) + normalized_target - 1) // normalized_target)
    chunks = [
        points[index : index + chunk_size]
        for index in range(0, len(points), chunk_size)
    ]
    while len(chunks) < normalized_target:
        chunks.append([])
    return chunks[:normalized_target]


def _expand_slide_type(
    base_type: SlideType,
    subject_family: str,
    part_index: int,
    part_count: int,
) -> SlideType:
    if part_count <= 1 or part_index == 0:
        return base_type
    if base_type == SlideType.CONCEPT:
        if subject_family == "humanities":
            return SlideType.COMPARISON
        if subject_family == "language":
            return SlideType.PROCESS
        return SlideType.MEDIA
    if base_type == SlideType.ACTIVITY and part_index == part_count - 1:
        return SlideType.ASSIGNMENT
    return base_type


def _pick_interaction_mode(
    spec: TeachingSpec,
    slide_type: SlideType,
    part_index: int,
) -> InteractionMode:
    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        return spec.interaction_preferences[0] if spec.interaction_preferences else InteractionMode.DISCUSSION
    if slide_type == SlideType.SUMMARY and spec.interaction_preferences:
        return spec.interaction_preferences[min(part_index, len(spec.interaction_preferences) - 1)]
    return InteractionMode.NONE


def _layout_hint_for_slide(slide_type: SlideType) -> str:
    layout_map = {
        SlideType.COVER: "全幅标题区 + 目标标签栏 + 页脚来源提示",
        SlideType.AGENDA: "纵向流程轴 + 章节标签",
        SlideType.CONCEPT: "双栏卡片布局，左侧概念，右侧例子或图示",
        SlideType.TIMELINE: "时间线或阶段流程布局",
        SlideType.COMPARISON: "左右对照卡片布局，突出差异与联系",
        SlideType.PROCESS: "步骤卡片布局，突出先后顺序和方法",
        SlideType.MEDIA: "图文混排布局，保留资料摘录或图像说明区",
        SlideType.ACTIVITY: "任务说明 + 分组要求 + 输出提示",
        SlideType.SUMMARY: "要点回顾卡 + 退出问题",
        SlideType.ASSIGNMENT: "作业清单 + 评价标准卡片",
    }
    return layout_map.get(slide_type, "卡片式信息布局")


def _visual_brief_for_slide(
    slide_type: SlideType,
    section: LessonOutlineSection,
    spec: TeachingSpec,
    retrieval_notes: list[str],
) -> list[str]:
    notes: list[str] = []
    if slide_type == SlideType.COVER:
        notes.append("突出课题、学段、学科与本课目标")
    elif slide_type == SlideType.CONCEPT:
        notes.append("用 2 到 3 个知识卡片解释核心概念")
    elif slide_type == SlideType.COMPARISON:
        notes.append("将关键材料或观点做左右对比")
    elif slide_type == SlideType.PROCESS:
        notes.append("用步骤箭头展示方法或任务流程")
    elif slide_type == SlideType.MEDIA:
        notes.append("预留图片、资料摘录或示例题区域")
    elif slide_type == SlideType.ACTIVITY:
        notes.append("突出任务要求、互动规则与产出")
    elif slide_type == SlideType.ASSIGNMENT:
        notes.append("展示课后任务与评价标准")
    elif slide_type == SlideType.SUMMARY:
        notes.append("回收重点并安排一个退出问题")

    if spec.style_preferences:
        notes.append(f"整体风格偏向 {', '.join(spec.style_preferences[:2])}")
    if retrieval_notes and slide_type in {SlideType.CONCEPT, SlideType.COMPARISON, SlideType.MEDIA, SlideType.PROCESS}:
        notes.append(f"参考资料提示：{retrieval_notes[0]}")
    if section.recommended_slide_type == SlideType.ACTIVITY and slide_type == SlideType.ACTIVITY:
        notes.append("互动区尽量留出学生回答和教师点评位置")
    return _sanitize_text_items(spec, notes, limit=3)


def _speaker_notes_for_slide(
    section: LessonOutlineSection,
    spec: TeachingSpec,
    slide_type: SlideType,
    key_points: list[str],
    part_index: int,
) -> list[str]:
    notes = [f"本页目标：{section.goal}"]
    if key_points:
        notes.append(f"只围绕已确认要点展开：{'；'.join(key_points[:2])}")
    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        notes.append("仅围绕当前页已确认任务推进，不新增未检索到的活动规则")
    elif slide_type == SlideType.COVER:
        notes.append("先确认课题、目标与资料边界，再进入具体内容")
    elif spec.teaching_methods:
        notes.append(f"优先采用 {', '.join(spec.teaching_methods[:2])} 推进，并只引用已确认资料")
    else:
        notes.append("若资料不足，保留待补充提示，不延展未检索到的新知识")
        notes.append("若资料不足，保留待补充提示，不延展未检索到的新知识")
    if part_index > 0:
        notes.append("这一页只补充当前分段内容，不再扩写新的知识分支")
    return notes[:3]


def _citations_for_slide(
    retrieval_hits: list[RetrievalHit],
    slide_type: SlideType,
    limit: int = 2,
) -> list[Citation]:
    if slide_type not in {SlideType.CONCEPT, SlideType.COMPARISON, SlideType.PROCESS, SlideType.MEDIA, SlideType.SUMMARY}:
        return []

    citations: list[Citation] = []
    for hit in retrieval_hits[:limit]:
        note = hit.source_title or " ".join(hit.content.split())[:60]
        citations.append(
            Citation(
                asset_id=hit.asset_id or hit.source_url or "knowledge-base",
                chunk_id=hit.chunk_id,
                page_label=hit.page_label,
                note=note,
                source_type=hit.source_type,
                source_url=hit.source_url,
            )
        )
    return citations


def _pick_hits_for_slide(
    spec: TeachingSpec,
    section: LessonOutlineSection,
    slide_type: SlideType,
    retrieval_hits: list[RetrievalHit],
    *,
    limit: int = 4,
) -> list[RetrievalHit]:
    sanitized_hits = _sanitize_hits_for_spec(spec, retrieval_hits)
    if not sanitized_hits:
        return []

    base_terms = _anchor_terms(spec.lesson_title or spec.lesson_topic)
    base_terms.extend(_anchor_terms(section.title))
    base_terms.extend(_anchor_terms(section.goal))
    if slide_type in {SlideType.COMPARISON, SlideType.MEDIA}:
        base_terms.extend(MATERIAL_KEYWORDS[:6])
    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        base_terms.extend(ACTIVITY_KEYWORDS[:6])
    if slide_type == SlideType.SUMMARY:
        base_terms.extend(spec.key_difficulties[:2])
        base_terms.extend(
            objective.description
            for objective in spec.learning_objectives[:2]
            if not _is_generic_objective_text(objective.description)
        )

    ranked: list[tuple[float, int, RetrievalHit]] = []
    for index, hit in enumerate(sanitized_hits):
        combined = _normalize_compact_text(f"{hit.content} {_hit_source_text(hit)}")
        score = float(hit.score or 0.0)
        score += _score_text_match(combined, base_terms) * 1.4
        score += _score_text_match(combined, _query_terms(spec)) * 0.6
        if slide_type in {SlideType.COMPARISON, SlideType.MEDIA} and _contains_any_marker(combined, MATERIAL_KEYWORDS):
            score += 2.0
        if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT} and _contains_any_marker(combined, ACTIVITY_KEYWORDS):
            score += 2.5
        if hit.source_type == "knowledge-base" and not hit.source_title:
            score -= 1.5
        ranked.append((score, -index, hit))

    ranked.sort(reverse=True)
    picked = [hit for score, _, hit in ranked[:limit] if score > 0]
    if picked:
        return picked
    return sanitized_hits[:limit]


def _filter_hits_for_slide(
    retrieval_hits: list[RetrievalHit],
    slide: SlidePlanItem,
    limit: int = 4,
) -> list[RetrievalHit]:
    if not retrieval_hits or not slide.citations:
        return []

    asset_ids = {citation.asset_id for citation in slide.citations if citation.asset_id}
    chunk_ids = {citation.chunk_id for citation in slide.citations if citation.chunk_id}
    source_terms = {
        term.lower()
        for citation in slide.citations
        for term in [citation.note, citation.page_label]
        if term and term.strip()
    }

    filtered: list[RetrievalHit] = []
    seen: set[tuple[str | None, str]] = set()
    for hit in retrieval_hits:
        hit_source = " ".join(
            part.strip()
            for part in [hit.source_title, hit.page_label, hit.source_url]
            if part and part.strip()
        ).lower()
        matches_slide = (
            (hit.chunk_id in chunk_ids if hit.chunk_id else False)
            or (hit.asset_id in asset_ids if hit.asset_id else False)
            or any(term in hit_source for term in source_terms)
        )
        if not matches_slide:
            continue

        content = " ".join(hit.content.split()).strip()
        dedupe_key = (hit.asset_id or hit.source_url, content[:120])
        if not content or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(hit)
        if len(filtered) >= limit:
            break
    return filtered


def _theme_hint(spec: TeachingSpec, outline: LessonOutline) -> str:
    keywords = list(dict.fromkeys(outline.design_keywords + spec.style_preferences))
    subject = spec.subject or "general"
    stage = spec.education_stage or "general-stage"
    if keywords:
        return f"{stage} {subject} 课件，卡片式版面，关键词：{', '.join(keywords[:3])}"
    return f"{stage} {subject} 课件，卡片式版面，强调信息分层和课堂互动"


def _slide_title(section: LessonOutlineSection, part_index: int, part_count: int) -> str:
    if part_count <= 1 or part_index == 0:
        return section.title
    return f"{section.title} · {part_index + 1}/{part_count}"


def _unique_texts(items: list[str], limit: int | None = None) -> list[str]:
    unique_items: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if not normalized or normalized in unique_items:
            continue
        unique_items.append(normalized)
        if limit is not None and len(unique_items) >= limit:
            break
    return unique_items


def _find_slide_index(slide_plan: SlidePlan, slide_number: int) -> int:
    for index, slide in enumerate(slide_plan.slides):
        if slide.slide_number == slide_number:
            return index
    raise ValueError(f"Slide {slide_number} not found")


def _renumber_slide_plan(slide_plan: SlidePlan) -> SlidePlan:
    slides = [
        slide.model_copy(update={"slide_number": index + 1})
        for index, slide in enumerate(slide_plan.slides)
    ]
    return slide_plan.model_copy(update={"slides": slides, "total_slides": len(slides)})


def _invalidate_plan_outputs(session: SessionState) -> SessionState:
    session.svg_deck = None
    session.preview_deck = None
    session.stage = SessionStage.PLANNING
    session.updated_at = utc_now()
    return session


def _suggest_key_points_for_slide(
    spec: TeachingSpec,
    slide_type: SlideType,
    title: str,
    goal: str,
    retrieval_hits: list[RetrievalHit],
    instructions: str | None = None,
) -> list[str]:
    retrieval_notes = _build_retrieval_notes(retrieval_hits, limit=4)
    requirement_notes = _build_requirement_notes(spec, limit=4)
    knowledge_notes = _build_knowledge_notes(spec, retrieval_notes, limit=4)
    summary_notes = _build_summary_notes(spec, limit=4)
    candidates: list[str] = [goal]

    if slide_type == SlideType.COVER:
        candidates.extend(_build_objective_notes(spec)[:2])
        candidates.extend(requirement_notes[:1])
    elif slide_type in {SlideType.CONCEPT, SlideType.COMPARISON, SlideType.PROCESS, SlideType.MEDIA, SlideType.TIMELINE}:
        candidates.extend(knowledge_notes[:3])
    elif slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        candidates.extend(_build_activity_notes(spec, retrieval_hits)[:3])
        candidates.extend(retrieval_notes[:1])
    elif slide_type == SlideType.SUMMARY:
        candidates.extend(_build_objective_notes(spec)[:1])
        candidates.extend(summary_notes[:3])
    else:
        candidates.extend(requirement_notes[:2] or knowledge_notes[:2])
    if instructions:
        candidates.append(f"调整要求：{instructions}")
    return _sanitize_text_items(spec, candidates, limit=4)


def _build_manual_slide_item(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit],
    slide_number: int,
    title: str,
    goal: str,
    slide_type: SlideType,
    interaction_mode: InteractionMode | None = None,
    template_id: str | None = None,
    key_points: list[str] | None = None,
    visual_brief: list[str] | None = None,
    speaker_notes: list[str] | None = None,
    layout_hint: str | None = None,
    revision_notes: list[str] | None = None,
    instructions: str | None = None,
) -> SlidePlanItem:
    base_key_points = _unique_texts(
        _sanitize_text_items(
            spec,
            key_points or _suggest_key_points_for_slide(spec, slide_type, title, goal, retrieval_hits, instructions),
            limit=4,
        )
        or _suggest_key_points_for_slide(spec, slide_type, title, goal, retrieval_hits, instructions),
        limit=4,
    )
    section = LessonOutlineSection(
        title=title,
        goal=goal,
        bullet_points=base_key_points,
        estimated_slides=1,
        recommended_slide_type=slide_type,
    )
    retrieval_notes = _build_retrieval_notes(retrieval_hits, limit=4)
    final_visual_brief = _unique_texts(
        _sanitize_text_items(
            spec,
            visual_brief or _visual_brief_for_slide(slide_type, section, spec, retrieval_notes),
            limit=4,
        )
        or _visual_brief_for_slide(slide_type, section, spec, retrieval_notes),
        limit=4,
    )
    final_speaker_notes = _unique_texts(
        _sanitize_text_items(
            spec,
            speaker_notes or _speaker_notes_for_slide(section, spec, slide_type, base_key_points, 0),
            limit=4,
        )
        or _speaker_notes_for_slide(section, spec, slide_type, base_key_points, 0),
        limit=4,
    )
    final_revision_notes = _unique_texts((revision_notes or []) + ([instructions] if instructions else []), limit=5)
    return SlidePlanItem(
        slide_number=slide_number,
        slide_type=slide_type,
        title=title,
        goal=goal,
        template_id=template_id or select_template_id(slide_type, _subject_family(spec.subject)),
        key_points=base_key_points,
        visual_brief=final_visual_brief,
        speaker_notes=final_speaker_notes,
        interaction_mode=interaction_mode or _pick_interaction_mode(spec, slide_type, 0),
        citations=_citations_for_slide(retrieval_hits, slide_type),
        layout_hint=layout_hint or _layout_hint_for_slide(slide_type),
        revision_notes=final_revision_notes,
    )


def _normalize_slide_plan_type(value: str | SlideType | None) -> SlideType:
    if isinstance(value, SlideType):
        return value
    normalized = _normalize_compact_text(value).lower()
    aliases = {
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
    return aliases.get(normalized, SlideType.CONCEPT)


def _normalize_slide_plan_interaction(
    value: str | InteractionMode | None,
    *,
    fallback: InteractionMode,
) -> InteractionMode:
    if isinstance(value, InteractionMode):
        return value
    normalized = _normalize_compact_text(value).lower()
    try:
        return InteractionMode(normalized)
    except ValueError:
        return fallback


def _match_outline_section(
    draft_slide: SlidePlanSlideDraft,
    outline: LessonOutline,
) -> LessonOutlineSection:
    candidates = [
        _normalize_compact_text(draft_slide.section_title),
        _normalize_compact_text(draft_slide.title),
        _normalize_compact_text(draft_slide.goal),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        lowered = candidate.lower()
        for section in outline.sections:
            if lowered in _normalize_compact_text(section.title).lower():
                return section
    if outline.sections:
        return outline.sections[0]
    return LessonOutlineSection(
        title=_normalize_compact_text(draft_slide.section_title) or _normalize_compact_text(draft_slide.title) or "未命名章节",
        goal=_normalize_compact_text(draft_slide.goal) or "待补充本节目标",
        bullet_points=[],
        estimated_slides=1,
        recommended_slide_type=_normalize_slide_plan_type(draft_slide.slide_type),
    )


def _merge_slide_plan_draft(
    spec: TeachingSpec,
    outline: LessonOutline,
    draft: SlidePlanDraft,
    retrieval_hits: list[RetrievalHit],
) -> SlidePlan:
    hits = _sanitize_hits_for_spec(spec, retrieval_hits)
    subject_family = _subject_family(spec.subject)
    slides: list[SlidePlanItem] = []

    for index, draft_slide in enumerate(draft.slides, start=1):
        section = _match_outline_section(draft_slide, outline)
        slide_type = _normalize_slide_plan_type(draft_slide.slide_type)
        slide_hits = _pick_hits_for_slide(spec, section, slide_type, hits, limit=4)
        retrieval_notes = _build_retrieval_notes(slide_hits, limit=3)
        title = _normalize_compact_text(draft_slide.title) or _slide_title(section, 0, 1)
        goal = _normalize_compact_text(draft_slide.goal) or section.goal
        key_points = _sanitize_text_items(spec, draft_slide.key_points, limit=4)
        if not key_points:
            key_points = _suggest_key_points_for_slide(spec, slide_type, title, goal, slide_hits)[:3]
        visual_brief = _sanitize_text_items(spec, draft_slide.visual_brief, limit=4)
        if not visual_brief:
            visual_brief = _visual_brief_for_slide(slide_type, section, spec, retrieval_notes)
        speaker_notes = _sanitize_text_items(spec, draft_slide.speaker_notes, limit=4)
        if not speaker_notes:
            speaker_notes = _speaker_notes_for_slide(section, spec, slide_type, key_points, 0)
        fallback_mode = _pick_interaction_mode(spec, slide_type, 0)
        interaction_mode = _normalize_slide_plan_interaction(
            draft_slide.interaction_mode,
            fallback=fallback_mode,
        )
        revision_notes = _unique_texts(
            _sanitize_text_items(spec, draft_slide.revision_notes, limit=4) + [STRICT_CONSTRAINT_NOTE],
            limit=4,
        )

        slides.append(
            SlidePlanItem(
                slide_number=index,
                slide_type=slide_type,
                title=title,
                goal=goal,
                template_id=select_template_id(slide_type, subject_family),
                key_points=key_points,
                visual_brief=visual_brief,
                speaker_notes=speaker_notes,
                interaction_mode=interaction_mode,
                citations=_citations_for_slide(slide_hits, slide_type),
                layout_hint=_normalize_compact_text(draft_slide.layout_hint) or _layout_hint_for_slide(slide_type),
                revision_notes=revision_notes,
            )
        )

    lesson_title = spec.lesson_title or draft.title or outline.title
    theme_hint = _normalize_compact_text(draft.theme_hint) or _theme_hint(spec, outline)
    return SlidePlan(
        title=_normalize_compact_text(draft.title) or f"{lesson_title} slide plan",
        theme_hint=theme_hint,
        slides=slides,
    )


def _generate_slide_plan_rule_based(
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit] | None = None,
) -> SlidePlan:
    hits = _sanitize_hits_for_spec(spec, retrieval_hits or [])
    subject_family = _subject_family(spec.subject)
    slides: list[SlidePlanItem] = []
    slide_number = 1

    for section in outline.sections:
        part_count = max(1, section.estimated_slides)
        point_groups = _chunk_points(section.bullet_points, part_count)
        for part_index in range(part_count):
            slide_type = _expand_slide_type(
                section.recommended_slide_type or SlideType.CONCEPT,
                subject_family,
                part_index,
                part_count,
            )
            slide_title = (
                spec.lesson_title
                or spec.lesson_topic
                or section.title
                if slide_type == SlideType.COVER
                else _slide_title(section, part_index, part_count)
            )
            slide_hits = _pick_hits_for_slide(spec, section, slide_type, hits, limit=4)
            slide_retrieval_notes = _build_retrieval_notes(slide_hits, limit=3)
            key_points = _sanitize_text_items(spec, point_groups[part_index], limit=3)
            if not key_points:
                key_points = _suggest_key_points_for_slide(
                    spec,
                    slide_type,
                    slide_title,
                    section.goal,
                    slide_hits,
                )[:3]
            slides.append(
                SlidePlanItem(
                    slide_number=slide_number,
                    slide_type=slide_type,
                    title=slide_title,
                    goal=section.goal,
                    template_id=select_template_id(slide_type, subject_family),
                    key_points=key_points,
                    visual_brief=_visual_brief_for_slide(slide_type, section, spec, slide_retrieval_notes),
                    speaker_notes=_speaker_notes_for_slide(section, spec, slide_type, key_points, part_index),
                    interaction_mode=_pick_interaction_mode(spec, slide_type, part_index),
                    citations=_citations_for_slide(slide_hits, slide_type),
                    layout_hint=_layout_hint_for_slide(slide_type),
                    revision_notes=_unique_texts(spec.key_difficulties[:2] + [STRICT_CONSTRAINT_NOTE], limit=3),
                )
            )
            slide_number += 1

    lesson_title = spec.lesson_title or outline.title
    return SlidePlan(
        title=f"{lesson_title} slide plan",
        theme_hint=_theme_hint(spec, outline),
        slides=slides,
    )


def _polish_slide_plan_speaker_notes(
    spec: TeachingSpec,
    slide_plan: SlidePlan,
    retrieval_hits: list[RetrievalHit],
    *,
    settings=None,
) -> SlidePlan:
    resolved_settings = settings or get_settings()
    if not slide_plan.slides or not openai_speaker_notes_ready(resolved_settings):
        return slide_plan

    slide_hits_map = {
        slide.slide_number: _filter_hits_for_slide(retrieval_hits, slide, limit=4)
        for slide in slide_plan.slides
    }
    try:
        draft = polish_speaker_notes_with_openai(
            spec,
            slide_plan.slides,
            slide_hits_map,
            settings=resolved_settings,
        )
    except Exception:
        return slide_plan

    polished_by_number = {
        item.slide_number: _sanitize_text_items(spec, item.speaker_notes, limit=4)
        for item in draft.slides
    }
    updated_slides: list[SlidePlanItem] = []
    changed = False
    for slide in slide_plan.slides:
        polished_notes = polished_by_number.get(slide.slide_number) or []
        if polished_notes and polished_notes != slide.speaker_notes:
            changed = True
            updated_slides.append(
                slide.model_copy(
                    update={
                        "speaker_notes": polished_notes,
                        "revision_notes": _unique_texts(
                            slide.revision_notes + ["模型润色讲稿，仅调整口播表达"],
                            limit=5,
                        ),
                    }
                )
            )
        else:
            updated_slides.append(slide)

    if not changed:
        return slide_plan
    return slide_plan.model_copy(update={"slides": updated_slides})


def generate_slide_plan(
    spec: TeachingSpec,
    outline: LessonOutline,
    retrieval_hits: list[RetrievalHit] | None = None,
    *,
    allow_llm: bool = False,
) -> SlidePlan:
    hits = _sanitize_hits_for_spec(spec, retrieval_hits or [])
    settings = get_settings()
    slide_plan: SlidePlan | None = None
    if allow_llm and openai_slide_planner_ready(settings):
        try:
            draft = generate_slide_plan_draft_with_openai(spec, outline, hits, settings=settings)
            if draft.slides:
                slide_plan = _merge_slide_plan_draft(spec, outline, draft, hits)
        except Exception:
            pass
    if slide_plan is None:
        slide_plan = _generate_slide_plan_rule_based(spec, outline, hits)
    if allow_llm:
        return _polish_slide_plan_speaker_notes(
            spec,
            slide_plan,
            hits,
            settings=settings,
        )
    return slide_plan


def _merge_slide_regeneration_draft(
    spec: TeachingSpec,
    current: SlidePlanItem,
    draft: SlideRegenerationDraft,
    slide_hits: list[RetrievalHit],
    *,
    instructions: str | None = None,
) -> SlidePlanItem:
    subject_family = _subject_family(spec.subject)
    slide_type = (
        _normalize_slide_plan_type(draft.slide_type)
        if draft.slide_type
        else current.slide_type
    )
    title = _normalize_compact_text(draft.title) or current.title
    goal = _normalize_compact_text(draft.goal) or current.goal
    key_points = _sanitize_text_items(spec, draft.key_points, limit=4)
    if not key_points:
        key_points = current.key_points
    if not key_points:
        key_points = _suggest_key_points_for_slide(spec, slide_type, title, goal, slide_hits)[:3]

    visual_brief = _sanitize_text_items(spec, draft.visual_brief, limit=4)
    if not visual_brief:
        visual_brief = current.visual_brief

    speaker_notes = _sanitize_text_items(spec, draft.speaker_notes, limit=4)
    if not speaker_notes:
        speaker_notes = current.speaker_notes

    interaction_mode = _normalize_slide_plan_interaction(
        draft.interaction_mode,
        fallback=current.interaction_mode,
    )
    layout_hint = _normalize_compact_text(draft.layout_hint) or current.layout_hint or _layout_hint_for_slide(slide_type)
    citations = _citations_for_slide(slide_hits, slide_type) or current.citations
    draft_revision_notes = _sanitize_text_items(spec, draft.revision_notes, limit=3)
    revision_notes = _unique_texts(
        current.revision_notes
        + draft_revision_notes
        + ["模型单页再生成", "仅基于当前页引用和既有要点重组"]
        + ([instructions] if instructions else []),
        limit=5,
    )

    return current.model_copy(
        update={
            "slide_type": slide_type,
            "title": title,
            "goal": goal,
            "template_id": select_template_id(slide_type, subject_family),
            "key_points": key_points,
            "visual_brief": visual_brief,
            "speaker_notes": speaker_notes,
            "interaction_mode": interaction_mode,
            "citations": citations,
            "layout_hint": layout_hint,
            "revision_notes": revision_notes,
        }
    )


def _generate_lesson_outline_rule_based(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit] | None = None,
) -> LessonOutline:
    hits = _sanitize_hits_for_spec(spec, retrieval_hits or [])
    retrieval_notes = _build_retrieval_notes(hits)
    objective_notes = _build_objective_notes(spec)
    requirement_notes = _build_requirement_notes(spec)
    knowledge_notes = _build_knowledge_notes(spec, retrieval_notes)
    material_notes = _build_material_notes(spec, retrieval_notes, hits)
    activity_notes = _build_activity_notes(spec, hits)
    summary_notes = _build_summary_notes(spec)
    family = _subject_family(spec.subject)
    sections: list[LessonOutlineSection] = []
    knowledge_ready = bool(_knowledge_point_notes(spec, limit=1)) or bool(_evidence_notes_from_hits(hits, limit=1))
    material_ready = bool(_evidence_notes_from_hits(hits, limit=1, keywords=MATERIAL_KEYWORDS, include_source=True)) or bool(spec.references)
    activity_requirement_ready = any(
        keyword in item.lower()
        for item in spec.additional_requirements
        for keyword in ("讨论", "项目", "小测", "练习", "实验", "辩论", "任务", "quiz", "project")
    )
    activity_ready = bool(spec.interaction_preferences or spec.assessment_methods or activity_requirement_ready) or bool(
        _evidence_notes_from_hits(hits, limit=1, keywords=ACTIVITY_KEYWORDS)
    )

    templates = _section_templates(family)
    for index, template in enumerate(templates):
        bullet_points: list[str] = []
        if index == 0:
            bullet_points.extend(objective_notes[:2])
            if len(bullet_points) < 2:
                bullet_points.extend(requirement_notes[: 2 - len(bullet_points)])
            if spec.class_duration_minutes:
                bullet_points.append(f"课时建议: {spec.class_duration_minutes} 分钟")
        elif index == 1:
            bullet_points.extend(knowledge_notes[:3])
        elif index == 2:
            bullet_points.extend(material_notes[:3])
        elif index == 3:
            bullet_points.extend(activity_notes[:3])
        else:
            bullet_points.extend(summary_notes[:3])

        recommended_type = template["type"]  # type: ignore[assignment]
        if recommended_type in {SlideType.CONCEPT, SlideType.PROCESS, SlideType.TIMELINE}:
            evidence_ready = knowledge_ready
        elif recommended_type in {SlideType.COMPARISON, SlideType.MEDIA}:
            evidence_ready = material_ready
        else:
            evidence_ready = knowledge_ready or material_ready
        estimated_slides = _estimate_section_slides(
            recommended_type,
            int(template["slides"]),
            evidence_ready=evidence_ready,
            activity_ready=activity_ready,
        )

        sections.append(
            LessonOutlineSection(
                title=str(template["title"]),
                goal=str(template["goal"]),
                bullet_points=_unique_texts(bullet_points, limit=4),
                estimated_slides=estimated_slides,
                recommended_slide_type=recommended_type,  # type: ignore[arg-type]
            )
        )

    title = spec.lesson_title or "Untitled lesson"
    summary = f"基于 {len(hits)} 条检索资料和当前教学需求生成的约束版课程大纲。"
    if len(hits) == 0:
        summary += " 当前未命中可用资料，缺失部分以“待补充”保留，并自动收缩页面数量。"
    elif len(hits) < 2:
        summary += " 当前命中资料较少，已收缩内容页数量，并优先保留有证据支撑的部分。"
    design_keywords = list(dict.fromkeys(spec.style_preferences + [mode.value for mode in spec.interaction_preferences]))

    return LessonOutline(
        title=f"{title} lesson outline",
        summary=summary,
        sections=sections,
        design_keywords=design_keywords,
    )


def generate_lesson_outline(
    spec: TeachingSpec,
    retrieval_hits: list[RetrievalHit] | None = None,
    *,
    allow_llm: bool = False,
) -> LessonOutline:
    hits = _sanitize_hits_for_spec(spec, retrieval_hits or [])
    settings = get_settings()
    if allow_llm and openai_planner_ready(settings):
        try:
            return generate_lesson_outline_with_openai(spec, hits, settings=settings)
        except Exception:
            pass
    return _generate_lesson_outline_rule_based(spec, hits)


def generate_outline_for_session(
    session: SessionState,
    store_namespace: str | None = None,
    top_k: int = 5,
    use_web_search: bool | None = None,
) -> SessionState:
    if session.teaching_spec is None:
        raise ValueError("Session has no teaching spec")

    retrieval_hits = fetch_retrieval_hits(
        session.teaching_spec,
        session=session,
        store_namespace=store_namespace,
        top_k=top_k,
        use_web_search=use_web_search,
    )
    session.retrieval_hits = retrieval_hits
    selected_hits = get_selected_retrieval_hits(session, retrieval_hits)
    outline = generate_lesson_outline(
        session.teaching_spec,
        selected_hits,
        allow_llm=True,
    )
    session.outline = outline
    session.stage = SessionStage.PLANNING
    session.last_summary = outline.summary
    session.updated_at = utc_now()
    return session


def generate_slide_plan_for_session(
    session: SessionState,
    store_namespace: str | None = None,
    top_k: int = 5,
    use_web_search: bool | None = None,
) -> SessionState:
    if session.teaching_spec is None:
        raise ValueError("Session has no teaching spec")

    if session.outline is None:
        session = generate_outline_for_session(
            session,
            store_namespace=store_namespace,
            top_k=top_k,
            use_web_search=use_web_search,
        )

    slide_plan = generate_slide_plan(
        session.teaching_spec,
        session.outline,
        get_selected_retrieval_hits(session),
        allow_llm=True,
    )
    session.slide_plan = slide_plan
    session.svg_deck = None
    session.stage = SessionStage.PLANNING
    session.last_summary = f"已生成 {slide_plan.total_slides} 页逐页策划，可进入预览生成。"
    session.updated_at = utc_now()
    return session


def update_slide_in_session(
    session: SessionState,
    slide_number: int,
    *,
    title: str | None = None,
    goal: str | None = None,
    slide_type: SlideType | None = None,
    key_points: list[str] | None = None,
    visual_brief: list[str] | None = None,
    speaker_notes: list[str] | None = None,
    interaction_mode: InteractionMode | None = None,
    layout_hint: str | None = None,
    revision_note: str | None = None,
) -> SessionState:
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(session)

    assert session.slide_plan is not None
    index = _find_slide_index(session.slide_plan, slide_number)
    current = session.slide_plan.slides[index]

    updated = current.model_copy(
        update={
            "title": title if title is not None else current.title,
            "goal": goal if goal is not None else current.goal,
            "slide_type": slide_type if slide_type is not None else current.slide_type,
            "template_id": select_template_id(
                slide_type if slide_type is not None else current.slide_type,
                _subject_family(session.teaching_spec.subject),
            ),
            "key_points": _unique_texts(key_points, limit=4) if key_points is not None else current.key_points,
            "visual_brief": _unique_texts(visual_brief, limit=4) if visual_brief is not None else current.visual_brief,
            "speaker_notes": _unique_texts(speaker_notes, limit=4) if speaker_notes is not None else current.speaker_notes,
            "interaction_mode": interaction_mode if interaction_mode is not None else current.interaction_mode,
            "layout_hint": layout_hint if layout_hint is not None else current.layout_hint,
            "revision_notes": _unique_texts(
                current.revision_notes + ([revision_note] if revision_note else []),
                limit=5,
            ),
        }
    )
    slides = session.slide_plan.slides[:]
    slides[index] = updated
    session.slide_plan = _renumber_slide_plan(session.slide_plan.model_copy(update={"slides": slides}))
    session = _invalidate_plan_outputs(session)
    session.last_summary = f"已更新第 {slide_number} 页内容。"
    return session


def move_slide_in_session(
    session: SessionState,
    from_slide_number: int,
    to_position: int,
) -> SessionState:
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(session)

    assert session.slide_plan is not None
    slides = session.slide_plan.slides[:]
    from_index = _find_slide_index(session.slide_plan, from_slide_number)
    target_index = max(0, min(len(slides) - 1, to_position - 1))
    slide = slides.pop(from_index)
    slides.insert(target_index, slide)
    session.slide_plan = _renumber_slide_plan(session.slide_plan.model_copy(update={"slides": slides}))
    session = _invalidate_plan_outputs(session)
    session.last_summary = f"已将第 {from_slide_number} 页移动到第 {target_index + 1} 位。"
    return session


def delete_slide_from_session(
    session: SessionState,
    slide_number: int,
) -> SessionState:
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(session)

    assert session.slide_plan is not None
    if len(session.slide_plan.slides) <= 1:
        raise ValueError("Slide plan must contain at least one slide")

    slides = session.slide_plan.slides[:]
    index = _find_slide_index(session.slide_plan, slide_number)
    slides.pop(index)
    session.slide_plan = _renumber_slide_plan(session.slide_plan.model_copy(update={"slides": slides}))
    session = _invalidate_plan_outputs(session)
    session.last_summary = f"已删除第 {slide_number} 页。"
    return session


def insert_slide_into_session(
    session: SessionState,
    position: int,
    *,
    title: str,
    goal: str,
    slide_type: SlideType = SlideType.CONCEPT,
    interaction_mode: InteractionMode | None = None,
    key_points: list[str] | None = None,
    visual_brief: list[str] | None = None,
    speaker_notes: list[str] | None = None,
    layout_hint: str | None = None,
    revision_note: str | None = None,
) -> SessionState:
    if session.teaching_spec is None:
        raise ValueError("Session has no teaching spec")
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(session)

    assert session.slide_plan is not None
    insertion_index = max(0, min(len(session.slide_plan.slides), position - 1))
    new_item = _build_manual_slide_item(
        session.teaching_spec,
        session.retrieval_hits,
        slide_number=insertion_index + 1,
        title=title,
        goal=goal,
        slide_type=slide_type,
        interaction_mode=interaction_mode,
        template_id=select_template_id(slide_type, _subject_family(session.teaching_spec.subject)),
        key_points=key_points,
        visual_brief=visual_brief,
        speaker_notes=speaker_notes,
        layout_hint=layout_hint,
        revision_notes=[revision_note] if revision_note else ["manual insert"],
    )
    slides = session.slide_plan.slides[:]
    slides.insert(insertion_index, new_item)
    session.slide_plan = _renumber_slide_plan(session.slide_plan.model_copy(update={"slides": slides}))
    session = _invalidate_plan_outputs(session)
    session.last_summary = f"已在第 {insertion_index + 1} 位插入新页面。"
    return session


def regenerate_slide_in_session(
    session: SessionState,
    slide_number: int,
    instructions: str | None = None,
) -> SessionState:
    if session.teaching_spec is None:
        raise ValueError("Session has no teaching spec")
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(session)
    if not session.retrieval_hits:
        session.retrieval_hits = fetch_retrieval_hits(
            session.teaching_spec,
            session=session,
            use_web_search=session.web_search_enabled,
        )

    assert session.slide_plan is not None
    index = _find_slide_index(session.slide_plan, slide_number)
    current = session.slide_plan.slides[index]
    slide_hits = _filter_hits_for_slide(get_selected_retrieval_hits(session), current, limit=4)
    preserve_existing_content = (
        current.slide_type in {SlideType.CONCEPT, SlideType.COMPARISON, SlideType.PROCESS, SlideType.MEDIA, SlideType.TIMELINE, SlideType.SUMMARY}
        and not slide_hits
    )
    regenerated = None
    settings = get_settings()
    regenerator_llm_ready = openai_slide_regenerator_ready(settings)
    if regenerator_llm_ready:
        try:
            draft = generate_slide_regeneration_draft_with_openai(
                session.teaching_spec,
                current,
                slide_hits,
                instructions=instructions,
                settings=settings,
            )
            regenerated = _merge_slide_regeneration_draft(
                session.teaching_spec,
                current,
                draft,
                slide_hits,
                instructions=instructions,
            )
        except Exception:
            regenerated = None

    if regenerated is None:
        regenerated = _build_manual_slide_item(
            session.teaching_spec,
            slide_hits,
            slide_number=current.slide_number,
            title=current.title,
            goal=current.goal,
            slide_type=current.slide_type,
            interaction_mode=current.interaction_mode,
            template_id=current.template_id,
            key_points=current.key_points if preserve_existing_content else None,
            speaker_notes=(
                _unique_texts(
                    current.speaker_notes + ["仅基于当前页既有要点重组，缺少引用时不扩写新结构。"],
                    limit=4,
                )
                if preserve_existing_content
                else None
            ),
            layout_hint=current.layout_hint,
            revision_notes=current.revision_notes + ["regenerated", "仅基于当前页引用和既有要点重组"],
            instructions=instructions,
        )
        if preserve_existing_content and current.citations:
            regenerated = regenerated.model_copy(update={"citations": current.citations})
    if regenerator_llm_ready and openai_speaker_notes_ready(settings):
        try:
            notes_draft = polish_speaker_notes_with_openai(
                session.teaching_spec,
                [regenerated],
                {regenerated.slide_number: slide_hits},
                settings=settings,
            )
            polished_notes = _sanitize_text_items(
                session.teaching_spec,
                next(
                    (
                        item.speaker_notes
                        for item in notes_draft.slides
                        if item.slide_number == regenerated.slide_number
                    ),
                    [],
                ),
                limit=4,
            )
            if polished_notes:
                regenerated = regenerated.model_copy(
                    update={
                        "speaker_notes": polished_notes,
                        "revision_notes": _unique_texts(
                            regenerated.revision_notes + ["模型润色讲稿，仅调整口播表达"],
                            limit=5,
                        ),
                    }
                )
        except Exception:
            pass
    slides = session.slide_plan.slides[:]
    slides[index] = regenerated
    session.slide_plan = _renumber_slide_plan(session.slide_plan.model_copy(update={"slides": slides}))
    session = _invalidate_plan_outputs(session)
    session.last_summary = f"已重新生成第 {slide_number} 页。"
    return session
