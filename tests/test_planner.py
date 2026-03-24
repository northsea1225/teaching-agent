from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import (
    Citation,
    InteractionMode,
    LessonOutline,
    LessonOutlineSection,
    RetrievalHit,
    SessionState,
    SlidePlan,
    SlidePlanItem,
    SlideType,
    TeachingSpec,
)
from app.services.evidence import get_selected_retrieval_hits, set_excluded_retrieval_hits
from app.services.openai_slide_regenerator import SlideRegenerationDraft
from app.services.openai_speaker_notes import (
    SpeakerNotesDeckDraft,
    SpeakerNotesSlideDraft,
)
from app.services.planner import fetch_retrieval_hits, generate_lesson_outline, generate_slide_plan, regenerate_slide_in_session
from app.services.quality import build_quality_report


client = TestClient(app)


def _make_kb_dir() -> Path:
    settings = get_settings()
    path = settings.knowledge_base_dir / f"_planner_tests_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_session_artifacts(session_id: str) -> None:
    settings = get_settings()
    shutil.rmtree(settings.raw_data_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.parsed_data_dir / session_id, ignore_errors=True)
    shutil.rmtree(settings.exports_dir / session_id, ignore_errors=True)


def test_generate_lesson_outline_builds_sections() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="math",
        lesson_title="一次函数",
        class_duration_minutes=50,
    )
    hits = [
        RetrievalHit(
            chunk_id="1",
            content="一次函数的图像是一条直线，k 决定倾斜方向，b 决定与 y 轴交点。",
        )
    ]
    outline = generate_lesson_outline(spec, hits)
    assert outline.sections
    assert outline.total_slides >= 5
    assert any("一次函数" in item for section in outline.sections for item in section.bullet_points)


def test_generate_slide_plan_builds_page_level_cards() -> None:
    spec = TeachingSpec(
        education_stage="high-school",
        subject="english",
        lesson_title="Environment Protection",
        class_duration_minutes=40,
        interaction_preferences=[InteractionMode.DISCUSSION, InteractionMode.PROJECT],
        style_preferences=["简洁", "可视化"],
    )
    hits = [
        RetrievalHit(
            chunk_id="eng-1",
            asset_id="english-asset",
            content="Environment Protection lessons can include vocabulary scaffolds, discussion prompts, and project tasks.",
            page_label="p1",
        )
    ]
    outline = generate_lesson_outline(spec, hits)
    slide_plan = generate_slide_plan(spec, outline, hits)

    assert slide_plan.slides
    assert slide_plan.total_slides == len(slide_plan.slides)
    assert slide_plan.theme_hint is not None
    assert any(slide.slide_type == SlideType.ACTIVITY for slide in slide_plan.slides)
    assert any(slide.interaction_mode == InteractionMode.DISCUSSION for slide in slide_plan.slides)
    assert any(slide.citations for slide in slide_plan.slides if slide.slide_type != SlideType.COVER)


def test_generate_lesson_outline_marks_missing_content_instead_of_inventing() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
    )

    outline = generate_lesson_outline(spec, [])
    all_points = [point for section in outline.sections for point in section.bullet_points]

    assert any("当前需求未明确学习目标" in point for point in all_points)
    assert any("待补充本节核心知识证据" in point for point in all_points)
    assert any("待补充教材、讲义或网页资料后" in point for point in all_points)
    assert outline.summary is not None
    assert "待补充" in outline.summary


def test_generate_slide_plan_prefers_requirements_and_hits() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        interaction_preferences=[InteractionMode.DISCUSSION],
        key_difficulties=["理解蒸汽机与工厂制度的关系"],
        additional_requirements=["加入材料分析", "不要扩展到未提供的课外史实"],
    )
    hits = [
        RetrievalHit(
            chunk_id="history-1",
            asset_id="history-asset",
            content="蒸汽机推动工厂生产，工厂制度改变了劳动组织，并带来城市化影响。",
            source_type="knowledge-base",
            source_title="教材第12页",
        )
    ]

    outline = generate_lesson_outline(spec, hits)
    slide_plan = generate_slide_plan(spec, outline, hits)

    all_key_points = [point for slide in slide_plan.slides for point in slide.key_points]
    all_speaker_notes = [note for slide in slide_plan.slides for note in slide.speaker_notes]

    assert any("蒸汽机" in point for point in all_key_points)
    assert any("加入材料分析" in point or "discussion" in point for point in all_key_points)
    assert any(
        "不新增未检索到的新知识" in note
        or "不新增未检索到的活动规则" in note
        or "保留待补充提示" in note
        for note in all_speaker_notes
    )


