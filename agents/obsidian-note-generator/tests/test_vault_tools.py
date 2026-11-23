"""Tests for guarded vault read/stage tools and inline validate_note.py checks."""

from __future__ import annotations

from pathlib import Path

from obsidian_note_agent.config import AppConfig
from obsidian_note_agent.state import StateStore
from obsidian_note_agent.tools.vault_tools import (
    ToolRuntimeContext,
    read_vault_note_impl,
    stage_obsidian_note_impl,
)


def _make_ctx(tmp_path: Path, *, dry_run: bool = False) -> ToolRuntimeContext:
    vault = tmp_path / "vault"
    (vault / "AI Engineering").mkdir(parents=True)
    (vault / "AI Engineering" / "Modern AI Architecture.md").write_text(
        "---\ntags:\n  - ai-engineering/agents\n---\nCore layers.\n\n## Core Mechanics\nDetails.\n",
        encoding="utf-8",
    )
    cfg = AppConfig.model_validate(
        {
            "vault": {"path": str(vault), "staging_dir": "staging"},
            "state": {"db_path": str(tmp_path / "state.db")},
        }
    )
    return ToolRuntimeContext(config=cfg, dry_run=dry_run)


def test_read_vault_note_reads_inside_vault_and_blocks_traversal(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ok = read_vault_note_impl(ctx, "AI Engineering/Modern AI Architecture.md")
    assert ok["status"] == "ok"
    assert "Core Mechanics" in ok["headings"]

    blocked = read_vault_note_impl(ctx, "../../etc/passwd")
    assert blocked["status"] == "error"


def test_stage_obsidian_note_validates_create_and_update_drafts(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, dry_run=False)

    # 1. Invalid note (verbose -and- tag) must fail validation and be unlinked
    bad = stage_obsidian_note_impl(
        ctx,
        category="AI Engineering",
        note_title="Agent Harness",
        markdown_content=(
            "---\ntags:\n  - ai-engineering/agent-deployment-and-development\n"
            "source: \"AI Harness\"\nsource-type: article\ncreated: 2026-11-23\n---\n"
            "Deterministic harness.\n"
        ),
        source_type="article",
        note_action="create",
        content_sha256="sha-bad",
    )
    assert bad["status"] == "validation_failed"
    assert bad["validation_passed"] is False
    assert not (ctx.effective_output_dir / "AI Engineering" / "Agent Harness.md").exists()

    # 2. Valid update draft auto-appends (Update), passes validation, and records in SQLite
    good_update = stage_obsidian_note_impl(
        ctx,
        category="AI Engineering",
        note_title="Modern AI Architecture",
        markdown_content=(
            "---\nnote-action: update\ntarget-note: \"[[Modern AI Architecture]]\"\n"
            "target-path: \"AI Engineering/Modern AI Architecture.md\"\n"
            "tags:\n  - ai-engineering/agents/harness\n"
            "source: \"AI Harness\"\nsource-type: article\n"
            "url: \"https://www.databricks.com/blog/ai-harness\"\ncreated: 2026-11-23\n---\n"
            "> [!NOTE]\n> **Draft Modification for [[Modern AI Architecture]]**\n\n"
            "## Proposed New Section: `## Eval Gates`\nRun offline golden evals in CI.\n"
        ),
        source_type="article",
        note_action="update",
        target_note="[[Modern AI Architecture]]",
        source_url="https://www.databricks.com/blog/ai-harness",
        source_title="AI Harness",
        content_sha256="sha-good-update",
    )
    assert good_update["status"] == "staged"
    assert good_update["validation_passed"] is True
    assert good_update["note_title"] == "Modern AI Architecture (Update)"
    assert Path(good_update["output_path"]).is_file()

    with StateStore(ctx.config.state.db_path) as store:
        rec = store.get_completed_by_hash("sha-good-update")
        assert rec is not None
        assert rec.note_action == "update"


def test_stage_obsidian_note_blocks_path_traversal(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    res = stage_obsidian_note_impl(
        ctx,
        category="AI Engineering",
        note_title="../Escaped",
        markdown_content="test",
        source_type="article",
    )
    assert res["status"] == "validation_failed"
