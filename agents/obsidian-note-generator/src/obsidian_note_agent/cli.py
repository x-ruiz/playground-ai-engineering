"""Thin CLI wrapper over the Google ADK obsidian_note_agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from obsidian_note_agent import __version__
from obsidian_note_agent.config import load_config, project_root, validate_runtime_environment
from obsidian_note_agent.runner import run_urls_async
from obsidian_note_agent.state import StateStore


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        output = asyncio.run(
            run_urls_async(
                args.urls,
                config_path=args.config,
                dry_run=args.dry_run,
                output_dir=args.output_dir,
                force=args.force,
                model=args.model,
            )
        )
    except Exception as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 1

    if output:
        print(output)
    return 0


def _cmd_validate_config(args: argparse.Namespace) -> int:
    try:
        config, found = load_config(args.config)
    except Exception as exc:
        print(f"[FAIL] Config error: {exc}", file=sys.stderr)
        return 1

    print(f"Config source:  {found if found else 'built-in defaults'}")
    print(f"Staging target: {config.staging_path}")
    print(f"Default model:  {config.agent.model}")
    fallbacks = ", ".join(config.agent.fallback_models) if config.agent.fallback_models else "(none)"
    print(f"Fallbacks:      {fallbacks}")
    retry = config.agent.retry
    print(
        f"Retry policy:   {retry.attempts} attempts, {retry.initial_delay}s..{retry.max_delay}s "
        f"(codes={retry.http_status_codes})"
    )
    checks = validate_runtime_environment(config)
    has_failure = False
    for check in checks:
        tag = check.status.upper()
        print(f"  [{tag:4s}] {check.name}: {check.detail}")
        if check.status == "fail":
            has_failure = True
    return 1 if has_failure else 0


def _cmd_history(args: argparse.Namespace) -> int:
    config, _ = load_config(args.config)
    with StateStore(config.state.db_path) as store:
        records = store.list_recent(limit=args.limit)
    if not records:
        print(f"No note runs recorded yet in {config.state.db_path}")
        return 0
    for rec in records:
        dest = rec.output_note_path or rec.error or "-"
        cat = rec.recommended_category or "-"
        print(
            f"#{rec.id:03d} | {rec.updated_at} | {rec.status:9s} | "
            f"{rec.source_type:13s} | {rec.note_action:6s} | {cat:20s} | {dest}"
        )
    return 0


def _resolve_mcp_command() -> str:
    venv_bin = project_root() / ".venv" / "bin" / "obsidian-note-mcp"
    if venv_bin.exists():
        return str(venv_bin.resolve())
    return str(Path(sys.executable).resolve().parent / "obsidian-note-mcp")


def _cmd_mcp_config(args: argparse.Namespace) -> int:
    cmd_path = _resolve_mcp_command()
    mcp_args: list[str] = []
    if args.config is not None:
        mcp_args.extend(["--config", str(args.config.expanduser().resolve())])

    client = args.client
    if client in ("agy", "claude-desktop", "cursor"):
        entry: dict[str, object] = {"command": cmd_path}
        if mcp_args:
            entry["args"] = mcp_args
        payload = {"mcpServers": {"obsidian-note-generator": entry}}
        target_hint = {
            "agy": "~/.gemini/config/mcp_config.json",
            "claude-desktop": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "cursor": "~/.cursor/mcp.json",
        }[client]
        print(f"# Add under {target_hint}:")
        print(json.dumps(payload, indent=2))
        return 0

    if client == "claude":
        extra = f" {' '.join(mcp_args)}" if mcp_args else ""
        print(f"claude mcp add obsidian-note-generator -- {cmd_path}{extra}")
        return 0

    if client == "codex":
        args_toml = json.dumps(mcp_args)
        print("# Add to ~/.codex/config.toml:")
        print("[mcp_servers.obsidian-note-generator]")
        print(f'command = "{cmd_path}"')
        if mcp_args:
            print(f"args = {args_toml}")
        return 0

    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-note",
        description="Google ADK agent CLI for generating staged Obsidian notes and Update Drafts from URLs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate staged note(s) or Update Draft(s) from one or more URLs.")
    p_gen.add_argument("urls", nargs="+", help="One or more YouTube, article, or documentation URLs.")
    p_gen.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_gen.add_argument("--dry-run", action="store_true", help="Write to preview dir without recording in SQLite.")
    p_gen.add_argument("--output-dir", type=Path, default=None, help="Override note staging/output directory.")
    p_gen.add_argument("--force", action="store_true", help="Reprocess URLs even if already recorded in SQLite.")
    p_gen.add_argument("--model", default=None, help="Override Gemini model (e.g. gemini-2.5-pro).")
    p_gen.set_defaults(func=_cmd_generate)

    p_val = sub.add_parser("validate-config", help="Validate config.yaml, vault path, skill assets, and Gemini auth.")
    p_val.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_val.set_defaults(func=_cmd_validate_config)

    p_hist = sub.add_parser("history", help="Display recent note generation runs from state.db.")
    p_hist.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_hist.add_argument("--limit", type=int, default=20, help="Number of recent entries to display.")
    p_hist.set_defaults(func=_cmd_history)

    p_mcp = sub.add_parser(
        "mcp-config",
        help="Print ready-to-paste MCP registration snippet for agy, Claude, Cursor, or Codex.",
    )
    p_mcp.add_argument(
        "--client",
        choices=("agy", "claude", "claude-desktop", "cursor", "codex"),
        default="agy",
        help="Target MCP client format (default: agy).",
    )
    p_mcp.add_argument("--config", type=Path, default=None, help="Optional explicit config.yaml path.")
    p_mcp.set_defaults(func=_cmd_mcp_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
