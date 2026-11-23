"""Tests for yt_to_obsidian.state."""

from __future__ import annotations

from pathlib import Path

from yt_to_obsidian.state import StateStore


def test_state_persists_dedup_across_restarts(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    sha = "a" * 64

    with StateStore(db_path) as store:
        assert not store.is_completed(sha)
        run_id = store.record_start(
            sha256=sha,
            source_path=tmp_path / "Demo_transcript",
            fallback_title="Demo",
        )
        assert not store.is_completed(sha)
        store.record_completed(
            run_id,
            category="Software Engineering",
            note_title="Demo",
            output_note_path=tmp_path / "staging" / "Software Engineering" / "Demo.md",
            tags=["software-engineering/frameworks"],
            duration_seconds=12.4,
        )
        assert store.is_completed(sha)

    # Reopen from disk to confirm durability
    with StateStore(db_path) as reopened:
        rec = reopened.get_completed(sha)
        assert rec is not None
        assert rec.status == "completed"
        assert rec.recommended_category == "Software Engineering"
        assert rec.tags == ["software-engineering/frameworks"]
        assert rec.duration_seconds == 12.4


def test_failed_run_does_not_block_future_retry(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    sha = "b" * 64

    with StateStore(db_path) as store:
        run_id = store.record_start(
            sha256=sha,
            source_path=tmp_path / "Retry_transcript",
            fallback_title="Retry",
        )
        store.record_failed(run_id, error="agy timeout", duration_seconds=30.0)
        assert not store.is_completed(sha)

        recent = store.list_recent(limit=5)
        assert len(recent) == 1
        assert recent[0].status == "failed"
        assert recent[0].error == "agy timeout"