def test_low_evidence_outline_compresses_pages_and_keeps_placeholders() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["加入材料分析"],
    )

    outline = generate_lesson_outline(spec, [])
    slide_plan = generate_slide_plan(spec, outline, [])

    assert outline.total_slides == len(slide_plan.slides)
    assert outline.total_slides <= 5
    assert any("待补充" in point for slide in slide_plan.slides for point in slide.key_points)
    assert any(
        "不补写未提供的延伸内容" in note
        for slide in slide_plan.slides
        for note in slide.revision_notes
    )


def test_quality_report_flags_uncited_content_when_evidence_is_missing() -> None:
    spec = TeachingSpec(
        education_stage="high-school",
        subject="english",
        lesson_title="Environment Protection",
        learning_objectives=[{"description": "围绕环境保护组织讨论"}],
    )
    outline = generate_lesson_outline(spec, [])
    slide_plan = generate_slide_plan(spec, outline, [])

    report = build_quality_report(
        SessionState(
            title="quality-temp",
            teaching_spec=spec,
            outline=outline,
            slide_plan=slide_plan,
            retrieval_hits=[],
        )
    )

    assert any(issue.code in {"unsupported_content_risk", "missing_citation"} for issue in report.issues)
    assert any(issue.code == "low_evidence" for issue in report.issues)


def test_manual_evidence_selection_filters_generation_hits() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "理解工业革命与工厂制度"}],
    )
    session = SessionState(
        title="evidence-filter",
        teaching_spec=spec,
        retrieval_hits=[
            RetrievalHit(
                chunk_id="history-hit",
                content="工业革命推动工厂制度和城市化发展。",
                score=9.0,
                source_type="knowledge-base",
                source_title="历史教材",
            ),
            RetrievalHit(
                chunk_id="chem-hit",
                content="NaHCO3 受热分解并生成新的物质。",
                score=8.0,
                source_type="knowledge-base",
                source_title="化学练习册",
            ),
        ],
    )

    session = set_excluded_retrieval_hits(session, ["chem-hit"])
    selected_hits = get_selected_retrieval_hits(session)

    assert len(selected_hits) == 1
    assert selected_hits[0].chunk_id == "history-hit"


def test_fetch_retrieval_hits_prefers_title_anchored_sources(monkeypatch) -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["加入材料分析"],
    )

    def fake_kb_search(self, query: str, top_k: int) -> list[RetrievalHit]:
        assert "工业革命" in query
        return [
            RetrievalHit(
                chunk_id="web-generic",
                content="课堂讨论案例库，适合多种历史课。",
                score=12.0,
                source_type="web",
                source_title="教学案例库",
            ),
            RetrievalHit(
                chunk_id="kb-anchored",
                content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
                score=6.0,
                source_type="knowledge-base",
                source_title="工业革命教材第12页",
            ),
            RetrievalHit(
                chunk_id="kb-generic",
                content="工厂制度改变了社会结构和劳动组织。",
                score=9.0,
                source_type="knowledge-base",
                source_title="教材第13页",
            ),
        ]

    monkeypatch.setattr("app.services.planner.LocalKnowledgeBase.search", fake_kb_search)
    monkeypatch.setattr("app.services.planner.search_web_hits", lambda query, top_k: [])

    hits = fetch_retrieval_hits(spec, top_k=2, use_web_search=False)

    assert hits
    assert hits[0].chunk_id == "kb-anchored"


def test_fetch_retrieval_hits_filters_cross_subject_contamination(monkeypatch) -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["加入材料分析和讨论"],
    )

    def fake_kb_search(self, query: str, top_k: int) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                chunk_id="history-good",
                content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
                score=5.0,
                source_type="knowledge-base",
                source_title="工业革命教材第12页",
            ),
            RetrievalHit(
                chunk_id="chem-bad",
                content="红纸编号 试剂 红纸变化 ② 蒸馏水 ③ 饱和食盐水 ④ NaHCO3溶液(调至pH＝7)",
                score=9.0,
                source_type="knowledge-base",
                source_title="化学练习册第57页",
            ),
            RetrievalHit(
                chunk_id="template-bad",
                content="31：参照模板中的内容输入文本",
                score=10.0,
                source_type="knowledge-base",
                source_title="模板页",
            ),
        ]

    monkeypatch.setattr("app.services.planner.LocalKnowledgeBase.search", fake_kb_search)
    monkeypatch.setattr("app.services.planner.search_web_hits", lambda query, top_k: [])

    hits = fetch_retrieval_hits(spec, top_k=5, use_web_search=False)

    chunk_ids = {hit.chunk_id for hit in hits}
    assert "history-good" in chunk_ids
    assert "chem-bad" not in chunk_ids
    assert "template-bad" not in chunk_ids


