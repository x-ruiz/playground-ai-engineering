"""Tests for the cross-client FastMCP wrapper (obsidian-note-mcp) and mcp-config CLI."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from obsidian_note_agent.cli import main as cli_main
from obsidian_note_agent.mcp_server import create_mcp_server
from obsidian_note_agent.state import StateStore


def _write_temp_config(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
vault:
  path: "{vault}"
  staging_dir: "staging"
state:
  db_path: "{tmp_path / 'state.db'}"
""",
        encoding="utf-8",
    )
    return cfg


def test_mcp_server_registers_exact_three_tools(tmp_path: Path) -> None:
    cfg = _write_temp_config(tmp_path)
    server = create_mcp_server(config_path=cfg)
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "generate_note_from_url",
        "generate_note_from_text",
        "list_recent_notes",
    }


def test_mcp_list_recent_notes_reads_sqlite_without_llm(tmp_path: Path) -> None:
    cfg = _write_temp_config(tmp_path)
    with StateStore(tmp_path / "state.db") as store:
        store.record_completed(
            canonical_url="https://www.databricks.com/blog/ai-harness",
            content_sha256="sha-1",
            source_type="article",
            note_action="create",
            target_note=None,
            source_title="AI Agent Harnesses",
            recommended_category="AI Engineering",
            note_title="AI Agent Harnesses",
            output_note_path=tmp_path / "vault" / "staging" / "AI Engineering" / "AI Agent Harnesses.md",
            tags=["ai-engineering/agents/harness"],
        )

    server = create_mcp_server(config_path=cfg)
    _, structured = asyncio.run(server.call_tool("list_recent_notes", {"limit": 5}))
    assert structured["status"] == "ok"
    assert structured["count"] == 1
    assert structured["runs"][0]["note_title"] == "AI Agent Harnesses"


def test_mcp_generate_tools_delegate_to_adk_runner_and_check_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _write_temp_config(tmp_path)
    server = create_mcp_server(config_path=cfg)

    # Missing Gemini auth returns clean diagnostic instead of crashing
    monkeypatch.setattr("obsidian_note_agent.mcp_server.has_gemini_auth", lambda: False)
    _, err_res = asyncio.run(
        server.call_tool(
            "generate_note_from_url",
            {"urls": ["https://www.databricks.com/blog/ai-harness"]},
        )
    )
    assert err_res["status"] == "error"
    assert "Gemini authentication" in err_res["error"]

    # With auth present, delegates cleanly to runner helpers
    monkeypatch.setattr("obsidian_note_agent.mcp_server.has_gemini_auth", lambda: True)
    with patch(
        "obsidian_note_agent.mcp_server.run_urls_async",
        new=AsyncMock(return_value="Staged AI Agent Harnesses.md"),
    ) as mock_urls:
        _, url_res = asyncio.run(
            server.call_tool(
                "generate_note_from_url",
                {
                    "urls": ["https://www.databricks.com/blog/ai-harness"],
                    "dry_run": True,
                    "force": True,
                },
            )
        )
    assert url_res["status"] == "ok"
    assert url_res["summary"] == "Staged AI Agent Harnesses.md"
    assert mock_urls.await_count == 1

    with patch(
        "obsidian_note_agent.mcp_server.run_pasted_text_async",
        new=AsyncMock(return_value="Staged Paywalled Article.md"),
    ) as mock_text:
        _, text_res = asyncio.run(
            server.call_tool(
                "generate_note_from_text",
                {
                    "text": "Distributed consensus details.",
                    "title": "Raft Notes",
                    "source_type": "article",
                },
            )
        )
    assert text_res["status"] == "ok"
    assert text_res["summary"] == "Staged Paywalled Article.md"
    assert mock_text.await_count == 1


def test_cli_mcp_config_prints_valid_snippets(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["mcp-config", "--client", "agy"])
    assert rc == 0
    out = capsys.readouterr().out
    json_part = "\n".join(line for line in out.splitlines() if not line.startswith("#"))
    parsed = json.loads(json_part)
    assert "obsidian-note-generator" in parsed["mcpServers"]
    assert parsed["mcpServers"]["obsidian-note-generator"]["command"].endswith("obsidian-note-mcp")

    for client in ("claude", "claude-desktop", "cursor", "codex"):
        assert cli_main(["mcp-config", "--client", client]) == 0
        assert "obsidian-note-mcp" in capsys.readouterr().out


def test_stdio_handshake_from_tmp_cwd_has_zero_stray_stdout() -> None:
    """Spawn the real MCP stdio server from cwd=/tmp and verify pure JSON-RPC frames."""
    mcp_bin = Path(sys.executable).resolve().parent / "obsidian-note-mcp"
    cmd = [str(mcp_bin)] if mcp_bin.exists() else [sys.executable, "-m", "obsidian_note_agent.mcp_server"]

    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest-client", "version": "1.0"},
        },
    }
    initialized_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    stdin_payload = (
        json.dumps(init_req) + "\n" + json.dumps(initialized_notif) + "\n" + json.dumps(list_req) + "\n"
    )

    proc = subprocess.run(
        cmd,
        input=stdin_payload,
        capture_output=True,
        text=True,
        cwd="/tmp",
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"

    stdout_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(stdout_lines) >= 2, f"Unexpected stdout: {proc.stdout!r}, stderr: {proc.stderr!r}"

    # Every single stdout line MUST be valid JSON-RPC (no stray prints or warnings)
    messages = [json.loads(line) for line in stdout_lines]
    by_id = {m.get("id"): m for m in messages if "id" in m}
    assert 1 in by_id and "result" in by_id[1]
    assert 2 in by_id and "result" in by_id[2]

    names = {tool["name"] for tool in by_id[2]["result"]["tools"]}
    assert names == {
        "generate_note_from_url",
        "generate_note_from_text",
        "list_recent_notes",
    }
