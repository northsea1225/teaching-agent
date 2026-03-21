from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.models import PreviewDeck, PreviewSlide, SessionStage, SessionState, SlidePlan, SlidePlanItem
from app.services.planner import generate_slide_plan_for_session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _list_items(items: list[str], css_class: str) -> str:
    if not items:
        return ""
    rendered = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f'<ul class="{css_class}">{rendered}</ul>'


def _render_slide_html(slide: SlidePlanItem, theme_hint: str | None = None) -> str:
    citations = [
        citation.note or citation.page_label or citation.asset_id
        for citation in slide.citations
    ]
    header_badge = escape(slide.slide_type.value.upper())
    theme = escape(theme_hint or "teaching-preview")
    title = escape(slide.title)
    goal = escape(slide.goal)
    layout_hint = escape(slide.layout_hint or "卡片式布局")
    interaction = escape(slide.interaction_mode.value)

    sections = [
        '<section class="panel hero">',
        f'<div class="badge">{header_badge}</div>',
        f"<h2>{title}</h2>",
        f"<p class=\"goal\">{goal}</p>",
        f"<p class=\"meta\">布局建议：{layout_hint} | 互动方式：{interaction}</p>",
        "</section>",
    ]

    if slide.key_points:
        sections.append(
            '<section class="panel"><h3>Key Points</h3>'
            + _list_items(slide.key_points, "bullet-list")
            + "</section>"
        )
    if slide.visual_brief:
        sections.append(
            '<section class="panel"><h3>Visual Brief</h3>'
            + _list_items(slide.visual_brief, "bullet-list")
            + "</section>"
        )
    if slide.speaker_notes:
        sections.append(
            '<section class="panel"><h3>Speaker Notes</h3>'
            + _list_items(slide.speaker_notes, "bullet-list notes")
            + "</section>"
        )
    if citations:
        sections.append(
            '<section class="panel"><h3>References</h3>'
            + _list_items(citations, "bullet-list refs")
            + "</section>"
        )

    body = "".join(sections)
    return (
        f'<article class="slide-card" data-theme="{theme}" data-slide="{slide.slide_number}">'
        f'<div class="slide-index">Slide {slide.slide_number}</div>'
        f"{body}"
        "</article>"
    )


def _render_document(deck: PreviewDeck) -> str:
    style = """
    <style>
      body { font-family: "Segoe UI", "PingFang SC", sans-serif; margin: 0; background: #eef3f7; color: #17202a; }
      .deck { max-width: 1200px; margin: 0 auto; padding: 32px 20px 48px; }
      .deck-header { margin-bottom: 24px; }
      .deck-header h1 { margin: 0 0 8px; font-size: 28px; }
      .deck-header p { margin: 0; color: #51606f; }
      .slide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }
      .slide-card { background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%); border: 1px solid #d8e4ef; border-radius: 20px; padding: 18px; box-shadow: 0 14px 36px rgba(31, 62, 93, 0.08); }
      .slide-index { font-size: 12px; color: #627487; margin-bottom: 10px; letter-spacing: 0.08em; text-transform: uppercase; }
      .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #16324f; color: #ffffff; font-size: 12px; margin-bottom: 10px; }
      .hero h2 { margin: 0 0 10px; font-size: 24px; line-height: 1.2; }
      .goal { margin: 0 0 8px; font-size: 15px; color: #213446; }
      .meta { margin: 0; font-size: 12px; color: #5b6d7f; }
      .panel { background: #f5f9fc; border-radius: 14px; padding: 14px; margin-top: 14px; }
      .panel h3 { margin: 0 0 10px; font-size: 14px; color: #16324f; }
      .bullet-list { margin: 0; padding-left: 18px; }
      .bullet-list li { margin-bottom: 8px; line-height: 1.5; }
    </style>
    """
    slide_cards = "".join(slide.html for slide in deck.slides)
    header = (
        '<div class="deck-header">'
        f"<h1>{escape(deck.title)}</h1>"
        f"<p>{escape(deck.theme_hint or 'Low-fidelity preview')}</p>"
        "</div>"
    )
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"{style}</head><body><main class=\"deck\">{header}<section class=\"slide-grid\">"
        f"{slide_cards}</section></main></body></html>"
    )


def generate_preview_deck(slide_plan: SlidePlan) -> PreviewDeck:
    slides: list[PreviewSlide] = []
    for slide in slide_plan.slides:
        rendered_html = _render_slide_html(slide, slide_plan.theme_hint)
        text_blocks = slide.key_points + slide.visual_brief + slide.speaker_notes
        slides.append(
            PreviewSlide(
                slide_number=slide.slide_number,
                slide_type=slide.slide_type,
                title=slide.title,
                html=rendered_html,
                text_blocks=text_blocks[:8],
            )
        )

    deck = PreviewDeck(
        title=f"{slide_plan.title} preview",
        theme_hint=slide_plan.theme_hint,
        slides=slides,
    )
    deck.html_document = _render_document(deck)
    return deck


def generate_preview_for_session(
    session: SessionState,
    store_namespace: str | None = None,
    top_k: int = 5,
) -> SessionState:
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(
            session,
            store_namespace=store_namespace,
            top_k=top_k,
        )

    assert session.slide_plan is not None
    preview_deck = generate_preview_deck(session.slide_plan)
    session.preview_deck = preview_deck
    session.stage = SessionStage.PREVIEW
    session.last_summary = f"已生成 {len(preview_deck.slides)} 页低保真预览，可继续进入导出阶段。"
    session.updated_at = utc_now()
    return session