def test_fetch_retrieval_hits_uses_ai_evidence_rerank_when_available(monkeypatch) -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["加入材料分析和讨论"],
    )

    def fake_kb_search(self, query: str, top_k: int, **kwargs) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                chunk_id="history-core",
                content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
                score=9.0,
                source_type="knowledge-base",
                source_title="工业革命教材第12页",
            ),
            RetrievalHit(
                chunk_id="history-side",
                content="工人生活与工厂纪律变化也影响了社会结构。",
                score=8.0,
                source_type="knowledge-base",
                source_title="工业革命材料包",
            ),
        ]

    def fake_ai_rerank(spec_arg, hits: list[RetrievalHit], *, top_k: int, settings=None) -> list[RetrievalHit]:
        assert spec_arg.lesson_title == "工业革命"
        assert top_k == 2
        return [
            hits[1].model_copy(update={"topic_hint": "社会结构变化"}),
            hits[0].model_copy(update={"topic_hint": "蒸汽机与工厂制度"}),
        ]

    monkeypatch.setattr("app.services.planner.LocalKnowledgeBase.search", fake_kb_search)
    monkeypatch.setattr("app.services.planner.search_web_hits", lambda query, top_k: [])
    monkeypatch.setattr("app.services.planner.openai_evidence_rerank_ready", lambda settings: True)
    monkeypatch.setattr("app.services.planner.rerank_retrieval_hits_with_openai", fake_ai_rerank)

    hits = fetch_retrieval_hits(spec, top_k=2, use_web_search=False)

    assert [hit.chunk_id for hit in hits] == ["history-side", "history-core"]
    assert hits[0].topic_hint == "社会结构变化"


def test_fetch_retrieval_hits_falls_back_to_rule_rerank_when_ai_rerank_fails(monkeypatch) -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        additional_requirements=["加入材料分析"],
    )

    def fake_kb_search(self, query: str, top_k: int, **kwargs) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                chunk_id="history-anchored",
                content="工业革命推动蒸汽机和工厂制度发展，并带来城市化影响。",
                score=5.0,
                source_type="knowledge-base",
                source_title="工业革命教材第12页",
            ),
            RetrievalHit(
                chunk_id="history-generic",
                content="社会结构变化会影响劳动组织和城市生活。",
                score=9.0,
                source_type="knowledge-base",
                source_title="教材第13页",
            ),
        ]

    monkeypatch.setattr("app.services.planner.LocalKnowledgeBase.search", fake_kb_search)
    monkeypatch.setattr("app.services.planner.search_web_hits", lambda query, top_k: [])
    monkeypatch.setattr("app.services.planner.openai_evidence_rerank_ready", lambda settings: True)
    monkeypatch.setattr(
        "app.services.planner.rerank_retrieval_hits_with_openai",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("gateway down")),
    )

    hits = fetch_retrieval_hits(spec, top_k=2, use_web_search=False)

    assert hits
    assert hits[0].chunk_id == "history-anchored"


def test_quality_report_flags_activity_and_summary_structure_gaps() -> None:
    spec = TeachingSpec(
        education_stage="high-school",
        subject="english",
        lesson_title="Environment Protection",
        learning_objectives=[{"description": "围绕环境议题组织讨论并形成结论"}],
    )
    report = build_quality_report(
        SessionState(
            title="structure-gaps",
            teaching_spec=spec,
            retrieval_hits=[
                RetrievalHit(
                    chunk_id="eng-1",
                    asset_id="eng-asset",
                    content="Environment Protection requires discussion and evidence cards.",
                    source_type="knowledge-base",
                    source_title="Workbook p.14",
                )
            ],
            slide_plan=SlidePlan(
                title="Environment Protection",
                slides=[
                    SlidePlanItem(
                        slide_number=1,
                        title="Task Board",
                        slide_type=SlideType.ACTIVITY,
                        goal="组织活动",
                        interaction_mode=InteractionMode.NONE,
                        key_points=["介绍背景知识"],
                    ),
                    SlidePlanItem(
                        slide_number=2,
                        title="Wrap-up",
                        slide_type=SlideType.SUMMARY,
                        goal="总结课程",
                        key_points=["回顾今天的知识点"],
                        citations=[
                            Citation(asset_id="eng-asset", note="Workbook p.14"),
                        ],
                    ),
                ],
            ),
        )
    )

    assert any(issue.code == "activity_missing_interaction" for issue in report.issues)
    assert any(issue.code == "activity_structure_weak" for issue in report.issues)
    assert any(issue.code == "summary_goal_unlinked" for issue in report.issues)


