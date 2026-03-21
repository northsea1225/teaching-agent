import hashlib
import re
from html import unescape
from typing import Protocol
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from app.config import get_settings
from app.models import RetrievalHit


RESULT_BLOCK_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<tail>.*?)(?=(?:<a[^>]+href=)|\Z)',
    flags=re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


class WebSearchProvider(Protocol):
    name: str

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        ...


def _strip_tags(value: str) -> str:
    text = TAG_PATTERN.sub(" ", value)
    return " ".join(unescape(text).split()).strip()


def _normalize_url(raw_url: str) -> str:
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    if raw_url.startswith("/l/?") or "uddg=" in raw_url:
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return unquote(params["uddg"][0])
    return unescape(raw_url)


def _domain_label(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    return domain[4:] if domain.startswith("www.") else domain


def _result_id(url: str) -> str:
    return "web:" + hashlib.blake2b(url.encode("utf-8"), digest_size=10).hexdigest()


class DisabledWebSearchProvider:
    name = "disabled"

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        return []


class DuckDuckGoLiteProvider:
    name = "duckduckgo"
    base_url = "https://lite.duckduckgo.com/lite/"

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def _fetch_html(self, query: str) -> str:
        url = f"{self.base_url}?q={quote_plus(query)}"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TeachingAgent/1.0",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _parse_results(self, html: str, top_k: int) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        seen_urls: set[str] = set()
        for match in RESULT_BLOCK_PATTERN.finditer(html):
            raw_href = match.group("href")
            url = _normalize_url(raw_href)
            if not url.startswith(("http://", "https://")) or url in seen_urls:
                continue
            seen_urls.add(url)

            title = _strip_tags(match.group("title"))
            tail = _strip_tags(match.group("tail"))
            snippet = tail[:260].strip()
            if not title:
                continue

            domain = _domain_label(url)
            content = " ".join(part for part in [title, snippet] if part).strip()
            hits.append(
                RetrievalHit(
                    chunk_id=_result_id(url),
                    asset_id=url,
                    content=content or title,
                    score=max(1.0, float(top_k - len(hits))),
                    page_label=domain or "web",
                    source_type="web",
                    source_url=url,
                    source_title=title,
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        if not query.strip():
            return []
        html = self._fetch_html(query)
        return self._parse_results(html, top_k)


def _provider_from_settings() -> WebSearchProvider:
    settings = get_settings()
    if not settings.web_search_enabled:
        return DisabledWebSearchProvider()
    if settings.web_search_provider == "duckduckgo":
        return DuckDuckGoLiteProvider(settings.web_search_timeout_seconds)
    return DisabledWebSearchProvider()


def search_web_hits(query: str, top_k: int | None = None) -> list[RetrievalHit]:
    settings = get_settings()
    provider = _provider_from_settings()
    if provider.name == "disabled":
        return []
    limit = top_k or settings.web_search_default_top_k
    try:
        return provider.search(query, limit)
    except Exception:
        return []
