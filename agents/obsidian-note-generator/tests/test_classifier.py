"""Tests for URL canonicalization and source-type classification."""

from __future__ import annotations

from obsidian_note_agent.fetchers.classifier import (
    canonicalize_url,
    classify_url,
    extract_youtube_video_id,
)


def test_youtube_canonicalization_and_classification() -> None:
    assert extract_youtube_video_id("https://youtu.be/mUw27wG7uFA?si=abc") == "mUw27wG7uFA"
    assert (
        canonicalize_url("https://youtu.be/mUw27wG7uFA?si=tracking&t=12")
        == "https://www.youtube.com/watch?v=mUw27wG7uFA"
    )
    assert (
        canonicalize_url("https://www.youtube.com/shorts/X4FVEEegCbk?feature=share")
        == "https://www.youtube.com/watch?v=X4FVEEegCbk"
    )
    assert classify_url("https://www.youtube.com/watch?v=mUw27wG7uFA") == "youtube"


def test_article_and_documentation_classification() -> None:
    assert classify_url("https://www.databricks.com/blog/ai-harness") == "article"
    assert classify_url("https://netflixtechblog.com/some-post") == "article"
    assert classify_url("https://newsletter.pragmaticengineer.com/p/distributed-locks") == "article"

    assert (
        classify_url("https://cloud.google.com/products/managed-service-for-apache-spark")
        == "documentation"
    )
    assert classify_url("https://docs.spring.io/spring-boot/reference/index.html") == "documentation"
    assert classify_url("https://kubernetes.io/docs/concepts/workloads/") == "documentation"


def test_canonicalize_web_url_strips_tracking_params() -> None:
    assert (
        canonicalize_url("https://www.databricks.com/blog/ai-harness/?utm_source=x&ref=hn&b=2&a=1")
        == "https://www.databricks.com/blog/ai-harness?a=1&b=2"
    )
