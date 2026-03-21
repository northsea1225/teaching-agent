from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import Citation, InteractionMode, RetrievalHit, SlidePlan, SlidePlanItem, SlideType, TeachingSpec
from app.services.planner import generate_lesson_outline, generate_slide_plan
from app.services.svg import generate_svg_deck


client = TestClient(app)


def _make_kb_dir() -> Path:
    settings = get_settings()
    path = settings.knowledge_base_dir / f"_svg_tests_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_generate_svg_deck_builds_markup() -> None:
    spec = TeachingSpec(
        education_stage="high-school",
        subject="english",
        lesson_title="Environment Protection",
        class_duration_minutes=40,
        interaction_preferences=[InteractionMode.DISCUSSION],
        style_preferences=["简洁", "可视化"],
    )
    hits = [
        RetrievalHit(
            chunk_id="svg-1",
            asset_id="english-svg-asset",
            content="Environment Protection lessons can include vocabulary scaffolds, discussion prompts, and project tasks.",
            page_label="p1",
        )
    ]
    outline = generate_lesson_outline(spec, hits)
    slide_plan = generate_slide_plan(spec, outline, hits)
    svg_deck = generate_svg_deck(slide_plan, theme_id="studio", font_preset="modern")

    assert svg_deck.slides
    assert svg_deck.theme_id == "studio"
    assert svg_deck.font_preset == "modern"
    assert svg_deck.title_font_family == "Bahnschrift"
    assert svg_deck.body_font_family == "Segoe UI"
    assert svg_deck.slides[0].markup.startswith("<svg")
    assert svg_deck.slides[0].layout_name == "cover-hero"
    assert svg_deck.slides[1].layout_name in {"split-grid", "comparison-columns", "timeline-ribbon"}
    assert svg_deck.slides[1].blocks[0].shape_variant == "hero-bar"
    assert svg_deck.slides[1].blocks[1].background_fill
    assert svg_deck.slides[0].title_font_family == "Bahnschrift"
    assert svg_deck.slides[0].body_font_family == "Segoe UI"
    assert "<defs>" in svg_deck.slides[0].markup
    assert "Knowledge Core" in svg_deck.slides[1].markup
    assert "Bahnschrift" in svg_deck.slides[0].markup


def test_generate_svg_deck_uses_specialized_high_fidelity_layouts() -> None:
    slide_plan = SlidePlan(
        title="layout coverage",
        theme_hint="可视化 工作坊",
        slides=[
            SlidePlanItem(
                slide_number=1,
                slide_type=SlideType.PROCESS,
                title="解题流程",
                goal="按步骤展示解决问题的方法链",
                key_points=["识别条件", "建立关系", "求解并检验"],
                visual_brief=["用阶梯式步骤卡呈现流程", "突出每一步判断点"],
            ),
            SlidePlanItem(
                slide_number=2,
                slide_type=SlideType.MEDIA,
                title="材料解读",
                goal="结合图像和资料摘录完成观察与分析",
                key_points=["先观察", "再提取证据", "最后形成结论"],
                visual_brief=["左侧保留大图像区", "右侧展示分析镜头"],
            ),
            SlidePlanItem(
                slide_number=3,
                slide_type=SlideType.ACTIVITY,
                title="分组任务",
                goal="组织学生分组完成课堂任务",
                key_points=["任务说明", "小组协作", "汇报展示"],
                visual_brief=["中间展示流程", "右侧展示教师提示"],
                interaction_mode=InteractionMode.DISCUSSION,
            ),
            SlidePlanItem(
                slide_number=4,
                slide_type=SlideType.ASSIGNMENT,
                title="课后任务",
                goal="布置迁移练习与成果提交要求",
                key_points=["完成练习", "提交作品", "自查标准"],
                visual_brief=["清单式展示提交物", "评价标准独立成块"],
            ),
            SlidePlanItem(
                slide_number=5,
                slide_type=SlideType.TIMELINE,
                title="发展脉络",
                goal="按时间顺序呈现关键阶段和转折点",
                key_points=["起点", "发展", "转折", "影响"],
                visual_brief=["曲线时间带连接三段内容", "底部保留证据说明"],
            ),
        ],
    )

    svg_deck = generate_svg_deck(slide_plan, theme_id="field", font_preset="classroom")
    layout_names = [slide.layout_name for slide in svg_deck.slides]

    assert layout_names == [
        "process-ladder",
        "media-gallery",
        "workshop-board",
        "assignment-brief",
        "timeline-ribbon",
    ]
    assert "Method Frame" in svg_deck.slides[0].markup
    assert "Visual Stage" in svg_deck.slides[1].markup
    assert "Studio Task" in svg_deck.slides[2].markup
    assert "After Class" in svg_deck.slides[3].markup
    assert "Timeline Lens" in svg_deck.slides[4].markup


