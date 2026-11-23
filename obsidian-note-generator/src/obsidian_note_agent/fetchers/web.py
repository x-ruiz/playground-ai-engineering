"""Web article & technical documentation fetcher using httpx + trafilatura."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

import httpx
import trafilatura

from obsidian_note_agent.fetchers.classifier import SourceType, canonicalize_url
from obsidian_note_agent.fetchers.youtube import FetchedSource, FetchError, _cap_text

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_ISO_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_MD_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)
_HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _normalize_date(raw: str | None) -> str | None:
    if not raw:
        return None
    match = _ISO_DATE_PREFIX_RE.match(raw.strip())
    return match.group(1) if match else None


def _extract_headings(markdown: str) -> tuple[str, ...]:
    headings: list[str] = []
    for match in _MD_HEADING_RE.finditer(markdown):
        heading = match.group(1).strip().strip("#").strip()
        if heading and heading not in headings:
            headings.append(heading)
        if len(headings) >= 15:
            break
    return tuple(headings)


def _fallback_html_title(html: str, url: str) -> str:
    match = _HTML_TITLE_RE.search(html)
    if match:
        cleaned = re.sub(r"\s+", " ", match.group(1)).strip()
        if cleaned:
            return cleaned
    return urlparse(url).netloc or url


def _fallback_url_context(url: str, *, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=model,
        contents=(
            f"Read the page at {url} and extract its core technical content, architecture, "
            "code snippets, CLI/API details, trade-offs, and key headings in clean Markdown. "
            "Exclude navigation bars, cookie banners, and promotional calls to action."
        ),
        config=types.GenerateContentConfig(tools=[types.Tool(url_context=types.UrlContext())]),
    )
    text = (response.text or "").strip()
    if not text:
        raise FetchError(f"Gemini url_context fallback returned empty content for {url}.")
    return text


def fetch_web(
    url: str,
    *,
    source_type: SourceType,
    max_chars: int = 45_000,
    timeout: float = 20.0,
    enable_url_context_fallback: bool = False,
    model: str = "gemini-2.5-flash",
) -> FetchedSource:
    """Fetch a public article or documentation page and extract clean Markdown + provenance."""
    canonical = canonicalize_url(url)

    try:
        resp = httpx.get(
            canonical,
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
        )
    except httpx.HTTPError as exc:
        raise FetchError(
            f"HTTP error fetching {canonical}: {exc}. Paste the page text directly in chat if needed."
        ) from exc

    if resp.status_code in (401, 403, 429):
        raise FetchError(
            f"Access blocked (HTTP {resp.status_code}) fetching {canonical}. "
            "If this page is paywalled or bot-protected, paste the text directly in chat."
        )
    if resp.status_code >= 400:
        raise FetchError(f"Failed to fetch {canonical} (HTTP {resp.status_code}).")

    html = resp.text
    extracted = trafilatura.extract(
        html,
        url=canonical,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_precision=True,
    )
    metadata = trafilatura.extract_metadata(html, default_url=canonical)

    extraction_method = "trafilatura"
    cleaned_text = (extracted or "").strip()

    if len(cleaned_text) < 400:
        if enable_url_context_fallback:
            cleaned_text = _fallback_url_context(canonical, model=model)
            extraction_method = "gemini-url-context"
        elif not cleaned_text:
            raise FetchError(
                f"Could not extract readable text from {canonical} (possibly JS-rendered or paywalled). "
                "Paste the text directly in chat or enable ingestion.enable_url_context_fallback."
            )

    title = (metadata.title.strip() if metadata and metadata.title else None) or _fallback_html_title(
        html, canonical
    )
    raw_author = metadata.author.strip() if metadata and metadata.author else None
    sitename = metadata.sitename.strip() if metadata and metadata.sitename else None
    published = _normalize_date(metadata.date if metadata else None)

    author: str | None = None
    vendor: str | None = None
    if source_type == "article":
        author = raw_author or sitename
    elif source_type == "documentation":
        vendor = sitename or urlparse(canonical).netloc

    sha256 = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    bounded_text, truncated = _cap_text(cleaned_text, max_chars=max_chars)

    return FetchedSource(
        canonical_url=canonical,
        source_type=source_type,
        title=title,
        cleaned_text=bounded_text,
        content_sha256=sha256,
        truncated=truncated,
        author=author,
        vendor=vendor,
        published=published,
        headings=_extract_headings(bounded_text),
        extraction_method=extraction_method,
    )