def test_quality_report_flags_cross_subject_contamination_and_template_leaks() -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "是交给学生这节课的内容"}],
    )
    report = build_quality_report(
        SessionState(
            title="history-polluted",
            teaching_spec=spec,
            retrieval_hits=[
                RetrievalHit(
                    chunk_id="chem-1",
                    asset_id="chem-asset",
                    content="红纸编号 试剂 红纸变化 ② 蒸馏水 ③ 饱和食盐水 ④ NaHCO3溶液(调至pH＝7)",
                    source_type="knowledge-base",
                    source_title="化学练习册第57页",
                )
            ],
            slide_plan=SlidePlan(
                title="工业革命",
                slides=[
                    SlidePlanItem(
                        slide_number=1,
                        title="材料与案例分析",
                        slide_type=SlideType.COMPARISON,
                        goal="结合资料进行分析和比较",
                        key_points=["31：参照模板中的内容输入文本"],
                        visual_brief=["参考资料提示：NaHCO3溶液(调至pH＝7)"],
                        speaker_notes=["只围绕已确认要点展开：红纸编号 试剂 红纸变化"],
                        citations=[Citation(asset_id="chem-asset", note="化学练习册第57页")],
                    )
                ],
            ),
        )
    )

    codes = {issue.code for issue in report.issues}
    assert "generic_learning_objective" in codes
    assert "retrieval_contamination" in codes
    assert "template_placeholder_leak" in codes
    assert "cross_subject_contamination" in codes


def test_regenerate_slide_stays_within_current_slide_citations() -> None:
    session = SessionState(
        title="regenerate-guard",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        ),
        retrieval_hits=[
            RetrievalHit(
                chunk_id="keep",
                asset_id="hist-keep",
                content="蒸汽机推动工厂制度形成，并带来城市化影响。",
                source_type="knowledge-base",
                source_title="教材第12页",
            ),
            RetrievalHit(
                chunk_id="drop",
                asset_id="hist-drop",
                content="拿破仑战争改变了欧洲政治格局。",
                source_type="knowledge-base",
                source_title="教材第3页",
            ),
        ],
        slide_plan=SlidePlan(
            title="工业革命",
            slides=[
                SlidePlanItem(
                    slide_number=1,
                    title="工业革命核心线索",
                    slide_type=SlideType.CONCEPT,
                    goal="说明蒸汽机与工厂制度的关系",
                    key_points=["蒸汽机推动工厂制度形成"],
                    speaker_notes=["围绕教材第12页讲解蒸汽机与工厂制度"],
                    citations=[Citation(asset_id="hist-keep", chunk_id="keep", note="教材第12页")],
                )
            ],
        ),
    )

    updated = regenerate_slide_in_session(session, 1, instructions="增加一句过渡说明")
    regenerated = updated.slide_plan.slides[0]

    assert any(citation.asset_id == "hist-keep" for citation in regenerated.citations)
    assert all(citation.asset_id != "hist-drop" for citation in regenerated.citations)
    assert any("蒸汽机" in point for point in regenerated.key_points)
    assert all("拿破仑战争" not in point for point in regenerated.key_points)
    assert any("仅基于当前页引用和既有要点重组" in note for note in regenerated.revision_notes)


