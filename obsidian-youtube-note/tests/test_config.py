"""Tests for yt_to_obsidian.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from yt_to_obsidian.config import AppConfig, load_config, resolve_skill_dir


def test_default_config_loads_and_resolves_paths() -> None:
    config, found = load_config()
    assert found is None
    assert isinstance(config, AppConfig)
    assert config.watch.path.is_absolute()
    assert config.vault.path.is_absolute()
    assert config.staging_path == (config.vault.path / "staging").resolve()
    assert ".txt" in config.watch.allowed_extensions


def test_load_explicit_yaml_resolves_relative_paths(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
watch:
  path: "./downloads"
  allowed_extensions: ["TXT", ".vtt"]
  debounce_ms: 250
vault:
  path: "./vault"
  staging_dir: "custom-staging"
state:
  db_path: "./state/ledger.db"
  log_file: "./state/app.log"
  log_level: "debug"
post_process:
  action: "move"
  archive_dir: "./archive"
""",
        encoding="utf-8",
    )

    config, found = load_config(cfg_file)
    assert found == cfg_file.resolve()
    assert config.watch.path == (tmp_path / "downloads").resolve()
    assert config.watch.allowed_extensions == [".txt", ".vtt"]
    assert config.vault.path == (tmp_path / "vault").resolve()
    assert config.staging_path == (tmp_path / "vault" / "custom-staging").resolve()
    assert config.state.db_path == (tmp_path / "state" / "ledger.db").resolve()
    assert config.state.log_level == "DEBUG"
    assert config.post_process.action == "move"
    assert config.post_process.archive_dir == (tmp_path / "archive").resolve()


def test_load_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")


def test_resolve_skill_dir_finds_local_skill() -> None:
    config, _ = load_config()
    skill_dir = resolve_skill_dir(config)
    assert skill_dir is not None
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "resources" / "output_schema.json").is_file()
    assert (skill_dir / "scripts" / "validate_note.py").is_file()
