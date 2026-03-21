from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.models import (
    Citation,
    SessionStage,
    SessionState,
    SlidePlan,
    SlidePlanItem,
    SlideType,
    SvgBlockSpec,
    SvgDeckSpec,
    SvgSlideSpec,
)
from app.services.planner import generate_slide_plan_for_session
from app.services.svg_finalize import finalize_svg_deck
from app.services.template_registry import select_template_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_lines(items: list[str], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if not normalized or normalized in lines:
            continue
        lines.append(normalized[:100])
        if len(lines) >= limit:
            break
    return lines


THEME_PRESETS: dict[str, dict[str, object]] = {
    "academy": {
        "default": {
            "background": "#f7fbff",
            "accent": "#16324f",
            "soft": "#d7e6f5",
            "text": "#17202a",
        },
        "by_type": {
            SlideType.CONCEPT: {"accent": "#164e63", "soft": "#d4eef4", "text": "#183445"},
            SlideType.PROCESS: {"background": "#f7fcfb", "accent": "#0f766e", "soft": "#d3f0eb", "text": "#17313a"},
            SlideType.TIMELINE: {"background": "#f8fcff", "accent": "#0369a1", "soft": "#d9eefb", "text": "#163447"},
            SlideType.COMPARISON: {"background": "#fffaf4", "accent": "#9a3412", "soft": "#fde6d8", "text": "#3a2416"},
            SlideType.MEDIA: {"background": "#fff9fb", "accent": "#9d174d", "soft": "#f9dbe7", "text": "#3b1f2c"},
            SlideType.ACTIVITY: {"background": "#fffdf5", "accent": "#a16207", "soft": "#fce8ba", "text": "#3e2d14"},
            SlideType.ASSIGNMENT: {"background": "#fefce8", "accent": "#854d0e", "soft": "#f7efbf", "text": "#3a2a14"},
            SlideType.SUMMARY: {"background": "#f8fafc", "accent": "#334155", "soft": "#dce3ea", "text": "#1e293b"},
        },
        "atlas_soft": "#e4f2fb",
        "workshop_background": "#fffef8",
    },
    "studio": {
        "default": {
            "background": "#fff8f3",
            "accent": "#8a2c0d",
            "soft": "#fde6d8",
            "text": "#342117",
        },
        "by_type": {
            SlideType.CONCEPT: {"accent": "#9a3412", "soft": "#fdd9c7"},
            SlideType.PROCESS: {"background": "#fff9f6", "accent": "#c2410c", "soft": "#ffe1d1"},
            SlideType.TIMELINE: {"background": "#fff7fb", "accent": "#be185d", "soft": "#f9d7e8", "text": "#411a2c"},
            SlideType.COMPARISON: {"background": "#fffaf6", "accent": "#b45309", "soft": "#fbe4c8"},
            SlideType.MEDIA: {"background": "#fff6fa", "accent": "#db2777", "soft": "#fbd8ea", "text": "#4a2035"},
            SlideType.ACTIVITY: {"background": "#fffbf3", "accent": "#ca8a04", "soft": "#fceab9"},
            SlideType.ASSIGNMENT: {"background": "#fffdf6", "accent": "#a16207", "soft": "#f8ebb7"},
            SlideType.SUMMARY: {"background": "#fcfaf8", "accent": "#7c2d12", "soft": "#f4dfd0"},
        },
        "atlas_soft": "#ffe4d6",
        "workshop_background": "#fffaf4",
    },
    "field": {
        "default": {
            "background": "#f7fcf9",
            "accent": "#166534",
            "soft": "#d7f0df",
            "text": "#1d3228",
        },
        "by_type": {
            SlideType.CONCEPT: {"accent": "#0f766e", "soft": "#d7f3ed"},
            SlideType.PROCESS: {"background": "#f6fcfa", "accent": "#15803d", "soft": "#d9f2de"},
            SlideType.TIMELINE: {"background": "#f5fbff", "accent": "#0f766e", "soft": "#d8f0f1"},
            SlideType.COMPARISON: {"background": "#fbfaf4", "accent": "#a16207", "soft": "#f3e8c6", "text": "#3b2e17"},
            SlideType.MEDIA: {"background": "#f8fcfa", "accent": "#047857", "soft": "#d8f3e8"},
            SlideType.ACTIVITY: {"background": "#fbfff8", "accent": "#65a30d", "soft": "#e7f4c8"},
            SlideType.ASSIGNMENT: {"background": "#fbfff7", "accent": "#4d7c0f", "soft": "#e5f2c4"},
            SlideType.SUMMARY: {"background": "#f8fbf8", "accent": "#365314", "soft": "#dde9d0"},
        },
        "atlas_soft": "#e3f6eb",
        "workshop_background": "#fbfff8",
    },
    "briefing": {
        "default": {
            "background": "#f8fafc",
            "accent": "#0f172a",
            "soft": "#e2e8f0",
            "text": "#172033",
        },
        "by_type": {
            SlideType.CONCEPT: {"accent": "#1d4ed8", "soft": "#dbe7fb"},
            SlideType.PROCESS: {"background": "#f7fafc", "accent": "#0f766e", "soft": "#d7eeea"},
            SlideType.TIMELINE: {"background": "#f6fbff", "accent": "#0369a1", "soft": "#d9ecf8"},
            SlideType.COMPARISON: {"background": "#faf8f5", "accent": "#92400e", "soft": "#eee1cf", "text": "#33261b"},
            SlideType.MEDIA: {"background": "#f9f7fd", "accent": "#7c3aed", "soft": "#e7def9", "text": "#2c2142"},
            SlideType.ACTIVITY: {"background": "#fbfbf7", "accent": "#b45309", "soft": "#f1e5cb"},
            SlideType.ASSIGNMENT: {"background": "#fbfbf5", "accent": "#854d0e", "soft": "#ece0c4"},
            SlideType.SUMMARY: {"background": "#f8fafc", "accent": "#334155", "soft": "#dde5ee"},
        },
        "atlas_soft": "#dbe7f5",
        "workshop_background": "#fbfcfe",
    },
}

FONT_PRESETS: dict[str, dict[str, str]] = {
    "classroom": {"title": "Microsoft YaHei UI", "body": "Microsoft YaHei"},
    "reading": {"title": "Georgia", "body": "Microsoft YaHei"},
    "modern": {"title": "Bahnschrift", "body": "Segoe UI"},
}


SVG_CITATION_THEME_STYLES: dict[str, dict[str, str | float]] = {
    "academy": {
        "heading_fill": "#16324f",
        "heading_text": "#ffffff",
        "heading_fill_transparency": 0.04,
        "chip_fill": "#d7e6f5",
        "chip_text": "#16324f",
        "chip_line": "#16324f",
        "chip_fill_transparency": 0.18,
        "chip_line_transparency": 0.48,
    },
    "studio": {
        "heading_fill": "#8a2c0d",
        "heading_text": "#fffaf7",
        "heading_fill_transparency": 0.02,
        "chip_fill": "#fde6d8",
        "chip_text": "#6b240c",
        "chip_line": "#8a2c0d",
        "chip_fill_transparency": 0.08,
        "chip_line_transparency": 0.2,
    },
    "field": {
        "heading_fill": "#166534",
        "heading_text": "#f8fff9",
        "heading_fill_transparency": 0.03,
        "chip_fill": "#d7f0df",
        "chip_text": "#1c4b32",
        "chip_line": "#166534",
        "chip_fill_transparency": 0.1,
        "chip_line_transparency": 0.24,
    },
    "briefing": {
        "heading_fill": "#0f172a",
        "heading_text": "#f8fafc",
        "heading_fill_transparency": 0.0,
        "chip_fill": "#e2e8f0",
        "chip_text": "#172033",
        "chip_line": "#334155",
        "chip_fill_transparency": 0.14,
        "chip_line_transparency": 0.34,
    },
}


def _resolve_theme_id(requested_theme_id: str | None, theme_hint: str | None) -> str:
    if requested_theme_id in THEME_PRESETS:
        return requested_theme_id

    hint = (theme_hint or "").lower()
    if any(keyword in hint for keyword in ("创意", "设计", "海报", "品牌")):
        return "studio"
    if any(keyword in hint for keyword in ("实践", "探究", "项目", "工作坊")):
        return "field"
    if any(keyword in hint for keyword in ("复习", "总结", "汇报", "简报")):
        return "briefing"
    return "academy"


def _resolve_font_preset(requested_font_preset: str | None) -> str:
    if requested_font_preset in FONT_PRESETS:
        return requested_font_preset
    return "classroom"


def _style_preset(theme_hint: str | None, slide_type: SlideType, theme_id: str) -> str:
    if theme_id == "briefing":
        return "clean-grid" if slide_type in {SlideType.COVER, SlideType.SUMMARY, SlideType.AGENDA} else "editorial"
    if theme_id == "studio":
        if slide_type in {SlideType.COVER, SlideType.MEDIA, SlideType.COMPARISON}:
            return "atlas"
    if theme_id == "field" and slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT, SlideType.PROCESS}:
        return "workshop"

    theme = (theme_hint or "").lower()
    if "可视化" in theme or slide_type in {SlideType.MEDIA, SlideType.TIMELINE}:
        return "atlas"
    if "简洁" in theme or slide_type in {SlideType.COVER, SlideType.SUMMARY}:
        return "clean-grid"
    if slide_type in {SlideType.ACTIVITY, SlideType.ASSIGNMENT}:
        return "workshop"
    return "editorial"


