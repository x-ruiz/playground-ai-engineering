"""Tests for obsidian_note_agent.state SQLite WAL ledger."""

from __future__ import annotations

from pathlib import Path

from obsidian_note_agent.state import StateStore


def test_state_store_dedup_by_url_and_hash(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    out_note = tmp_path / "staging" / "AI Engineering" / "Modern AI Architecture (Update).md"

    with StateStore(db_path) as store:
        assert store.get_completed_by_url("https://www.databricks.com/blog/ai-harness") is None
        run_id = store.record_completed(
            canonical_url="https://www.databricks.com/blog/ai-harness",
            content_sha256="abc123",
            source_type="article",
            note_action="update",
            target_note="[[Modern AI Architecture]]",
            source_title="Building Production AI Agent Harnesses",
            recommended_category="AI Engineering",
            note_title="Modern AI Architecture (Update)",
            output_note_path=out_note,
            tags=["ai-engineering/agents/harness"],
        )
        assert run_id > 0

        by_url = store.get_completed_by_url("https://www.databricks.com/blog/ai-harness")
        assert by_url is not None
        assert by_url.note_action == "update"
        assert by_url.target_note == "[[Modern AI Architecture]]"
        assert by_url.tags == ["ai-engineering/agents/harness"]

        by_hash = store.get_completed_by_hash("abc123")
        assert by_hash is not None
        assert by_hash.id == run_id

        recent = store.list_recent(limit=5)
        assert len(recent) == 1
        assert recent[0].output_note_path == str(out_note)
