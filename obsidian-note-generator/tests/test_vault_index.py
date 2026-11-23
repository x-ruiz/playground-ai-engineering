"""Tests for vault + staging indexing, live tag tree, and overlap detection."""

from __future__ import annotations

from pathlib import Path

from obsidian_note_agent.tools.vault_index import scan_vault_state


def _build_sample_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "obsidian-notes"
    (vault / "Software Engineering").mkdir(parents=True)
    (vault / "staging" / "AI Engineering").mkdir(parents=True)
    (vault / "misc").mkdir(parents=True)

    (vault / "README.md").write_text("# Mastery Framework\n", encoding="utf-8")
    (vault / "Software Engineering" / "Software Engineering.md").write_text(
        "---\ncategory: Software Engineering\ntags:\n  - software-engineering\n---\nHub.\n",
        encoding="utf-8",
    )
    (vault / "Software Engineering" / "Inversion of Control.md").write_text(
        "---\ntags:\n  - software-engineering/principles\naliases:\n  - IoC\n---\nIoC.\n",
        encoding="utf-8",
    )
    (vault / "staging" / "AI Engineering" / "Modern AI Architecture.md").write_text(
        "---\ntags:\n  - ai-engineering/agents\naliases:\n  - AI Agent Architecture\n---\nAgents.\n",
        encoding="utf-8",
    )
    (vault / "staging" / "AI Engineering" / "Modern AI Architecture (Update).md").write_text(
        "---\nnote-action: update\ntags:\n  - ai-engineering/agents/harness\n---\nDraft.\n",
        encoding="utf-8",
    )
    (vault / "misc" / "Ignored.md").write_text("ignore", encoding="utf-8")
    return vault


def test_scan_vault_state_collects_prod_staged_and_live_tags(tmp_path: Path) -> None:
    vault = _build_sample_vault(tmp_path)
    snapshot = scan_vault_state(vault)

    titles = {n.title for n in snapshot.notes}
    assert "Inversion of Control" in titles
    assert "Modern AI Architecture" in titles
    # Hub, README, misc, and existing (Update) draft must be excluded
    assert "Software Engineering" not in titles
    assert "README" not in titles
    assert "Ignored" not in titles
    assert "Modern AI Architecture (Update)" not in titles

    assert "software-engineering/principles" in snapshot.live_tags
    assert "ai-engineering/agents" in snapshot.live_tags
    assert "software-engineering" not in snapshot.live_tags

    inv = snapshot.format_inventory()
    assert any("Inversion of Control (aliases: IoC)" in line for line in inv)
    assert any("Modern AI Architecture [staged]" in line for line in inv)


def test_find_likely_overlaps_matches_staged_and_prod_notes(tmp_path: Path) -> None:
    vault = _build_sample_vault(tmp_path)
    snapshot = scan_vault_state(vault)

    overlaps = snapshot.find_likely_overlaps(
        title="Production AI Agent Architecture and Harnesses",
        headings=["Agent Loop", "Guardrails"],
    )
    assert overlaps
    assert overlaps[0].title == "Modern AI Architecture"
    assert overlaps[0].location == "staging"


def test_inventory_top_k_ranking_triggers_above_threshold(tmp_path: Path) -> None:
    vault = _build_sample_vault(tmp_path)
    for i in range(15):
        (vault / "Software Engineering" / f"Topic {i}.md").write_text(
            "---\ntags:\n  - software-engineering/patterns\n---\nBody.\n",
            encoding="utf-8",
        )
    snapshot = scan_vault_state(vault)
    ranked = snapshot.format_inventory(
        query_text="Inversion of Control IoC",
        rank_threshold=10,
        top_k=5,
    )
    assert len(ranked) == 5
    assert ranked[0].startswith("Inversion of Control")