def _palette(theme_id: str, slide_type: SlideType, style_preset: str) -> dict[str, str]:
    theme = THEME_PRESETS.get(theme_id, THEME_PRESETS["academy"])
    palette = dict(theme["default"])
    palette.update(theme["by_type"].get(slide_type, {}))
    if style_preset == "atlas":
        palette["soft"] = str(theme["atlas_soft"])
    elif style_preset == "workshop":
        palette["background"] = str(theme["workshop_background"])
    return palette


def _font_stack(font_family: str) -> str:
    return f'{font_family}, "PingFang SC", "Microsoft YaHei", sans-serif'


def _block(
    *,
    role: str,
    title: str | None,
    text_lines: list[str],
    x: int,
    y: int,
    width: int,
    height: int,
    accent_color: str,
    background_fill: str,
    text_color: str,
    stroke_color: str | None = None,
    title_size: int = 22,
    body_size: int = 18,
    corner_radius: int = 28,
    shape_variant: str = "card",
) -> SvgBlockSpec:
    return SvgBlockSpec(
        role=role,
        title=title,
        text_lines=text_lines,
        x=x,
        y=y,
        width=width,
        height=height,
        accent_color=accent_color,
        background_fill=background_fill,
        stroke_color=stroke_color or accent_color,
        text_color=text_color,
        title_size=title_size,
        body_size=body_size,
        corner_radius=corner_radius,
        shape_variant=shape_variant,
    )


def _citation_lines(slide: SlidePlanItem, fallback: str, limit: int = 4) -> list[str]:
    return _trim_lines(
        [citation.note or citation.page_label or citation.asset_id for citation in slide.citations]
        or [fallback],
        limit=limit,
    )


def _citation_label(citation: Citation) -> str:
    label = citation.note or citation.page_label or citation.asset_id or "Reference"
    normalized = " ".join(label.split()).strip()
    return normalized[:48]


def _citation_layout_profile(slide_spec: SvgSlideSpec) -> dict[str, int]:
    profile: dict[str, int] = {
        "heading_x": slide_spec.width - 320,
        "heading_y": 88,
        "heading_width": 120,
        "heading_height": 24,
        "chip_width": 250,
        "chip_height": 30,
        "chip_gap": 8,
        "max_visible": 3,
    }

    if slide_spec.layout_name == "cover-hero":
        profile.update(
            {
                "heading_x": slide_spec.width - 326,
                "heading_width": 136,
                "chip_width": 262,
                "chip_height": 32,
                "chip_gap": 10,
                "max_visible": 2,
            }
        )
    elif slide_spec.layout_name == "comparison-columns":
        profile.update(
            {
                "heading_x": slide_spec.width - 310,
                "heading_y": 104,
                "heading_width": 126,
                "chip_width": 236,
                "chip_height": 28,
                "max_visible": 2,
            }
        )
    elif slide_spec.layout_name == "timeline-ribbon":
        profile.update(
            {
                "heading_x": slide_spec.width - 296,
                "heading_y": 74,
                "heading_width": 118,
                "chip_width": 220,
                "chip_height": 26,
                "chip_gap": 6,
                "max_visible": 2,
            }
        )
    elif slide_spec.layout_name == "process-ladder":
        profile.update(
            {
                "heading_x": slide_spec.width - 308,
                "heading_y": 162,
                "chip_width": 232,
                "max_visible": 2,
            }
        )
    elif slide_spec.layout_name in {"media-gallery", "workshop-board"}:
        profile.update(
            {
                "heading_x": slide_spec.width - 316,
                "heading_y": 96,
                "chip_width": 244,
                "max_visible": 2,
            }
        )
    elif slide_spec.layout_name == "assignment-brief":
        profile.update(
            {
                "heading_x": slide_spec.width - 314,
                "heading_y": 86,
                "chip_width": 238,
            }
        )
    elif slide_spec.layout_name == "recap-strip":
        profile.update(
            {
                "heading_x": slide_spec.width - 316,
                "heading_y": 82,
                "chip_width": 242,
                "max_visible": 2,
            }
        )

    return profile


