"""URL canonicalization and deterministic source-type classification."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

SourceType = Literal["youtube", "article", "documentation"]

_YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
)
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = frozenset(
    {"si", "feature", "ref", "fbclid", "gclid", "pp", "mc_cid", "mc_eid"}
)
_DOC_HOST_PREFIXES = ("docs.", "doc.", "developer.", "developers.", "learn.", "api.", "reference.")
_DOC_EXACT_HOSTS = frozenset(
    {
        "kubernetes.io",
        "spark.apache.org",
        "iceberg.apache.org",
        "docs.python.org",
        "docs.spring.io",
        "react.dev",
        "datatracker.ietf.org",
        "www.rfc-editor.org",
    }
)
_DOC_PATH_RE = re.compile(
    r"/(docs|documentation|reference|references|api|manual|manuals|guide|guides|products|spec|specs|rfc)(/|$)",
    re.IGNORECASE,
)
_ARTICLE_HOSTS = frozenset(
    {
        "medium.com",
        "towardsdatascience.com",
        "dev.to",
        "martinfowler.com",
        "netflixtechblog.com",
        "engineering.fb.com",
        "stripe.com",
        "arxiv.org",
    }
)
_ARTICLE_PATH_RE = re.compile(
    r"/(blog|blogs|engineering|posts|post|articles|article|essays|newsletter|p)(/|$)",
    re.IGNORECASE,
)
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_youtube_video_id(url: str) -> str | None:
    """Extract an 11-character YouTube video ID from standard watch, share, live, or shorts URLs."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    if parsed.path == "/watch":
        params = dict(parse_qsl(parsed.query))
        candidate = params.get("v", "")
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
        candidate = parts[1]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    return None


def canonicalize_url(url: str) -> str:
    """Normalize a URL for reliable deduplication (strips tracking params and YouTube aliases)."""
    raw = url.strip()
    video_id = extract_youtube_video_id(raw)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
        and not any(k.lower().startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)
    ]
    query = urlencode(sorted(kept_params))
    return urlunparse((scheme, netloc, path, "", query, ""))


def classify_url(url: str) -> SourceType:
    """Deterministically classify a URL as youtube, documentation, or article."""
    if extract_youtube_video_id(url) is not None:
        return "youtube"

    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if host in _YOUTUBE_HOSTS:
        return "youtube"

    # Explicit article/blog path wins over vendor domain (e.g., databricks.com/blog/ai-harness)
    if _ARTICLE_PATH_RE.search(path) or host.endswith(".substack.com") or host in _ARTICLE_HOSTS:
        return "article"

    if (
        host.startswith(_DOC_HOST_PREFIXES)
        or host in _DOC_EXACT_HOSTS
        or _DOC_PATH_RE.search(path)
    ):
        return "documentation"

    return "article"
