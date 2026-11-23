"""Transcript parsing, format normalization, metadata extraction, and SHA-256 hashing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from yt_to_obsidian.matcher import extract_fallback_title

TranscriptFormat = Literal["plain", "timestamped", "srt", "vtt"]

_HEADER_LINE_RE = re.compile(r"^(title|channel|author|url|link)\s*:\s*(.+)$", re.IGNORECASE)
_SRT_TIMING_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}.*$"
)
_VTT_TIMING_RE = re.compile(
    r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{1,2}:)?\d{2}:\d{2}\.\d{3}.*$"
)
_STANDALONE_TIMESTAMP_RE = re.compile(r"^\s*\[?(?:\d{1,2}:)?\d{1,2}:\d{2}\]?\s*$")
_INLINE_PREFIX_TIMESTAMP_RE = re.compile(r"^\s*\[?(?:\d{1,2}:)?\d{1,2}:\d{2}\]?(?:\s*[-–—:]\s*|\s+)")
_VTT_INLINE_TAG_RE = re.compile(r"</?(?:c(?:\.[^>]+)?|i|b|u|v(?:\s+[^>]+)?|\d{2}:\d{2}[^>]*)>")
_HTML_TAG_RE = re.compile(r"</?(?:i|b|u|font[^>]*|span[^>]*)>", re.IGNORECASE)
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


class TranscriptParseError(ValueError):
    """Raised when a transcript file is empty, binary, or unreadable."""


@dataclass(frozen=True)
class TranscriptDocument:
    source_path: Path
    sha256: str
    fallback_title: str
    detected_title: str | None
    channel: str | None
    url: str | None
    detected_format: TranscriptFormat
    cleaned_text: str
    char_count: int

    def render_for_agent(self) -> str:
        """Render normalized transcript with preserved metadata headers for agent input."""
        headers: list[str] = []
        if self.detected_title:
            headers.append(f"Title: {self.detected_title}")
        if self.channel:
            headers.append(f"Channel: {self.channel}")
        if self.url:
            headers.append(f"URL: {self.url}")
        if headers:
            return "\n".join(headers) + "\n\n" + self.cleaned_text + "\n"
        return self.cleaned_text + "\n"


def _looks_binary(raw: bytes) -> bool:
    if b"\x00" in raw:
        return True
    sample = raw[:8192]
    if not sample:
        return False
    control_count = sum(1 for b in sample if b < 32 and b not in (9, 10, 13))
    return (control_count / len(sample)) > 0.10


def _decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _extract_leading_headers(
    lines: list[str],
) -> tuple[str | None, str | None, str | None, list[str]]:
    detected_title: str | None = None
    channel: str | None = None
    url: str | None = None

    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            idx += 1
            if detected_title or channel or url:
                break
            continue
        match = _HEADER_LINE_RE.match(stripped)
        if not match:
            break
        key = match.group(1).lower()
        val = match.group(2).strip()
        if key == "title" and not detected_title:
            detected_title = val
        elif key in ("channel", "author") and not channel:
            channel = val
        elif key in ("url", "link") and not url:
            url = val
        idx += 1

    return detected_title, channel, url, lines[idx:]


def _detect_format(path: Path, body_lines: list[str]) -> TranscriptFormat:
    suffix = path.suffix.lower()
    non_empty = [line.strip() for line in body_lines if line.strip()]
    if suffix == ".vtt" or (non_empty and non_empty[0].startswith("WEBVTT")):
        return "vtt"
    if suffix == ".srt" or any(_SRT_TIMING_RE.match(line) for line in non_empty[:40]):
        return "srt"

    ts_hits = sum(
        1
        for line in non_empty[:60]
        if _STANDALONE_TIMESTAMP_RE.match(line) or _INLINE_PREFIX_TIMESTAMP_RE.match(line)
    )
    if ts_hits >= 2:
        return "timestamped"
    return "plain"


def _dedupe_consecutive_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    last_non_empty: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result and result[-1] != "":
                result.append("")
            continue
        if stripped == last_non_empty:
            continue
        result.append(line.rstrip())
        last_non_empty = stripped
    return result


def _clean_vtt(lines: list[str]) -> str:
    cleaned: list[str] = []
    skip_header_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            skip_header_block = True
            continue
        if skip_header_block:
            if not stripped:
                skip_header_block = False
            elif stripped.startswith(("Kind:", "Language:")):
                continue
            else:
                skip_header_block = False
        if not stripped:
            cleaned.append("")
            continue
        if stripped.isdigit() or _VTT_TIMING_RE.match(stripped):
            continue
        text = _VTT_INLINE_TAG_RE.sub("", stripped)
        text = _HTML_TAG_RE.sub("", text).strip()
        if text:
            cleaned.append(text)
    deduped = _dedupe_consecutive_lines(cleaned)
    return _EXCESS_BLANK_LINES_RE.sub("\n\n", "\n".join(deduped)).strip()


def _clean_srt(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.isdigit() or _SRT_TIMING_RE.match(stripped):
            continue
        text = _HTML_TAG_RE.sub("", stripped).strip()
        if text:
            cleaned.append(text)
    deduped = _dedupe_consecutive_lines(cleaned)
    return _EXCESS_BLANK_LINES_RE.sub("\n\n", "\n".join(deduped)).strip()


def _clean_timestamped(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        if _STANDALONE_TIMESTAMP_RE.match(line):
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        match = _INLINE_PREFIX_TIMESTAMP_RE.match(line)
        if match:
            remainder = line[match.end() :].rstrip()
            if remainder:
                cleaned.append(remainder)
            continue
        cleaned.append(line.rstrip())
    deduped = _dedupe_consecutive_lines(cleaned)
    return _EXCESS_BLANK_LINES_RE.sub("\n\n", "\n".join(deduped)).strip()


def _clean_plain(lines: list[str]) -> str:
    text = "\n".join(line.rstrip() for line in lines)
    return _EXCESS_BLANK_LINES_RE.sub("\n\n", text).strip()


def parse_transcript(path: Path, *, fallback_title: str | None = None) -> TranscriptDocument:
    """Read, validate, hash, and normalize a YouTube transcript file."""
    if not path.is_file():
        raise TranscriptParseError(f"Transcript file does not exist: {path}")

    raw_bytes = path.read_bytes()
    if not raw_bytes:
        raise TranscriptParseError(f"Transcript file is empty: {path}")
    if _looks_binary(raw_bytes):
        raise TranscriptParseError(f"Transcript file appears to be binary: {path}")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    decoded = _decode_text(raw_bytes).replace("\r\n", "\n").replace("\r", "\n")
    lines = decoded.split("\n")

    detected_title, channel, url, body_lines = _extract_leading_headers(lines)
    detected_format = _detect_format(path, body_lines)

    if detected_format == "vtt":
        cleaned_text = _clean_vtt(body_lines)
    elif detected_format == "srt":
        cleaned_text = _clean_srt(body_lines)
    elif detected_format == "timestamped":
        cleaned_text = _clean_timestamped(body_lines)
    else:
        cleaned_text = _clean_plain(body_lines)

    if not cleaned_text.strip():
        raise TranscriptParseError(f"Transcript contains no readable text after normalization: {path}")

    resolved_fallback = fallback_title or extract_fallback_title(path.stem if path.suffix else path.name)
    if not resolved_fallback:
        resolved_fallback = path.stem or path.name

    return TranscriptDocument(
        source_path=path.resolve(),
        sha256=sha256,
        fallback_title=resolved_fallback,
        detected_title=detected_title,
        channel=channel,
        url=url,
        detected_format=detected_format,
        cleaned_text=cleaned_text,
        char_count=len(cleaned_text),
    )