def _citation_theme_style(theme_id: str | None, slide_spec: SvgSlideSpec) -> dict[str, str | float]:
    style = dict(SVG_CITATION_THEME_STYLES.get(theme_id or "academy", SVG_CITATION_THEME_STYLES["academy"]))
    style.setdefault("heading_fill", slide_spec.accent_color)
    style.setdefault("heading_text", "#ffffff")
    style.setdefault("heading_fill_transparency", 0.04)
    style.setdefault("chip_fill", slide_spec.soft_color)
    style.setdefault("chip_text", slide_spec.accent_color)
    style.setdefault("chip_line", slide_spec.accent_color)
    style.setdefault("chip_fill_transparency", 0.18)
    style.setdefault("chip_line_transparency", 0.48)
    return style


def _opacity_from_transparency(value: float) -> str:
    opacity = max(0.0, min(1.0, 1.0 - value))
    return f"{opacity:.2f}"


def _citation_markup(
    slide_spec: SvgSlideSpec,
    citations: list[Citation],
    theme_id: str | None,
) -> str:
    labels: list[str] = []
    for citation in citations:
        label = _citation_label(citation)
        if label and label not in labels:
            labels.append(label)

    if not labels:
        return ""

    profile = _citation_layout_profile(slide_spec)
    theme_style = _citation_theme_style(theme_id, slide_spec)
    max_visible = profile["max_visible"]
    visible_labels = labels[:max_visible]
    remaining = len(labels) - len(visible_labels)
    if remaining > 0:
        visible_labels.append(f"+{remaining} more")

    heading_x = profile["heading_x"]
    heading_y = profile["heading_y"]
    heading_width = profile["heading_width"]
    heading_height = profile["heading_height"]
    chip_width = profile["chip_width"]
    chip_height = profile["chip_height"]
    chip_gap = profile["chip_gap"]

    if slide_spec.layout_name == "cover-hero":
        total_height = heading_height + 6 + (len(visible_labels) * chip_height) + (max(len(visible_labels) - 1, 0) * chip_gap)
        heading_y = max(slide_spec.height - total_height - 44, 86)

    title_font = escape(_font_stack(slide_spec.title_font_family))
    body_font = escape(_font_stack(slide_spec.body_font_family))
    heading_fill = escape(str(theme_style["heading_fill"]))
    heading_text = escape(str(theme_style["heading_text"]))
    chip_fill = escape(str(theme_style["chip_fill"]))
    chip_text = escape(str(theme_style["chip_text"]))
    chip_line = escape(str(theme_style["chip_line"]))
    heading_fill_opacity = _opacity_from_transparency(float(theme_style["heading_fill_transparency"]))
    chip_fill_opacity = _opacity_from_transparency(float(theme_style["chip_fill_transparency"]))
    chip_line_opacity = _opacity_from_transparency(float(theme_style["chip_line_transparency"]))

    parts = [
        '<g data-role="citation-panel">',
        f'<rect x="{heading_x}" y="{heading_y}" width="{heading_width}" height="{heading_height}" rx="12" fill="{heading_fill}" fill-opacity="{heading_fill_opacity}"/>',
        f'<text x="{heading_x + heading_width / 2}" y="{heading_y + heading_height / 2 + 1}" font-size="11" font-weight="700" text-anchor="middle" dominant-baseline="middle" fill="{heading_text}" font-family="{title_font}">References</text>',
    ]

    chip_y = heading_y + heading_height + 6
    chip_font_size = 9 if slide_spec.layout_name == "timeline-ribbon" else 10
    for label in visible_labels:
        safe_label = escape(label)
        parts.append(
            f'<rect x="{heading_x}" y="{chip_y}" width="{chip_width}" height="{chip_height}" rx="15" '
            f'fill="{chip_fill}" fill-opacity="{chip_fill_opacity}" stroke="{chip_line}" stroke-opacity="{chip_line_opacity}" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{heading_x + 14}" y="{chip_y + chip_height / 2 + 1}" font-size="{chip_font_size}" dominant-baseline="middle" '
            f'fill="{chip_text}" font-family="{body_font}">{safe_label}</text>'
        )
        chip_y += chip_height + chip_gap

    parts.append("</g>")
    return "".join(parts)


def _header_block(slide: SlidePlanItem, palette: dict[str, str], style_preset: str) -> SvgBlockSpec:
    header_title = slide.title if slide.slide_type != SlideType.COVER else "Lesson Frame"
    body_lines = [
        f"TYPE · {slide.slide_type.value}",
        f"GOAL · {slide.goal}",
        f"MODE · {slide.interaction_mode.value}",
    ]
    return _block(
        role="header",
        title=header_title,
        text_lines=body_lines,
        x=60,
        y=44,
        width=1160,
        height=116,
        accent_color=palette["accent"],
        background_fill="#ffffff",
        text_color=palette["text"],
        title_size=30 if style_preset == "clean-grid" else 28,
        body_size=14,
        corner_radius=36,
        shape_variant="hero-bar",
    )