def test_regenerate_slide_prefers_model_when_gateway_is_ready(monkeypatch) -> None:
    session = SessionState(
        title="regenerate-llm",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
            additional_requirements=["只使用上传资料和检索命中"],
        ),
        retrieval_hits=[
            RetrievalHit(
                chunk_id="keep",
                asset_id="hist-keep",
                content="蒸汽机推动工厂制度形成，并带来城市化影响。",
                source_type="knowledge-base",
                source_title="教材第12页",
                topic_hint="蒸汽机与工厂制度",
            ),
        ],
        slide_plan=SlidePlan(
            title="工业革命",
            slides=[
                SlidePlanItem(
                    slide_number=1,
                    title="工业革命核心线索",
                    slide_type=SlideType.CONCEPT,
                    goal="说明蒸汽机与工厂制度的关系",
                    key_points=["蒸汽机推动工厂制度形成"],
                    speaker_notes=["围绕教材第12页讲解蒸汽机与工厂制度"],
                    citations=[Citation(asset_id="hist-keep", chunk_id="keep", note="教材第12页")],
                )
            ],
        ),
    )

    monkeypatch.setattr("app.services.planner.openai_slide_regenerator_ready", lambda settings: True)
    monkeypatch.setattr(
        "app.services.planner.generate_slide_regeneration_draft_with_openai",
        lambda *args, **kwargs: SlideRegenerationDraft(
            title="工业革命的关键驱动",
            goal="更清楚地说明蒸汽机与工厂制度的因果关系",
            slide_type="activity",
            key_points=["根据教材证据概括蒸汽机带来的生产变化", "讨论工厂制度为何改变劳动组织"],
            visual_brief=["左侧证据卡片，右侧讨论任务区"],
            speaker_notes=["先回顾教材证据，再组织学生讨论工厂制度变化。"],
            interaction_mode="discussion",
            layout_hint="双栏证据+讨论布局",
            revision_notes=["保留教材证据，不扩展课外史实"],
        ),
    )

    updated = regenerate_slide_in_session(session, 1, instructions="改成讨论页")
    regenerated = updated.slide_plan.slides[0]

    assert regenerated.title == "工业革命的关键驱动"
    assert regenerated.slide_type == SlideType.ACTIVITY
    assert regenerated.interaction_mode == InteractionMode.DISCUSSION
    assert any(citation.asset_id == "hist-keep" for citation in regenerated.citations)
    assert any("讨论工厂制度" in point for point in regenerated.key_points)
    assert any("模型单页再生成" in note for note in regenerated.revision_notes)


def test_generate_slide_plan_polishes_speaker_notes_when_gateway_is_ready(monkeypatch) -> None:
    spec = TeachingSpec(
        education_stage="middle-school",
        subject="history",
        lesson_title="工业革命",
        learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
    )
    outline = LessonOutline(
        title="工业革命 lesson outline",
        sections=[
            LessonOutlineSection(
                title="核心概念",
                goal="说明蒸汽机与工厂制度的关系",
                bullet_points=["蒸汽机推动工厂制度形成", "工业革命改变生产组织"],
                estimated_slides=1,
                recommended_slide_type=SlideType.CONCEPT,
            )
        ],
    )
    hits = [
        RetrievalHit(
            chunk_id="hist-1",
            asset_id="hist-1",
            content="蒸汽机推动工厂制度形成，并改变劳动组织方式。",
            source_type="knowledge-base",
            source_title="历史教材",
        )
    ]

    monkeypatch.setattr("app.services.planner.openai_slide_planner_ready", lambda settings: False)
    monkeypatch.setattr("app.services.planner.openai_speaker_notes_ready", lambda settings: True)
    monkeypatch.setattr(
        "app.services.planner.polish_speaker_notes_with_openai",
        lambda *args, **kwargs: SpeakerNotesDeckDraft(
            slides=[
                SpeakerNotesSlideDraft(
                    slide_number=1,
                    speaker_notes=["先结合教材证据说明蒸汽机如何推动工厂制度形成，再引导学生概括生产组织变化。"],
                )
            ]
        ),
    )

    slide_plan = generate_slide_plan(spec, outline, hits, allow_llm=True)

    assert slide_plan.slides[0].speaker_notes[0].startswith("先结合教材证据说明蒸汽机")
    assert any("模型润色讲稿" in note for note in slide_plan.slides[0].revision_notes)


