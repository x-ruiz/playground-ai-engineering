"""Tests verifying Google ADK root_agent and SkillToolset initialization."""

from __future__ import annotations

from pathlib import Path

from google.adk.tools.skill_toolset import SkillToolset

from obsidian_note_agent import root_agent
from obsidian_note_agent.agent import build_agent
from obsidian_note_agent.config import AppConfig


def test_root_agent_loads_skill_toolset_and_tools(tmp_path: Path) -> None:
    cfg = AppConfig.model_validate(
        {
            "vault": {"path": str(tmp_path / "vault")},
            "state": {"db_path": str(tmp_path / "state.db")},
            "agent": {"model": "gemini-2.5-flash"},
        }
    )
    agent = build_agent(cfg, dry_run=True, output_dir=tmp_path / "preview")

    assert agent.name == "obsidian_note_agent"
    assert agent.model == "gemini-2.5-flash"
    assert root_agent.name == "obsidian_note_agent"

    toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
    assert len(toolsets) == 1

    callable_names = {getattr(t, "__name__", "") for t in agent.tools if callable(t)}
    assert {
        "ingest_url",
        "ingest_pasted_text",
        "read_vault_note",
        "stage_obsidian_note",
        "list_recent_notes",
    }.issubset(callable_names)