def _cover_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    hero = _block(
        role="hero",
        title=slide.title,
        text_lines=_trim_lines(slide.key_points + slide.visual_brief or [slide.goal], limit=4),
        x=60,
        y=188,
        width=700,
        height=364,
        accent_color=palette["accent"],
        background_fill="#ffffff",
        text_color=palette["text"],
        title_size=34,
        body_size=22,
        corner_radius=38,
        shape_variant="spotlight",
    )
    launch_chip = _block(
        role="launch-chip",
        title=f"Launch · {slide.interaction_mode.value}",
        text_lines=[],
        x=60,
        y=164,
        width=220,
        height=42,
        accent_color=palette["accent"],
        background_fill=palette["soft"],
        text_color=palette["text"],
        title_size=14,
        corner_radius=21,
        shape_variant="chip",
    )
    snapshot = _block(
        role="snapshot",
        title="Class Snapshot",
        text_lines=_trim_lines(
            [
                slide.goal,
                slide.layout_hint or "封面强调学习目标与课堂入口问题",
                *(slide.speaker_notes[:2] or ["先用真实情境导入，再交代本课任务。"]),
            ],
            limit=4,
        ),
        x=790,
        y=188,
        width=430,
        height=158,
        accent_color=palette["accent"],
        background_fill=palette["soft"],
        text_color=palette["text"],
        body_size=16,
        corner_radius=28,
        shape_variant="glass-card",
    )
    rhythm = _block(
        role="rhythm",
        title="Lesson Rhythm",
        text_lines=_trim_lines(
            slide.visual_brief or [slide.layout_hint or "主视觉区 + 任务标签 + 教师提示卡"],
            limit=4,
        ),
        x=790,
        y=368,
        width=200,
        height=184,
        accent_color=palette["accent"],
        background_fill="#ffffff",
        text_color=palette["text"],
        body_size=16,
        corner_radius=26,
        shape_variant="editorial-panel",
    )
    source_lens = _block(
        role="source-lens",
        title="Source Lens",
        text_lines=_citation_lines(slide, "这里可放教材、资料摘录或课堂观察点。", limit=4),
        x=1010,
        y=368,
        width=210,
        height=184,
        accent_color=palette["accent"],
        background_fill="#ffffff",
        text_color=palette["text"],
        body_size=15,
        corner_radius=26,
        shape_variant="outline-card",
    )
    footer = _block(
        role="footer-strip",
        title="Opening Move",
        text_lines=_trim_lines(
            [
                slide.layout_hint or "封面用情境导入，避免只展示标题",
                *(slide.speaker_notes[:1] or []),
            ],
            limit=2,
        ),
        x=60,
        y=582,
        width=1160,
        height=82,
        accent_color=palette["accent"],
        background_fill=palette["soft"],
        text_color=palette["text"],
        body_size=16,
        corner_radius=24,
        shape_variant="strip",
    )
    return "cover-hero", [launch_chip, hero, snapshot, rhythm, source_lens, footer]


def _split_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    blocks = [
        _block(
            role="knowledge-core",
            title="Knowledge Core",
            text_lines=_trim_lines(slide.key_points + [slide.goal], limit=5),
            x=60,
            y=196,
            width=620,
            height=266,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=18,
            corner_radius=34,
            shape_variant="spotlight",
        ),
        _block(
            role="visual-brief",
            title="Visual System",
            text_lines=_trim_lines(slide.visual_brief or [slide.layout_hint or "卡片式布局"], limit=4),
            x=710,
            y=196,
            width=510,
            height=158,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=16,
            shape_variant="glass-card",
        ),
        _block(
            role="teaching-move",
            title="Teaching Move",
            text_lines=_trim_lines(slide.speaker_notes or ["根据本页目标组织讲解和提问。"], limit=4),
            x=710,
            y=380,
            width=510,
            height=168,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            shape_variant="editorial-panel",
        ),
        _block(
            role="evidence-strip",
            title="Evidence Snapshot",
            text_lines=_citation_lines(slide, "暂无引用片段，可后续补充资料来源。", limit=4),
            x=60,
            y=490,
            width=620,
            height=158,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            shape_variant="outline-card",
        ),
        _block(
            role="design-note",
            title="Design Note",
            text_lines=_trim_lines(
                [
                    slide.layout_hint or "双栏卡片布局，左概念右示例",
                    "适合将概念、例证和教师提示并列展示",
                ],
                limit=3,
            ),
            x=60,
            y=666,
            width=1160,
            height=56,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=14,
            corner_radius=22,
            shape_variant="strip",
        ),
    ]
    return "split-grid", blocks


def _comparison_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    left_lines = _trim_lines(slide.key_points[:2] or [slide.goal], limit=3)
    right_lines = _trim_lines(slide.visual_brief[:2] or [slide.layout_hint or "突出对照关系"], limit=3)
    bottom_lines = _trim_lines(slide.speaker_notes + [citation.note or citation.page_label or citation.asset_id for citation in slide.citations], limit=5)
    blocks = [
        _block(
            role="left-column",
            title="Perspective A",
            text_lines=left_lines,
            x=60,
            y=196,
            width=500,
            height=282,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            corner_radius=32,
            shape_variant="spotlight",
        ),
        _block(
            role="right-column",
            title="Perspective B",
            text_lines=right_lines,
            x=720,
            y=196,
            width=500,
            height=282,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            corner_radius=32,
            shape_variant="glass-card",
        ),
        _block(
            role="compare-chip",
            title="Compare",
            text_lines=[],
            x=590,
            y=310,
            width=100,
            height=48,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            title_size=15,
            corner_radius=24,
            shape_variant="chip",
        ),
        _block(
            role="criteria-panel",
            title="Criteria",
            text_lines=_trim_lines(
                [
                    slide.goal,
                    slide.layout_hint or "围绕关键差异、共性和迁移点展开对照",
                    "让学生先观察，再用问题驱动比较",
                ],
                limit=4,
            ),
            x=60,
            y=510,
            width=350,
            height=140,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=15,
            corner_radius=26,
            shape_variant="editorial-panel",
        ),
        _block(
            role="evidence-strip",
            title="Evidence and Teaching Notes",
            text_lines=bottom_lines or ["补充材料证据、讲解提醒和对照结论。"],
            x=440,
            y=510,
            width=780,
            height=140,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            corner_radius=28,
            shape_variant="strip",
        ),
    ]
    return "comparison-columns", blocks


def _activity_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    blocks = [
        _block(
            role="activity-tag",
            title="Studio Task",
            text_lines=[],
            x=60,
            y=164,
            width=180,
            height=42,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            title_size=14,
            corner_radius=21,
            shape_variant="chip",
        ),
        _block(
            role="task-brief",
            title="Task Brief",
            text_lines=_trim_lines([slide.goal] + slide.key_points, limit=5),
            x=60,
            y=196,
            width=450,
            height=352,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=18,
            corner_radius=38,
            shape_variant="spotlight",
        ),
        _block(
            role="workflow",
            title="Workflow",
            text_lines=_trim_lines(
                slide.visual_brief or [slide.layout_hint or "说明任务步骤、分组方式和输出形式"],
                limit=5,
            ),
            x=540,
            y=196,
            width=300,
            height=352,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=16,
            corner_radius=32,
            shape_variant="glass-card",
        ),
        _block(
            role="teacher-moves",
            title="Teacher Moves",
            text_lines=_trim_lines(slide.speaker_notes or ["教师说明规则后，预留学生协作和汇报时间。"], limit=4),
            x=870,
            y=196,
            width=350,
            height=158,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            corner_radius=28,
            shape_variant="editorial-panel",
        ),
        _block(
            role="output-check",
            title="Output Check",
            text_lines=_trim_lines(
                [
                    slide.layout_hint or "输出形式、评价标准和汇报顺序要清楚可见",
                    "建议保留学生产出展示区和评价提示区",
                ],
                limit=3,
            ),
            x=870,
            y=382,
            width=350,
            height=166,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=15,
            corner_radius=28,
            shape_variant="outline-card",
        ),
        _block(
            role="reference-rail",
            title="Reference Rail",
            text_lines=_citation_lines(slide, "活动页可进一步补充案例、样题或任务来源。", limit=4),
            x=60,
            y=580,
            width=1160,
            height=84,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=15,
            corner_radius=24,
            shape_variant="strip",
        ),
    ]
    return "workshop-board", blocks


