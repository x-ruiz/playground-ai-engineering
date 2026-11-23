"""Transcript filename matching and fallback title extraction."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ALLOWED_EXTENSIONS: tuple[str, ...] = (".txt", ".md", ".srt", ".vtt")

IGNORED_TEMP_SUFFIXES: frozenset[str] = frozenset(
    {
        ".crdownload",
        ".part",
        ".download",
        ".tmp",
        ".opdownload",
        ".swp",
        ".partial",
    }
)

_TRANSCRIPT_SUFFIX_RE = re.compile(r"_transcript$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MatchResult:
    path: Path
    fallback_title: str


def extract_fallback_title(stem: str) -> str:
    """Derive a clean human-readable topic title from a matched transcript stem."""
    without_suffix = _TRANSCRIPT_SUFFIX_RE.sub("", stem)
    spaced = without_suffix.replace("_", " ")
    cleaned = _WHITESPACE_RE.sub(" ", spaced).strip(" -_")
    return cleaned


def match_transcript_path(
    path: Path,
    *,
    allowed_extensions: Iterable[str] = DEFAULT_ALLOWED_EXTENSIONS,
) -> MatchResult | None:
    """Return MatchResult if `path` matches `*_transcript` (extensionless or allowed ext)."""
    name = path.name
    if not name or name.startswith("."):
        return None

    lower_suffix = path.suffix.lower()
    if lower_suffix in IGNORED_TEMP_SUFFIXES:
        return None

    normalized_exts = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_extensions
    }

    if lower_suffix == "":
        stem = name
    elif lower_suffix in normalized_exts:
        stem = path.stem
    else:
        return None

    if not _TRANSCRIPT_SUFFIX_RE.search(stem):
        return None

    fallback_title = extract_fallback_title(stem)
    if not fallback_title:
        return None

    return MatchResult(path=path, fallback_title=fallback_title)
