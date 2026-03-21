from app.models import RetrievalHit
from app.services.web_search import DuckDuckGoLiteProvider


def test_duckduckgo_parser_extracts_web_results() -> None:
    provider = DuckDuckGoLiteProvider(timeout_seconds=5)
    html = """
    <html><body>
      <a href="https://example.com/history/industrial-revolution">Industrial Revolution Timeline</a>
      <div>Steam power, factories, and social change overview.</div>
      <a href="/l/?uddg=https%3A%2F%2Fwww.britannica.com%2Ftopic%2FIndustrial-Revolution">Industrial Revolution | Britannica</a>
      <span>Reference article with milestones and impact.</span>
    </body></html>
    """

    hits = provider._parse_results(html, top_k=3)

    assert len(hits) == 2
    assert hits[0].source_type == "web"
    assert hits[0].source_url == "https://example.com/history/industrial-revolution"
    assert hits[0].source_title == "Industrial Revolution Timeline"
    assert "Steam power" in hits[0].content
    assert hits[1].source_url == "https://www.britannica.com/topic/Industrial-Revolution"


def test_web_hit_model_carries_source_metadata() -> None:
    hit = RetrievalHit(
        chunk_id="web:test",
        asset_id="https://example.com",
        content="Example web snippet",
        source_type="web",
        source_url="https://example.com",
        source_title="Example article",
        page_label="example.com",
    )
    assert hit.source_type == "web"
    assert hit.source_title == "Example article"