def test_regenerate_slide_polishes_speaker_notes_when_gateway_is_ready(monkeypatch) -> None:
    session = SessionState(
        title="regenerate-notes",
        teaching_spec=TeachingSpec(
            education_stage="middle-school",
            subject="history",
            lesson_title="工业革命",
            learning_objectives=[{"description": "理解蒸汽机与工厂制度的关系"}],
        ),
        retrieval_hits=[
            RetrievalHit(
                chunk_id="keep",
                asset_id="hist-keep",
                content="蒸汽机推动工厂制度形成，并带来城市化影响。",
                source_type="knowledge-base",
                source_title="教材第12页",
            ),
        ],
        slide_plan=SlidePlan(
            title="工业革命",
            slides=[
                SlidePlanItem(
                    slide_number=1,
                    title="工业革命核心线索",
                    slide_type=SlideType.CONCEPT,
                    goal="说明蒸汽机与工厂制度的关系",
                    key_points=["蒸汽机推动工厂制度形成"],
                    speaker_notes=["围绕教材第12页讲解蒸汽机与工厂制度。"],
                    citations=[Citation(asset_id="hist-keep", chunk_id="keep", note="教材第12页")],
                )
            ],
        ),
    )

    monkeypatch.setattr("app.services.planner.openai_slide_regenerator_ready", lambda settings: True)
    monkeypatch.setattr(
        "app.services.planner.generate_slide_regeneration_draft_with_openai",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("force fallback")),
    )
    monkeypatch.setattr("app.services.planner.openai_speaker_notes_ready", lambda settings: True)
    monkeypatch.setattr(
        "app.services.planner.polish_speaker_notes_with_openai",
        lambda *args, **kwargs: SpeakerNotesDeckDraft(
            slides=[
                SpeakerNotesSlideDraft(
                    slide_number=1,
                    speaker_notes=["先展示教材第12页证据，再引导学生概括蒸汽机如何改变工厂制度。"],
                )
            ]
        ),
    )

    updated = regenerate_slide_in_session(session, 1, instructions="增加一句过渡说明")
    regenerated = updated.slide_plan.slides[0]

    assert regenerated.speaker_notes[0].startswith("先展示教材第12页证据")
    assert any("模型润色讲稿" in note for note in regenerated.revision_notes)


def test_planner_outline_endpoint_uses_kb_hits() -> None:
    settings = get_settings()
    source_dir = _make_kb_dir()
    namespace = f"planner_api_{uuid4().hex}"

    try:
        (source_dir / "english.txt").write_text(
            "Environment Protection lessons can include vocabulary, discussion prompts, and project tasks.",
            encoding="utf-8",
        )

        ingest_response = client.post(
            "/api/kb/ingest",
            json={
                "source_dir": str(source_dir),
                "reset": True,
                "store_namespace": namespace,
            },
        )
        assert ingest_response.status_code == 200

        chat_response = client.post(
            "/api/chat/messages",
            json={
                "title": "English Demo",
                "content": '我想做一节高中英语"Environment Protection"课程，40分钟，加入讨论和项目任务。',
            },
        )
        assert chat_response.status_code == 200
        session_id = chat_response.json()["session_id"]

        outline_response = client.post(
            "/api/planner/outline",
            json={
                "session_id": session_id,
                "store_namespace": namespace,
                "top_k": 3,
            },
        )
        assert outline_response.status_code == 200
        payload = outline_response.json()
        assert payload["outline"]["sections"]
        assert payload["retrieval_hits"]
        assert payload["session"]["outline"]["title"].startswith("Environment Protection")
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_planner_slide_plan_endpoint_generates_plan() -> None:
    settings = get_settings()
    source_dir = _make_kb_dir()
    namespace = f"planner_slide_{uuid4().hex}"

    try:
        (source_dir / "history.txt").write_text(
            "Industrial Revolution lessons benefit from timeline evidence, source analysis, and discussion questions about social change.",
            encoding="utf-8",
        )

        ingest_response = client.post(
            "/api/kb/ingest",
            json={
                "source_dir": str(source_dir),
                "reset": True,
                "store_namespace": namespace,
            },
        )
        assert ingest_response.status_code == 200

        chat_response = client.post(
            "/api/chat/messages",
            json={
                "title": "History Demo",
                "content": "我想做一节初中历史《工业革命》课程，45分钟，加入材料分析和讨论。",
            },
        )
        assert chat_response.status_code == 200
        session_id = chat_response.json()["session_id"]

        slide_plan_response = client.post(
            "/api/planner/slide-plan",
            json={
                "session_id": session_id,
                "store_namespace": namespace,
                "top_k": 3,
            },
        )
        assert slide_plan_response.status_code == 200
        payload = slide_plan_response.json()
        assert payload["outline"]["sections"]
        assert payload["slide_plan"]["slides"]
        assert payload["slide_plan"]["total_slides"] == len(payload["slide_plan"]["slides"])
        assert payload["session"]["slide_plan"]["title"].startswith("工业革命")
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_uploaded_session_file_influences_outline_generation() -> None:
    session_response = client.post("/api/chat/sessions", json={"title": "Uploaded Context Demo"})
    session_id = session_response.json()["session_id"]

    try:
        upload_response = client.post(
            "/api/files/upload",
            files={
                "file": (
                    "history_notes.txt",
                    "工业革命的材料分析可以围绕蒸汽机、工厂制度、城市化影响和工人处境展开。",
                    "text/plain",
                )
            },
            data={"session_id": session_id},
        )
        assert upload_response.status_code == 200

        chat_response = client.post(
            "/api/chat/messages",
            json={
                "session_id": session_id,
                "content": "我想做一节初中历史《工业革命》课程，45分钟，加入材料分析和讨论。",
            },
        )
        assert chat_response.status_code == 200

        outline_response = client.post(
            "/api/planner/outline",
            json={
                "session_id": session_id,
                "top_k": 5,
            },
        )
        assert outline_response.status_code == 200
        payload = outline_response.json()
        assert any(hit["page_label"] == "history_notes.txt" for hit in payload["retrieval_hits"])
        assert any(
            "蒸汽机" in point or "工厂制度" in point
            for section in payload["outline"]["sections"]
            for point in section["bullet_points"]
        )
    finally:
        _cleanup_session_artifacts(session_id)