def _assignment_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    blocks = [
        _block(
            role="assignment-tag",
            title="After Class",
            text_lines=[],
            x=60,
            y=164,
            width=170,
            height=42,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            title_size=14,
            corner_radius=21,
            shape_variant="chip",
        ),
        _block(
            role="assignment-core",
            title="Assignment Core",
            text_lines=_trim_lines([slide.goal] + slide.key_points, limit=5),
            x=60,
            y=196,
            width=520,
            height=280,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=17,
            corner_radius=36,
            shape_variant="spotlight",
        ),
        _block(
            role="deliverables",
            title="Deliverables",
            text_lines=_trim_lines(slide.visual_brief or ["明确作业提交物、完成形式和时间要求"], limit=4),
            x=610,
            y=196,
            width=280,
            height=280,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=16,
            corner_radius=32,
            shape_variant="glass-card",
        ),
        _block(
            role="success-criteria",
            title="Success Criteria",
            text_lines=_trim_lines(
                slide.speaker_notes or ["给出评价标准、完成层级和自查提醒。"],
                limit=4,
            ),
            x=920,
            y=196,
            width=300,
            height=280,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            corner_radius=30,
            shape_variant="editorial-panel",
        ),
        _block(
            role="support-panel",
            title="Support and Reference",
            text_lines=_trim_lines(
                [
                    slide.layout_hint or "作业页建议采用清单 + 评价标准布局",
                    *_citation_lines(slide, "可补充样例答案、资源链接或引用出处。", limit=3),
                ],
                limit=4,
            ),
            x=60,
            y=510,
            width=1160,
            height=140,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            corner_radius=28,
            shape_variant="strip",
        ),
    ]
    return "assignment-brief", blocks


def _process_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    step_lines = _trim_lines(slide.key_points + slide.visual_brief, limit=6)
    grouped = [step_lines[0:2], step_lines[2:4], step_lines[4:6]]
    blocks = [
        _block(
            role="process-intro",
            title="Method Frame",
            text_lines=_trim_lines([slide.goal, slide.layout_hint or "强调步骤顺序、关键动作和判断点"], limit=3),
            x=60,
            y=188,
            width=1160,
            height=96,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=16,
            corner_radius=34,
            shape_variant="spotlight",
        ),
    ]
    x_positions = [60, 360, 660]
    for index, (chunk, x) in enumerate(zip(grouped, x_positions), start=1):
        blocks.append(
            _block(
                role=f"process-step-{index}",
                title=f"Step {index}",
                text_lines=chunk or [slide.goal],
                x=x,
                y=334,
                width=250,
                height=236,
                accent_color=palette["accent"],
                background_fill="#ffffff" if index != 2 else palette["soft"],
                text_color=palette["text"],
                body_size=16,
                corner_radius=32,
                shape_variant="glass-card" if index == 2 else "editorial-panel",
            )
        )
    blocks.extend(
        [
            _block(
                role="teacher-cue",
                title="Teacher Cue",
                text_lines=_trim_lines(slide.speaker_notes or ["每一步都要交代判断点和易错提醒。"], limit=4),
                x=950,
                y=334,
                width=270,
                height=150,
                accent_color=palette["accent"],
                background_fill="#ffffff",
                text_color=palette["text"],
                body_size=15,
                corner_radius=28,
                shape_variant="outline-card",
            ),
            _block(
                role="reference-panel",
                title="Reference",
                text_lines=_citation_lines(slide, "可在这里挂接例题、图示或过程演示来源。", limit=4),
                x=950,
                y=510,
                width=270,
                height=150,
                accent_color=palette["accent"],
                background_fill=palette["soft"],
                text_color=palette["text"],
                body_size=15,
                corner_radius=28,
                shape_variant="glass-card",
            ),
        ]
    )
    return "process-ladder", blocks


def _media_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    blocks = [
        _block(
            role="media-frame",
            title="Visual Stage",
            text_lines=_trim_lines(slide.visual_brief or [slide.layout_hint or "这里预留图片、材料摘录或示例题展示区"], limit=4),
            x=60,
            y=196,
            width=700,
            height=404,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=18,
            corner_radius=38,
            shape_variant="spotlight",
        ),
        _block(
            role="analysis-panel",
            title="Analysis Lens",
            text_lines=_trim_lines([slide.goal] + slide.key_points, limit=4),
            x=800,
            y=196,
            width=420,
            height=180,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=16,
            corner_radius=30,
            shape_variant="glass-card",
        ),
        _block(
            role="teacher-panel",
            title="Teaching Prompt",
            text_lines=_trim_lines(slide.speaker_notes or ["引导学生先观察，再说证据和结论。"], limit=4),
            x=800,
            y=404,
            width=420,
            height=120,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=15,
            corner_radius=28,
            shape_variant="editorial-panel",
        ),
        _block(
            role="source-panel",
            title="Source Notes",
            text_lines=_citation_lines(slide, "这里展示引用出处、页码或资料说明。", limit=4),
            x=800,
            y=548,
            width=420,
            height=116,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=15,
            corner_radius=26,
            shape_variant="outline-card",
        ),
    ]
    return "media-gallery", blocks


def _summary_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    recap_lines = _trim_lines(slide.key_points or [slide.goal], limit=3)
    transfer_lines = _trim_lines(slide.visual_brief or ["指出迁移任务、延伸练习或课后要求"], limit=3)
    notes_lines = _trim_lines(slide.speaker_notes or ["回顾重点后，用退出问题确认学生理解"], limit=3)
    footer_lines = _trim_lines(
        [citation.note or citation.page_label or citation.asset_id for citation in slide.citations]
        or [slide.layout_hint or "总结页强调结构收束和下一步任务"],
        limit=3,
    )
    blocks = [
        _block(
            role="takeaway-strip",
            title="Big Takeaway",
            text_lines=_trim_lines([slide.goal] + recap_lines, limit=3),
            x=60,
            y=188,
            width=1160,
            height=110,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            title_size=28,
            body_size=16,
            corner_radius=34,
            shape_variant="spotlight",
        ),
        _block(
            role="recap-a",
            title="Recap",
            text_lines=recap_lines,
            x=60,
            y=334,
            width=360,
            height=206,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            corner_radius=34,
            shape_variant="editorial-panel",
        ),
        _block(
            role="recap-b",
            title="Transfer",
            text_lines=transfer_lines,
            x=460,
            y=334,
            width=360,
            height=206,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            corner_radius=34,
            shape_variant="glass-card",
        ),
        _block(
            role="recap-c",
            title="Teacher Prompt",
            text_lines=notes_lines,
            x=860,
            y=334,
            width=360,
            height=206,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            corner_radius=34,
            shape_variant="outline-card",
        ),
        _block(
            role="footer-strip",
            title="Closing Cue",
            text_lines=footer_lines,
            x=60,
            y=570,
            width=1160,
            height=96,
            accent_color=palette["accent"],
            background_fill=palette["soft"],
            text_color=palette["text"],
            body_size=16,
            corner_radius=26,
            shape_variant="strip",
        ),
    ]
    return "recap-strip", blocks


