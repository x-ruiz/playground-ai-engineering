"""Tests for YouTube/web fetchers and compound ingest_url deduplication."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from obsidian_note_agent.config import AppConfig
from obsidian_note_agent.fetchers.web import fetch_web
from obsidian_note_agent.fetchers.youtube import FetchedSource, FetchError, fetch_youtube
from obsidian_note_agent.state import StateStore
from obsidian_note_agent.tools.ingest_tools import ingest_url_impl
from obsidian_note_agent.tools.vault_tools import ToolRuntimeContext


def test_fetch_youtube_combines_oembed_and_transcript() -> None:
    with (
        patch(
            "obsidian_note_agent.fetchers.youtube._fetch_oembed_metadata",
            return_value=("Protocol Buffers Crash Course", "Hussein Nasser"),
        ),
        patch(
            "obsidian_note_agent.fetchers.youtube._fetch_transcript_text",
            return_value="Protocol Buffers encode structured payloads using varints.",
        ),
    ):
        src = fetch_youtube("https://youtu.be/mUw27wG7uFA", max_chars=2000)
    assert src.canonical_url == "https://www.youtube.com/watch?v=mUw27wG7uFA"
    assert src.title == "Protocol Buffers Crash Course"
    assert src.channel == "Hussein Nasser"
    assert src.source_type == "youtube"
    assert src.truncated is False


def test_fetch_web_handles_blocked_403() -> None:
    fake_resp = SimpleNamespace(status_code=403, text="Forbidden")
    with (
        patch("obsidian_note_agent.fetchers.web.httpx.get", return_value=fake_resp),
        pytest.raises(FetchError, match="HTTP 403"),
    ):
        fetch_web("https://www.databricks.com/blog/ai-harness", source_type="article")


def test_ingest_url_compound_payload_and_dedup(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "AI Engineering").mkdir(parents=True)
    (vault / "AI Engineering" / "Modern AI Architecture.md").write_text(
        "---\ntags:\n  - ai-engineering/agents\n---\nArchitecture.\n",
        encoding="utf-8",
    )
    cfg = AppConfig.model_validate(
        {
            "vault": {"path": str(vault), "staging_dir": "staging"},
            "state": {"db_path": str(tmp_path / "state.db")},
        }
    )
    ctx = ToolRuntimeContext(config=cfg)

    fake_source = FetchedSource(
        canonical_url="https://www.databricks.com/blog/ai-harness",
        source_type="article",
        title="Modern AI Agent Harness Architecture",
        cleaned_text="Harnesses isolate tool execution and evals.",
        content_sha256="sha-article-1",
        author="Databricks Engineering Blog",
        published="2026-04-15",
        headings=("Harness Control Plane",),
        extraction_method="trafilatura",
    )

    with patch("obsidian_note_agent.tools.ingest_tools.fetch_web", return_value=fake_source):
        payload = ingest_url_impl(ctx, "https://www.databricks.com/blog/ai-harness?utm_source=x")

    assert payload["status"] == "ok"
    assert payload["provenance"]["source_type"] == "article"
    assert "ai-engineering/agents" in payload["vault_tags"]
    assert payload["likely_overlap_notes"][0]["title"] == "Modern AI Architecture"

    # Record completion -> subsequent ingest_url must short-circuit as duplicate
    with StateStore(cfg.state.db_path) as store:
        store.record_completed(
            canonical_url=fake_source.canonical_url,
            content_sha256=fake_source.content_sha256,
            source_type="article",
            note_action="update",
            target_note="[[Modern AI Architecture]]",
            source_title=fake_source.title,
            recommended_category="AI Engineering",
            note_title="Modern AI Architecture (Update)",
            output_note_path=vault / "staging" / "AI Engineering" / "Modern AI Architecture (Update).md",
            tags=["ai-engineering/agents/harness"],
        )

    dup = ingest_url_impl(ctx, "https://www.databricks.com/blog/ai-harness")
    assert dup["status"] == "duplicate"