def test_slide_plan_edit_endpoints_support_card_style_workflow() -> None:
    chat_response = client.post(
        "/api/chat/messages",
        json={
            "title": "Editable Demo",
            "content": "请帮我准备一节初中数学《一次函数》复习课，50分钟，增加练习和小测。",
        },
    )
    assert chat_response.status_code == 200
    session_id = chat_response.json()["session_id"]

    preview_response = client.post(
        "/api/preview/deck",
        json={
            "session_id": session_id,
            "top_k": 5,
        },
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["session"]["preview_deck"] is not None

    update_response = client.post(
        "/api/planner/slide-plan/update",
        json={
            "session_id": session_id,
            "slide_number": 2,
            "title": "一次函数概念回顾",
            "goal": "回顾图像、k 值和 b 值的含义",
            "key_points": ["图像是一条直线", "k 决定倾斜方向", "b 决定与 y 轴交点"],
            "revision_note": "手动强化基础概念",
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["slide_plan"]["slides"][1]["title"] == "一次函数概念回顾"
    assert updated_payload["session"]["preview_deck"] is None

    move_response = client.post(
        "/api/planner/slide-plan/move",
        json={
            "session_id": session_id,
            "from_slide_number": 1,
            "to_position": 3,
        },
    )
    assert move_response.status_code == 200
    moved_payload = move_response.json()
    assert moved_payload["slide_plan"]["slides"][2]["slide_type"] == "cover"

    insert_response = client.post(
        "/api/planner/slide-plan/insert",
        json={
            "session_id": session_id,
            "position": 2,
            "title": "错题易错点整理",
            "goal": "用典型错题强化一次函数复习",
            "slide_type": "comparison",
            "key_points": ["对比常见错误", "说明原因", "给出改正策略"],
            "revision_note": "插入错题整理页",
        },
    )
    assert insert_response.status_code == 200
    inserted_payload = insert_response.json()
    assert inserted_payload["slide_plan"]["slides"][1]["title"] == "错题易错点整理"

    regenerate_response = client.post(
        "/api/planner/slide-plan/regenerate-slide",
        json={
            "session_id": session_id,
            "slide_number": 2,
            "instructions": "强调错题归因和变式练习",
        },
    )
    assert regenerate_response.status_code == 200
    regenerated_payload = regenerate_response.json()
    regenerated_slide = regenerated_payload["slide_plan"]["slides"][1]
    assert any("强调错题归因和变式练习" in note for note in regenerated_slide["revision_notes"])

    delete_response = client.post(
        "/api/planner/slide-plan/delete",
        json={
            "session_id": session_id,
            "slide_number": 2,
        },
    )
    assert delete_response.status_code == 200
    deleted_payload = delete_response.json()
    slide_numbers = [slide["slide_number"] for slide in deleted_payload["slide_plan"]["slides"]]
    assert slide_numbers == list(range(1, len(slide_numbers) + 1))
    assert all(slide["title"] != "错题易错点整理" for slide in deleted_payload["slide_plan"]["slides"])