def test_svg_deck_endpoint_generates_svg_specs() -> None:
    settings = get_settings()
    source_dir = _make_kb_dir()
    namespace = f"svg_api_{uuid4().hex}"

    try:
        (source_dir / "history.txt").write_text(
            "Industrial Revolution lessons benefit from timeline evidence, source analysis, and discussion prompts.",
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
                "title": "SVG Demo",
                "content": "我想做一节初中历史《工业革命》课程，45分钟，加入材料分析和讨论。",
            },
        )
        assert chat_response.status_code == 200
        session_id = chat_response.json()["session_id"]

        svg_response = client.post(
            "/api/svg/deck",
            json={
                "session_id": session_id,
                "store_namespace": namespace,
                "top_k": 3,
                "theme_id": "briefing",
                "font_preset": "reading",
            },
        )
        assert svg_response.status_code == 200
        payload = svg_response.json()
        assert payload["slide_plan"]["slides"]
        assert payload["svg_deck"]["slides"]
        assert payload["svg_deck"]["slides"][0]["markup"].startswith("<svg")
        assert payload["svg_deck"]["slides"][0]["layout_name"] == "cover-hero"
        assert payload["svg_deck"]["slides"][0]["style_preset"]
        assert payload["svg_deck"]["theme_id"] == "briefing"
        assert payload["svg_deck"]["font_preset"] == "reading"
        assert payload["svg_deck"]["slides"][0]["title_font_family"] == "Georgia"
        assert payload["svg_deck"]["slides"][0]["body_font_family"] == "Microsoft YaHei"
        assert payload["session"]["svg_theme_id"] == "briefing"
        assert payload["session"]["svg_font_preset"] == "reading"
        assert payload["session"]["svg_deck"]["title"].endswith("svg deck")
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(settings.vector_store_dir / namespace, ignore_errors=True)


def test_generate_svg_deck_renders_theme_bound_citation_tags() -> None:
    slide_plan = SlidePlan(
        title="citation preview",
        slides=[
            SlidePlanItem(
                slide_number=1,
                slide_type=SlideType.COVER,
                title="Environment Protection",
                goal="建立环境议题的课堂入口",
                key_points=["topic framing", "visual prompt"],
                citations=[
                    Citation(asset_id="eng-1", note="Workbook p.14"),
                    Citation(asset_id="eng-2", note="Photo Set A"),
                    Citation(asset_id="eng-3", note="Discussion Card"),
                ],
            )
        ],
    )

    studio_deck = generate_svg_deck(slide_plan, theme_id="studio", font_preset="modern")
    briefing_deck = generate_svg_deck(slide_plan, theme_id="briefing", font_preset="modern")

    studio_markup = studio_deck.slides[0].markup
    briefing_markup = briefing_deck.slides[0].markup

    assert "References" in studio_markup
    assert "Workbook p.14" in studio_markup
    assert "+1 more" in studio_markup
    assert "#8a2c0d" in studio_markup.lower()
    assert "#fde6d8" in studio_markup.lower()
    assert "#0f172a" in briefing_markup.lower()
    assert "#e2e8f0" in briefing_markup.lower()