def _timeline_layout(slide: SlidePlanItem, palette: dict[str, str]) -> tuple[str, list[SvgBlockSpec]]:
    timeline_lines = _trim_lines(slide.key_points + slide.visual_brief + [slide.goal], limit=8)
    chunks = [timeline_lines[0:2], timeline_lines[2:4], timeline_lines[4:6]]
    blocks: list[SvgBlockSpec] = [
        _block(
            role="timeline-intro",
            title="Timeline Lens",
            text_lines=_trim_lines(
                [slide.goal, slide.layout_hint or "用阶段线索串联概念、事件或方法推进"],
                limit=3,
            ),
            x=60,
            y=188,
            width=1160,
            height=96,
            accent_color=palette["accent"],
            background_fill="#ffffff",
            text_color=palette["text"],
            body_size=16,
            corner_radius=34,
            shape_variant="spotlight",
        )
    ]
    positions = [(74, 334), (430, 278), (800, 334)]
    widths = [290, 340, 320]
    heights = [184, 220, 184]
    variants = ["editorial-panel", "spotlight", "glass-card"]
    for index, (chunk, (x, y), width, height, variant) in enumerate(zip(chunks, positions, widths, heights, variants), start=1):
        blocks.append(
            _block(
                role=f"timeline-step-{index}",
                title=f"Stage {index}",
                text_lines=chunk or [slide.goal],
                x=x,
                y=y,
                width=width,
                height=height,
                accent_color=palette["accent"],
                background_fill="#ffffff" if index != 2 else palette["soft"],
                text_color=palette["text"],
                body_size=16,
                corner_radius=32,
                shape_variant=variant,
            )
        )
    blocks.extend(
        [
            _block(
                role="timeline-notes",
                title="Teaching Notes",
                text_lines=_trim_lines(slide.speaker_notes or ["用阶段推进方式讲解本页内容。"], limit=4),
                x=60,
                y=570,
                width=760,
                height=94,
                accent_color=palette["accent"],
                background_fill="#ffffff",
                text_color=palette["text"],
                body_size=15,
                corner_radius=24,
                shape_variant="strip",
            ),
            _block(
                role="timeline-source",
                title="Source Pointer",
                text_lines=_citation_lines(slide, "可补充史料、案例或阶段证据。", limit=3),
                x=850,
                y=570,
                width=370,
                height=94,
                accent_color=palette["accent"],
                background_fill=palette["soft"],
                text_color=palette["text"],
                body_size=14,
                corner_radius=24,
                shape_variant="glass-card",
            ),
        ]
    )
    return "timeline-ribbon", blocks


def _blocks_for_slide(slide: SlidePlanItem, palette: dict[str, str], style_preset: str) -> tuple[str, list[SvgBlockSpec]]:
    header = _header_block(slide, palette, style_preset)
    template_id = slide.template_id or select_template_id(slide.slide_type)
    template_builders = {
        "cover-hero": _cover_layout,
        "split-grid": _split_layout,
        "comparison-columns": _comparison_layout,
        "process-ladder": _process_layout,
        "media-gallery": _media_layout,
        "workshop-board": _activity_layout,
        "assignment-brief": _assignment_layout,
        "recap-strip": _summary_layout,
        "timeline-ribbon": _timeline_layout,
    }
    builder = template_builders.get(template_id, _split_layout)
    layout_name, blocks = builder(slide, palette)
    return layout_name, [header] + blocks


