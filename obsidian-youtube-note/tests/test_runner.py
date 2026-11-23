"""Tests for yt_to_obsidian.runner and yt_to_obsidian.queue_worker."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from yt_to_obsidian.config import AppConfig
from yt_to_obsidian.parser import parse_transcript
from yt_to_obsidian.queue_worker import TranscriptProcessor
from yt_to_obsidian.runner import AgyCliRunner, RunnerError, RunRequest, scan_vault_inventory
from yt_to_obsidian.state import StateStore

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "Protocol_Buffers_Crash_Course_transcript"


def _make_config(tmp_path: Path, *, max_retries: int = 1) -> AppConfig:
    vault_dir = tmp_path / "vault"
    (vault_dir / "Software Engineering").mkdir(parents=True)
    (vault_dir / "README.md").write_text("# Mastery Framework\n", encoding="utf-8")
    (vault_dir / "Software Engineering" / "Builder Pattern.md").write_text(
        "---\ntags:\n  - software-engineering/design-patterns\n---\nBuilder.\n",
        encoding="utf-8",
    )
    (vault_dir / "Software Engineering" / "Inversion of Control.md").write_text(
        "---\ntags:\n  - software-engineering/design-principles\naliases:\n  - IoC\n---\nIoC.\n",
        encoding="utf-8",
    )
    (vault_dir / "misc").mkdir()
    (vault_dir / "misc" / "Ignored.md").write_text("ignore me", encoding="utf-8")

    fake_agy = tmp_path / "agy"
    fake_agy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_agy.chmod(0o755)

    return AppConfig.model_validate(
        {
            "watch": {"path": str(tmp_path / "downloads")},
            "vault": {"path": str(vault_dir), "staging_dir": "staging"},
            "state": {
                "db_path": str(tmp_path / "state.db"),
                "log_file": str(tmp_path / "app.log"),
            },
            "runner": {
                "agy_binary": str(fake_agy),
                "timeout_seconds": 60,
                "max_retries": max_retries,
                "strict_validation_warnings": True,
            },
            "notifications": {"enabled": False},
        }
    )


def _write_valid_note(note_path: Path) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        """---
tags:
  - software-engineering/frameworks/protobuf
aliases:
  - Protobuf
source: "Protocol Buffers Crash Course"
source-type: youtube
created: 2026-11-23
---
Schema-first binary serialization format using `.proto` contracts and [[Builder Pattern]] codegen.

