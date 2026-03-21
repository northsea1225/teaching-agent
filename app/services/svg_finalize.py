from __future__ import annotations

import re
from html import escape

from app.models import SvgDeckSpec


EMPTY_TEXT_RE = re.compile(r"<text\b[^>]*>\s*</text>")
TAG_GAP_RE = re.compile(r">\s+<")
SVG_OPEN_RE = re.compile(r"(<svg\b[^>]*>)")


def finalize_svg_markup(markup: str, *, slide_title: str, template_id: str | None) -> str:
    compact = markup.replace("\r", "")
    compact = EMPTY_TEXT_RE.sub("", compact)
    compact = TAG_GAP_RE.sub("><", compact)
    compact = compact.strip()

    if "<title>" not in compact:
        compact = SVG_OPEN_RE.sub(
            r"\1"
            + f"<title>{escape(slide_title)}</title><desc>template:{escape(template_id or 'unknown')}</desc>",
            compact,
            count=1,
        )
    return compact


def finalize_svg_deck(deck: SvgDeckSpec) -> SvgDeckSpec:
    slides = []
    for slide in deck.slides:
        slides.append(
            slide.model_copy(
                update={
                    "markup": finalize_svg_markup(
                        slide.markup,
                        slide_title=slide.title,
                        template_id=slide.template_id,
                    )
                }
            )
        )
    return deck.model_copy(update={"slides": slides, "finalized": True})
