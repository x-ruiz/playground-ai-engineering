"""Tests for obsidian_note_agent.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_note_agent.config import AppConfig, load_config, resolve_skill_dir


def test_default_config_loads_and_resolves_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("obsidian_note_agent.config.discover_config_file", lambda _p=None: None)
    config, found = load_config()
    assert found is None
    assert isinstance(config, AppConfig)
    assert config.vault.path.is_absolute()
    assert config.staging_path == (config.vault.path / "staging").resolve()
    assert config.agent.model == "gemini-2.5-flash"
    assert config.ingestion.max_source_chars == 45_000


def test_load_explicit_yaml_resolves_relative_paths(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
vault:
  path: "./vault"
  staging_dir: "custom-staging"
  inventory_rank_threshold: 100
  inventory_top_k: 25
state:
  db_path: "./state/ledger.db"
  log_level: "debug"
agent:
  model: "gemini-2.5-pro"
  fallback_models: ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
  retry:
    attempts: 6
    initial_delay: 1.0
    max_delay: 20.0
    http_status_codes: [429, 503]
  max_validation_retries: 3
ingestion:
  max_source_chars: 30000
  enable_gemini_video_fallback: true
""",
        encoding="utf-8",
    )

    config, found = load_config(cfg_file)
    assert found == cfg_file.resolve()
    assert config.vault.path == (tmp_path / "vault").resolve()
    assert config.staging_path == (tmp_path / "vault" / "custom-staging").resolve()
    assert config.vault.inventory_rank_threshold == 100
    assert config.vault.inventory_top_k == 25
    assert config.state.db_path == (tmp_path / "state" / "ledger.db").resolve()
    assert config.state.log_level == "DEBUG"
    assert config.agent.model == "gemini-2.5-pro"
    assert config.agent.fallback_models == ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    assert config.agent.retry.attempts == 6
    assert config.agent.retry.initial_delay == 1.0
    assert config.agent.retry.max_delay == 20.0
    assert config.agent.retry.http_status_codes == [429, 503]
    assert config.ingestion.max_source_chars == 30_000
    assert config.ingestion.enable_gemini_video_fallback is True


def test_load_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")


def test_resolve_skill_dir_finds_unified_skill() -> None:
    skill_dir = resolve_skill_dir()
    assert skill_dir is not None
    assert skill_dir.name == "obsidian-note-generator"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "references" / "vault_conventions.md").is_file()
    assert (skill_dir / "references" / "exemplars.md").is_file()
    assert (skill_dir / "scripts" / "validate_note.py").is_file()
