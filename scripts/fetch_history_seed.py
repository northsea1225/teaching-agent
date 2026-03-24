from __future__ import annotations

import json
import re
import ssl
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_EXTERNAL_ROOT = Path(r"E:\teaching-agent_resources\subject_seed\history")
TARGET_ROOT = DEFAULT_EXTERNAL_ROOT
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)
SEED_INDEXES: tuple[str, ...] = (
    "https://www.qinghistory.cn/",
    "https://www.qinghistory.cn/wszl1/",
    "https://www.qinghistory.cn/qszl/",
    "https://www.qinghistory.cn/xlmb1/",
)
MAX_CATEGORY_PAGES = 16
MAX_ARTICLES = 60


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
                time.sleep(0.2)
                return response.read().decode("utf-8", errors="ignore")
        except ssl.SSLCertVerificationError:
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            with urlopen(request, timeout=30, context=insecure) as response:
                time.sleep(0.2)
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
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


def discover_category_pages(index_html: str, base_url: str) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for link in extract_links(index_html, base_url):
        parsed = urlparse(link)
        if parsed.netloc != "www.qinghistory.cn":
            continue
        path = parsed.path.rstrip("/")
        if not path.endswith("/") and "." in Path(path).name:
            continue
        if not re.search(r"/(qsyj|qsck|qsbk|xlxh|lzsy|wszl|xzsl|yjkw|qszl|xlmb1)", path + "/"):
            continue
        if link in seen:
            continue
        seen.add(link)
        categories.append(link if link.endswith("/") else link + "/")
    return categories[:MAX_CATEGORY_PAGES]


def discover_article_links(page_html: str, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for link in extract_links(page_html, base_url):
        parsed = urlparse(link)
        if parsed.netloc != "www.qinghistory.cn":
            continue
        if not re.search(r"/c/\d+/\d+\.shtml$", parsed.path):
            continue
        if link in seen:
            continue
        seen.add(link)
        links.append(link)
    return links


def extract_title(html: str, fallback_url: str) -> str:
    for pattern in (
        r"(?is)<h1[^>]*>(.*?)</h1>",
        r"(?is)<h2[^>]*>(.*?)</h2>",
        r"(?is)<h3[^>]*>(.*?)</h3>",
    ):
        match = re.search(pattern, html)
        if match:
            title = strip_html_to_text(match.group(1)).strip()
            if title and len(title) >= 4:
                return title
    match = re.search(r"(?is)<title>(.*?)</title>", html)
    if match:
        title = strip_html_to_text(match.group(1)).split("|")[0].split("_")[0].strip()
        if title:
            return title
    path_name = Path(urlparse(fallback_url).path).stem
    return sanitize_name(path_name)


def category_from_url(url: str) -> str:
    path = urlparse(url).path
    if "/qsyj/" in path or "/qszl/" in path:
        return "history_research"
    if "/qsck/" in path:
        return "history_reference"
    if "/qsbk/" in path:
        return "history_encyclopedia"
    if "/xlxh/" in path or "/xlmb1/" in path:
        return "history_scholarship"
    if "/lzsy/" in path:
        return "historical_examples"
    if "/wszl/" in path or "/wszl1/" in path:
        return "history_readings"
    return "history_misc"


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
    if len(text) < 300:
        return None
    title = extract_title(html, article_url)
    category = category_from_url(article_url)
    category_dir = ensure_dir(TARGET_ROOT / category)
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
    category_pages: list[str] = []
    article_candidates: list[str] = []
    errors: list[dict[str, str]] = []

    for index_url in SEED_INDEXES:
        try:
            html = fetch_html(index_url)
        except Exception as exc:
            errors.append({"url": index_url, "error": str(exc)})
            continue
        category_pages.extend(discover_category_pages(html, index_url))
        if index_url != "https://www.qinghistory.cn/":
            article_candidates.extend(discover_article_links(html, index_url))

    deduped_categories: list[str] = []
    seen_categories: set[str] = set()
    for url in category_pages:
        if url not in seen_categories:
            seen_categories.add(url)
            deduped_categories.append(url)

    for category_url in deduped_categories[:MAX_CATEGORY_PAGES]:
        try:
            html = fetch_html(category_url)
        except Exception as exc:
            errors.append({"url": category_url, "error": str(exc)})
            continue
        article_candidates.extend(discover_article_links(html, category_url))

    deduped_articles: list[str] = []
    seen_articles: set[str] = set()
    for url in article_candidates:
        if url not in seen_articles:
            seen_articles.add(url)
            deduped_articles.append(url)

    saved: list[SavedArticle] = []
    for article_url in deduped_articles:
        if len(saved) >= MAX_ARTICLES:
            break
        try:
            result = save_article(article_url)
        except Exception as exc:
            errors.append({"url": article_url, "error": str(exc)})
            continue
        if result:
            saved.append(result)

    manifest_path = TARGET_ROOT / "download_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "seed_indexes": list(SEED_INDEXES),
                "category_pages": deduped_categories,
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
                "category_pages": len(deduped_categories),
                "saved_articles": len(saved),
                "errors": len(errors),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
