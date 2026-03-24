from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


TARGET_ROOT = Path(r"E:\teaching-agent_resources\subject_seed\math")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)
SEED_INDEXES: tuple[str, ...] = (
    "https://www.mathsisfun.com/algebra/index.html",
    "https://www.mathsisfun.com/geometry/index.html",
    "https://www.mathsisfun.com/numbers/index.html",
    "https://www.mathsisfun.com/data/index.html",
    "https://www.mathsisfun.com/measure/index.html",
    "https://www.mathsisfun.com/calculus/index.html",
    "https://www.mathsisfun.com/definitions/index.html",
)
MAX_ARTICLES = 60
DISALLOWED_SEGMENTS = (
    "/games/",
    "/puzzles/",
    "/worksheets/",
    "/activity/",
    "/links/",
    "/search/",
    "/money/",
    "/physics/",
)
DISALLOWED_FILES = {
    "index.html",
    "index-2.html",
    "index-college.html",
    "definitions/index.html",
}


@dataclass(frozen=True)
class SavedArticle:
    title: str
    url: str
    category: str
    saved_to: str
    chars: int


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return cleaned or "resource"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                time.sleep(0.15)
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def strip_html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"""(?i)(?:href|src)\s*=\s*["']([^"'#]+)["']""", html):
        full = urljoin(base_url, unescape(raw))
        if full in seen:
            continue
        seen.add(full)
        links.append(full)
    return links


def allowed_article_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc not in {"www.mathsisfun.com", "mathsisfun.com"}:
        return False
    path = parsed.path
    if any(segment in path for segment in DISALLOWED_SEGMENTS):
        return False
    if path.endswith("/"):
        return False
    if not path.endswith(".html"):
        return False
    if any(path.endswith(bad) for bad in DISALLOWED_FILES):
        return False
    if "/images/" in path:
        return False
    return True


def category_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "math_misc"
    top = parts[0]
    if top == "definitions":
        return "math_definitions"
    return f"math_{top}"


def extract_title(html: str, fallback_url: str) -> str:
    for pattern in (
        r"(?is)<h1[^>]*>(.*?)</h1>",
        r"(?is)<title>(.*?)</title>",
    ):
        match = re.search(pattern, html)
        if match:
            title = strip_html_to_text(match.group(1)).split("|")[0].strip()
            if title:
                return title
    return sanitize_name(Path(urlparse(fallback_url).path).stem)


def unique_output_path(directory: Path, stem: str) -> Path:
    base = sanitize_name(stem)
    candidate = directory / f"{base}.txt"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{base}_{counter}.txt"
        counter += 1
    return candidate


def save_article(article_url: str) -> SavedArticle | None:
    html = fetch_html(article_url)
    text = strip_html_to_text(html)
    if len(text) < 350:
        return None
    parsed = urlparse(article_url)
    category = category_from_path(parsed.path)
    category_dir = ensure_dir(TARGET_ROOT / category)
    title = extract_title(html, article_url)
    output_path = unique_output_path(category_dir, title)
    output_path.write_text(text, encoding="utf-8")
    return SavedArticle(
        title=title,
        url=article_url,
        category=category,
        saved_to=str(output_path),
        chars=len(text),
    )


def main() -> None:
    ensure_dir(TARGET_ROOT)
    candidates: list[str] = []
    errors: list[dict[str, str]] = []

    for seed_url in SEED_INDEXES:
        try:
            html = fetch_html(seed_url)
        except Exception as exc:
            errors.append({"url": seed_url, "error": str(exc)})
            continue
        for link in extract_links(html, seed_url):
            if allowed_article_url(link):
                candidates.append(link)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    saved: list[SavedArticle] = []
    for url in deduped:
        if len(saved) >= MAX_ARTICLES:
            break
        try:
            result = save_article(url)
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})
            continue
        if result:
            saved.append(result)

    manifest_path = TARGET_ROOT / "download_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "seed_indexes": list(SEED_INDEXES),
                "items": [item.__dict__ for item in saved],
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "target_root": str(TARGET_ROOT),
                "saved_articles": len(saved),
                "errors": len(errors),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