## Wire Format
Encodes compact varints and length-delimited fields.
""",
        encoding="utf-8",
    )


def test_scan_vault_inventory_excludes_misc_and_extracts_aliases(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    inventory = scan_vault_inventory(config.vault.path)
    assert "Builder Pattern" in inventory
    assert "Inversion of Control (aliases: IoC)" in inventory
    assert all("Ignored" not in item for item in inventory)
    assert all("README" not in item for item in inventory)


def test_runner_constructs_zero_shell_command_and_validates_note(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    output_dir = tmp_path / "preview"
    note_path = output_dir / "Software Engineering" / "Protocol Buffers.md"
    doc = parse_transcript(FIXTURE_PATH)

    captured_cmd: list[str] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_cmd.extend(cmd)
        _write_valid_note(note_path)
        envelope = {
            "status": "SUCCESS",
            "structured_output": {
                "status": "created",
                "recommended_category": "Software Engineering",
                "note_title": "Protocol Buffers",
                "output_path": str(note_path),
                "tags": ["software-engineering/frameworks/protobuf"],
                "aliases": ["Protobuf"],
                "existing_wikilinks": ["Builder Pattern"],
                "overlapping_notes": [],
                "validation_passed": True,
                "summary": "Created Protocol Buffers note.",
            },
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(envelope), stderr="")

    runner = AgyCliRunner(config)
    with patch("yt_to_obsidian.runner.subprocess.run", side_effect=fake_run):
        result = runner.run(RunRequest(transcript=doc, output_dir=output_dir, vault_path=config.vault.path, dry_run=True))

    assert result.status == "created"
    assert result.validation_passed is True
    assert result.output_path == note_path.resolve()
    assert "--mode" in captured_cmd and "accept-edits" in captured_cmd
    assert "--json-schema" in captured_cmd
    assert "--dangerously-skip-permissions" not in captured_cmd
    prompt_arg = captured_cmd[captured_cmd.index("-p") + 1]
    assert "Builder Pattern" in prompt_arg
    assert "Inversion of Control (aliases: IoC)" in prompt_arg


def test_runner_retries_once_on_validation_failure_then_succeeds(tmp_path: Path) -> None:
    config = _make_config(tmp_path, max_retries=1)
    output_dir = tmp_path / "preview"
    note_path = output_dir / "Software Engineering" / "Protocol Buffers.md"
    doc = parse_transcript(FIXTURE_PATH)
    call_count = 0

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        note_path.parent.mkdir(parents=True, exist_ok=True)
        if call_count == 1:
            # Invalid note: flat tag + recap phrasing
            note_path.write_text(
                "---\ntags:\n  - software-engineering\nsource: test\nsource-type: youtube\ncreated: 2026-11-23\n---\nIn this video we learn protobuf.\n",
                encoding="utf-8",
            )
        else:
            prompt_arg = cmd[cmd.index("-p") + 1]
            assert "PREVIOUS ATTEMPT FAILED VALIDATION" in prompt_arg
            _write_valid_note(note_path)

        envelope = {
            "status": "SUCCESS",
            "structured_output": {
                "status": "created",
                "recommended_category": "Software Engineering",
                "note_title": "Protocol Buffers",
                "output_path": str(note_path),
                "tags": ["software-engineering/frameworks/protobuf"],
                "existing_wikilinks": [],
                "overlapping_notes": [],
                "validation_passed": True,
                "summary": "Created note.",
            },
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(envelope), stderr="")

    runner = AgyCliRunner(config)
    with patch("yt_to_obsidian.runner.subprocess.run", side_effect=fake_run):
        result = runner.run(RunRequest(transcript=doc, output_dir=output_dir, vault_path=config.vault.path, dry_run=True))

    assert call_count == 2
    assert result.attempts == 2
    assert result.validation_passed is True


def test_runner_blocks_output_path_outside_output_dir(tmp_path: Path) -> None:
    config = _make_config(tmp_path, max_retries=0)
    output_dir = tmp_path / "preview"
    escaped_path = config.vault.path / "Software Engineering" / "Escaped.md"
    doc = parse_transcript(FIXTURE_PATH)

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        _write_valid_note(escaped_path)
        envelope = {
            "status": "SUCCESS",
            "structured_output": {
                "status": "created",
                "recommended_category": "Software Engineering",
                "note_title": "Escaped",
                "output_path": str(escaped_path),
                "tags": ["software-engineering/frameworks/protobuf"],
                "existing_wikilinks": [],
                "overlapping_notes": [],
                "validation_passed": True,
                "summary": "Escaped.",
            },
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(envelope), stderr="")

    runner = AgyCliRunner(config)
    with (
        patch("yt_to_obsidian.runner.subprocess.run", side_effect=fake_run),
        pytest.raises(RunnerError, match="outside configured output_dir"),
    ):
        runner.run(RunRequest(transcript=doc, output_dir=output_dir, vault_path=config.vault.path, dry_run=True))


def test_processor_deduplicates_and_respects_dry_run(tmp_path: Path) -> None:
    config = _make_config(tmp_path, max_retries=0)
    transcript = tmp_path / "Demo_transcript"
    transcript.write_text("Title: Demo\n\n00:00\nDistributed consensus basics.\n", encoding="utf-8")

    class StubRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, request: RunRequest):
            self.calls += 1
            note_path = request.output_dir / "Software Engineering" / "Demo.md"
            _write_valid_note(note_path)
            from yt_to_obsidian.runner import RunResult

            return RunResult(
                status="created",
                recommended_category="Software Engineering",
                note_title="Demo",
                output_path=note_path,
                tags=["software-engineering/frameworks/protobuf"],
                validation_passed=True,
                summary="ok",
            )

    stub = StubRunner()
    with StateStore(config.state.db_path) as store:
        processor = TranscriptProcessor(config=config, state_store=store, runner=stub)

        # Dry run must not record into state DB
        dry_outcome = processor.process_file(transcript, dry_run=True, output_dir=tmp_path / "dry")
        assert dry_outcome.status == "completed"
        assert store.list_recent() == []

        # Real run records completion
        first = processor.process_file(transcript, dry_run=False)
        assert first.status == "completed"
        assert stub.calls == 2

        # Second identical run is skipped by SHA-256 dedup
        second = processor.process_file(transcript, dry_run=False)
        assert second.status == "skipped"
        assert stub.calls == 2

        # Force bypasses dedup
        forced = processor.process_file(transcript, dry_run=False, force=True)
        assert forced.status == "completed"
        assert stub.calls == 3