def _decorative_markup(slide_spec: SvgSlideSpec) -> str:
    accent = escape(slide_spec.accent_color)
    soft = escape(slide_spec.soft_color)
    if slide_spec.layout_name == "cover-hero":
        return (
            f'<rect x="36" y="34" width="1208" height="652" rx="36" fill="none" stroke="{soft}" stroke-opacity="0.55" stroke-width="1.5"/>'
            f'<circle cx="1110" cy="120" r="168" fill="url(#accentGlow)" fill-opacity="0.92"/>'
            f'<circle cx="1044" cy="608" r="220" fill="{soft}" fill-opacity="0.28"/>'
            f'<path d="M58 176 C180 136, 302 144, 408 188" stroke="{accent}" stroke-opacity="0.18" stroke-width="3" fill="none"/>'
            f'<rect x="60" y="180" width="8" height="420" rx="4" fill="{accent}" fill-opacity="0.24"/>'
        )
    if slide_spec.layout_name == "split-grid":
        return (
            f'<rect x="48" y="178" width="1184" height="490" rx="38" fill="none" stroke="{soft}" stroke-opacity="0.44" stroke-width="1.5"/>'
            f'<circle cx="1140" cy="110" r="130" fill="{soft}" fill-opacity="0.22"/>'
            f'<path d="M710 186 L710 650" stroke="{accent}" stroke-opacity="0.12" stroke-width="2" stroke-dasharray="8 12"/>'
            f'<rect x="58" y="660" width="1164" height="6" rx="3" fill="{accent}" fill-opacity="0.10"/>'
        )
    if slide_spec.layout_name == "comparison-columns":
        return (
            f'<rect x="592" y="184" width="96" height="392" rx="36" fill="{soft}" fill-opacity="0.22"/>'
            f'<rect x="638" y="220" width="6" height="284" rx="3" fill="{accent}" fill-opacity="0.22"/>'
            f'<circle cx="641" cy="336" r="14" fill="{accent}" fill-opacity="0.28"/>'
            f'<path d="M92 210 C236 166, 404 164, 540 208" stroke="{accent}" stroke-opacity="0.12" stroke-width="2" fill="none"/>'
            f'<path d="M742 208 C886 164, 1056 166, 1186 210" stroke="{accent}" stroke-opacity="0.12" stroke-width="2" fill="none"/>'
        )
    if slide_spec.layout_name == "workshop-board":
        return (
            f'<rect x="44" y="182" width="1188" height="494" rx="40" fill="none" stroke="{soft}" stroke-opacity="0.42" stroke-width="1.5"/>'
            f'<rect x="524" y="186" width="8" height="384" rx="4" fill="{accent}" fill-opacity="0.18"/>'
            f'<circle cx="1086" cy="118" r="112" fill="{soft}" fill-opacity="0.28"/>'
            f'<path d="M86 564 C254 536, 434 542, 604 574" stroke="{accent}" stroke-opacity="0.10" stroke-width="2" fill="none"/>'
        )
    if slide_spec.layout_name == "assignment-brief":
        return (
            f'<rect x="46" y="182" width="1188" height="488" rx="40" fill="none" stroke="{soft}" stroke-opacity="0.38" stroke-width="1.5"/>'
            f'<rect x="606" y="196" width="4" height="280" rx="2" fill="{accent}" fill-opacity="0.12"/>'
            f'<circle cx="1120" cy="120" r="120" fill="{soft}" fill-opacity="0.24"/>'
        )
    if slide_spec.layout_name == "process-ladder":
        return (
            f'<rect x="48" y="182" width="1184" height="488" rx="40" fill="none" stroke="{soft}" stroke-opacity="0.40" stroke-width="1.5"/>'
            f'<path d="M190 452 L344 452" stroke="{accent}" stroke-opacity="0.18" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M492 452 L646 452" stroke="{accent}" stroke-opacity="0.18" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M790 452 L944 452" stroke="{accent}" stroke-opacity="0.18" stroke-width="6" stroke-linecap="round"/>'
            f'<circle cx="344" cy="452" r="10" fill="{accent}" fill-opacity="0.24"/>'
            f'<circle cx="646" cy="452" r="10" fill="{accent}" fill-opacity="0.24"/>'
            f'<circle cx="944" cy="452" r="10" fill="{accent}" fill-opacity="0.24"/>'
        )
    if slide_spec.layout_name == "media-gallery":
        return (
            f'<rect x="46" y="182" width="1188" height="506" rx="42" fill="none" stroke="{soft}" stroke-opacity="0.40" stroke-width="1.5"/>'
            f'<rect x="94" y="236" width="632" height="290" rx="24" fill="{soft}" fill-opacity="0.14" stroke="{accent}" stroke-opacity="0.10" stroke-dasharray="10 8"/>'
            f'<circle cx="1120" cy="118" r="118" fill="{soft}" fill-opacity="0.22"/>'
        )
    if slide_spec.layout_name == "recap-strip":
        return (
            f'<rect x="48" y="178" width="1184" height="506" rx="42" fill="none" stroke="{soft}" stroke-opacity="0.40" stroke-width="1.5"/>'
            f'<circle cx="1094" cy="118" r="132" fill="{soft}" fill-opacity="0.24"/>'
            f'<rect x="76" y="558" width="1128" height="3" rx="1.5" fill="{accent}" fill-opacity="0.12"/>'
        )
    if slide_spec.layout_name == "timeline-ribbon":
        return (
            f'<path d="M176 438 C320 360, 404 334, 598 388 C744 430, 826 468, 1014 424" stroke="{accent}" stroke-opacity="0.18" stroke-width="8" fill="none" stroke-linecap="round"/>'
            f'<circle cx="220" cy="414" r="18" fill="{accent}" fill-opacity="0.24"/>'
            f'<circle cx="600" cy="388" r="20" fill="{accent}" fill-opacity="0.26"/>'
            f'<circle cx="1010" cy="426" r="18" fill="{accent}" fill-opacity="0.24"/>'
            f'<rect x="44" y="182" width="1188" height="494" rx="40" fill="none" stroke="{soft}" stroke-opacity="0.36" stroke-width="1.5"/>'
        )
    return (
        f'<circle cx="1130" cy="120" r="150" fill="{accent}" fill-opacity="0.08"/>'
        f'<circle cx="180" cy="660" r="180" fill="{soft}" fill-opacity="0.30"/>'
    )


def _svg_defs(slide_spec: SvgSlideSpec) -> str:
    accent = escape(slide_spec.accent_color)
    soft = escape(slide_spec.soft_color)
    background = escape(slide_spec.background)
    return (
        "<defs>"
        '<filter id="shadowSoft" x="-20%" y="-20%" width="140%" height="160%">'
        '<feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#15324c" flood-opacity="0.10"/>'
        "</filter>"
        '<filter id="shadowStrong" x="-20%" y="-20%" width="150%" height="180%">'
        '<feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#11263b" flood-opacity="0.16"/>'
        "</filter>"
        '<linearGradient id="accentGlow" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{accent}" stop-opacity="0.22"/>'
        f'<stop offset="100%" stop-color="{soft}" stop-opacity="0.04"/>'
        "</linearGradient>"
        '<linearGradient id="panelWash" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{background}"/>'
        f'<stop offset="100%" stop-color="{soft}" stop-opacity="0.24"/>'
        "</linearGradient>"
        "</defs>"
    )


def _shadow_filter(shape_variant: str) -> str:
    if shape_variant in {"hero", "spotlight"}:
        return ' filter="url(#shadowStrong)"'
    if shape_variant in {"soft-card", "glass-card", "editorial-panel", "hero-bar", "card", "outline-card"}:
        return ' filter="url(#shadowSoft)"'
    return ""


