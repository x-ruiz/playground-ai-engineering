"""YouTube URL metadata + transcript fetcher with token-budgeting and opt-in video fallback."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import httpx

from obsidian_note_agent.fetchers.classifier import canonicalize_url, extract_youtube_video_id

_NOISE_RE = re.compile(r"\[(music|applause|laughter|inaudible)\]", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched or extracted cleanly."""


@dataclass(frozen=True)
class FetchedSource:
    canonical_url: str
    source_type: str
    title: str
    cleaned_text: str
    content_sha256: str
    truncated: bool = False
    channel: str | None = None
    author: str | None = None
    vendor: str | None = None
    published: str | None = None
    headings: tuple[str, ...] = ()
    extraction_method: str = ""


def _cap_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    head_len = int(max_chars * 0.8)
    tail_len = max_chars - head_len - 80
    clipped = (
        text[:head_len].rstrip()
        + "\n\n[... middle excerpt omitted for token budget ...]\n\n"
        + text[-max(tail_len, 200) :].lstrip()
    )
    return clipped, True


def _fetch_oembed_metadata(canonical_url: str, *, timeout: float) -> tuple[str | None, str | None]:
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": canonical_url, "format": "json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            payload = resp.json()
            title = payload.get("title")
            channel = payload.get("author_name")
            return (
                str(title).strip() if title else None,
                str(channel).strip() if channel else None,
            )
    except Exception:
        pass
    return None, None


def _fetch_transcript_text(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    if hasattr(api, "fetch"):
        fetched = api.fetch(video_id, languages=("en", "en-US", "en-GB"))
        snippets = [getattr(item, "text", "") for item in fetched]
    else:
        # Backwards compatibility for youtube-transcript-api < 1.0
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])  # type: ignore[attr-defined]
        snippets = [str(item.get("text", "")) for item in raw]

    cleaned_parts: list[str] = []
    for raw_line in snippets:
        line = _NOISE_RE.sub("", raw_line)
        line = _WHITESPACE_RE.sub(" ", line).strip()
        if line:
            cleaned_parts.append(line)

    # Group into readable paragraphs (~12 cues each) without timestamp bloat
    paragraphs: list[str] = []
    chunk_size = 12
    for idx in range(0, len(cleaned_parts), chunk_size):
        paragraphs.append(" ".join(cleaned_parts[idx : idx + chunk_size]))
    return "\n\n".join(paragraphs).strip()


def _fallback_gemini_video(canonical_url: str, *, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=model,
        contents=types.Content(
            parts=[
                types.Part.from_uri(file_uri=canonical_url, mime_type="video/mp4"),
                types.Part.from_text(
                    text=(
                        "Extract a dense, accurate technical transcript and key visual slide/code details "
                        "from this video. Include exact code snippets, diagrams, architectures, and "
                        "trade-offs mentioned. Do not add filler."
                    )
                ),
            ]
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise FetchError("Gemini video fallback returned empty output.")
    return text


def fetch_youtube(
    url: str,
    *,
    max_chars: int = 45_000,
    timeout: float = 20.0,
    enable_gemini_video_fallback: bool = False,
    model: str = "gemini-2.5-flash",
) -> FetchedSource:
    """Fetch YouTube title/channel via oEmbed and text transcript via youtube-transcript-api."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise FetchError(f"Could not extract YouTube video ID from URL: {url}")

    canonical = canonicalize_url(url)
    title, channel = _fetch_oembed_metadata(canonical, timeout=timeout)
    resolved_title = title or f"YouTube Video {video_id}"

    extraction_method = "youtube-transcript-api"
    try:
        raw_text = _fetch_transcript_text(video_id)
    except Exception as exc:
        if not enable_gemini_video_fallback:
            raise FetchError(
                f"Could not fetch English captions for {canonical} ({exc}). "
                "Paste the transcript directly in chat or enable ingestion.enable_gemini_video_fallback."
            ) from exc
        raw_text = _fallback_gemini_video(canonical, model=model)
        extraction_method = "gemini-native-video"

    if not raw_text:
        raise FetchError(f"Empty transcript returned for {canonical}.")

    sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    bounded_text, truncated = _cap_text(raw_text, max_chars=max_chars)
    return FetchedSource(
        canonical_url=canonical,
        source_type="youtube",
        title=resolved_title,
        cleaned_text=bounded_text,
        content_sha256=sha256,
        truncated=truncated,
        channel=channel,
        extraction_method=extraction_method,
    )