def _block_markup(block: SvgBlockSpec, slide_spec: SvgSlideSpec) -> str:
    title = escape(block.title or "")
    accent = escape(block.accent_color or "#16324f")
    stroke = escape(block.stroke_color or accent)
    bg = escape(block.background_fill)
    text = escape(block.text_color)
    title_font = escape(_font_stack(slide_spec.title_font_family))
    body_font = escape(_font_stack(slide_spec.body_font_family))
    shadow = _shadow_filter(block.shape_variant)

    if block.shape_variant == "chip":
        return (
            f'<g data-role="{escape(block.role)}" data-variant="{escape(block.shape_variant)}">'
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" stroke="{stroke}" stroke-opacity="0.16" stroke-width="1.5"/>'
            f'<text x="{block.x + block.width / 2}" y="{block.y + block.height / 2 + 1}" '
            f'font-size="{block.title_size}" font-weight="700" text-anchor="middle" dominant-baseline="middle" '
            f'fill="{accent}" font-family="{title_font}">{title}</text>'
            "</g>"
        )

    if block.shape_variant == "hero":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" stroke="{stroke}" stroke-opacity="0.14" stroke-width="2"{shadow}/>'
        )
    elif block.shape_variant == "spotlight":
        rect = (
            f'<rect x="{block.x + 8}" y="{block.y + 10}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{accent}" fill-opacity="0.08" stroke="none"/>'
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="url(#panelWash)" stroke="{stroke}" stroke-opacity="0.18" stroke-width="2"{shadow}/>'
        )
    elif block.shape_variant == "soft-card":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" stroke="{stroke}" stroke-opacity="0.10" stroke-width="2"{shadow}/>'
        )
    elif block.shape_variant == "glass-card":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" fill-opacity="0.92" stroke="{stroke}" stroke-opacity="0.12" stroke-width="1.8"{shadow}/>'
            f'<rect x="{block.x + 18}" y="{block.y + 18}" width="{max(block.width - 36, 0)}" height="16" '
            f'rx="8" fill="#ffffff" fill-opacity="0.45" stroke="none"/>'
        )
    elif block.shape_variant == "outline-card":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="#ffffff" stroke="{stroke}" stroke-opacity="0.22" stroke-width="2"{shadow}/>'
        )
    elif block.shape_variant == "strip":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" stroke="none"/>'
        )
    elif block.shape_variant == "editorial-panel":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="#ffffff" stroke="{stroke}" stroke-opacity="0.18" stroke-width="1.8"{shadow}/>'
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="16" rx="{block.corner_radius}" fill="{accent}" fill-opacity="0.08" stroke="none"/>'
        )
    elif block.shape_variant == "hero-bar":
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="#ffffff" stroke="{stroke}" stroke-opacity="0.16" stroke-width="2"{shadow}/>'
        )
    else:
        rect = (
            f'<rect x="{block.x}" y="{block.y}" width="{block.width}" height="{block.height}" '
            f'rx="{block.corner_radius}" fill="{bg}" stroke="{stroke}" stroke-opacity="0.18" stroke-width="2"{shadow}/>'
        )

    accent_mark = ""
    if block.shape_variant not in {"strip"}:
        accent_mark = f'<rect x="{block.x + 18}" y="{block.y + 18}" width="132" height="6" rx="3" fill="{accent}" fill-opacity="0.24"/>'
    lines = []
    body_start_y = block.y + 70
    for index, line in enumerate(block.text_lines):
        y = body_start_y + index * (block.body_size + 10)
        lines.append(
            f'<text x="{block.x + 24}" y="{y}" font-size="{block.body_size}" fill="{text}" font-family="{body_font}">{escape(line)}</text>'
        )
    return (
        f'<g data-role="{escape(block.role)}" data-variant="{escape(block.shape_variant)}">'
        f"{rect}"
        f"{accent_mark}"
        f'<text x="{block.x + 24}" y="{block.y + 50}" font-size="{block.title_size}" font-weight="700" fill="{accent}" font-family="{title_font}">{title}</text>'
        f'{"".join(lines)}'
        "</g>"
    )


def _render_markup(
    slide_spec: SvgSlideSpec,
    citations: list[Citation] | None = None,
    theme_id: str | None = None,
) -> str:
    decorative = _decorative_markup(slide_spec)
    body_font = escape(_font_stack(slide_spec.body_font_family))
    citation_markup = _citation_markup(slide_spec, citations or [], theme_id)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{slide_spec.width}" height="{slide_spec.height}" viewBox="0 0 {slide_spec.width} {slide_spec.height}">'
        f"{_svg_defs(slide_spec)}"
        f'<rect width="{slide_spec.width}" height="{slide_spec.height}" fill="{escape(slide_spec.background)}"/>'
        f"{decorative}"
        f'<text x="60" y="34" font-size="14" fill="#627487" font-family="{body_font}">Slide {slide_spec.slide_number}</text>'
        f'{"".join(_block_markup(block, slide_spec) for block in slide_spec.blocks)}'
        f"{citation_markup}"
        "</svg>"
    )


def generate_svg_deck(
    slide_plan: SlidePlan,
    theme_id: str | None = None,
    font_preset: str | None = None,
) -> SvgDeckSpec:
    resolved_theme_id = _resolve_theme_id(theme_id, slide_plan.theme_hint)
    resolved_font_preset = _resolve_font_preset(font_preset)
    font_config = FONT_PRESETS[resolved_font_preset]
    slides: list[SvgSlideSpec] = []
    for slide in slide_plan.slides:
        style_preset = _style_preset(slide_plan.theme_hint, slide.slide_type, resolved_theme_id)
        palette = _palette(resolved_theme_id, slide.slide_type, style_preset)
        layout_name, blocks = _blocks_for_slide(slide, palette, style_preset)
        slide_spec = SvgSlideSpec(
            slide_number=slide.slide_number,
            title=slide.title,
            slide_type=slide.slide_type,
            template_id=slide.template_id or layout_name,
            background=palette["background"],
            accent_color=palette["accent"],
            soft_color=palette["soft"],
            text_color=palette["text"],
            layout_name=layout_name,
            style_preset=style_preset,
            title_font_family=font_config["title"],
            body_font_family=font_config["body"],
            blocks=blocks,
        )
        slide_spec.markup = _render_markup(
            slide_spec,
            citations=slide.citations,
            theme_id=resolved_theme_id,
        )
        slides.append(slide_spec)

    deck = SvgDeckSpec(
        title=f"{slide_plan.title} svg deck",
        theme_hint=slide_plan.theme_hint,
        theme_id=resolved_theme_id,
        font_preset=resolved_font_preset,
        title_font_family=font_config["title"],
        body_font_family=font_config["body"],
        slides=slides,
    )
    return finalize_svg_deck(deck)


def generate_svg_deck_for_session(
    session: SessionState,
    store_namespace: str | None = None,
    top_k: int = 5,
    theme_id: str | None = None,
    font_preset: str | None = None,
) -> SessionState:
    if session.slide_plan is None:
        session = generate_slide_plan_for_session(
            session,
            store_namespace=store_namespace,
            top_k=top_k,
        )

    assert session.slide_plan is not None
    resolved_theme_id = theme_id or session.svg_theme_id
    resolved_font_preset = font_preset or session.svg_font_preset
    session.svg_deck = generate_svg_deck(
        session.slide_plan,
        theme_id=resolved_theme_id,
        font_preset=resolved_font_preset,
    )
    session.svg_theme_id = session.svg_deck.theme_id
    session.svg_font_preset = session.svg_deck.font_preset
    session.stage = SessionStage.PREVIEW
    session.last_summary = (
        f"已生成 {len(session.svg_deck.slides)} 页 SVG 中间稿，"
        f"当前主题为 {session.svg_deck.theme_id}，字体方案为 {session.svg_deck.font_preset}。"
    )
    session.updated_at = utc_now()
    return session
