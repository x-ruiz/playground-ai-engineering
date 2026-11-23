"""Thin CLI wrapper over the Google ADK obsidian_note_agent."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from obsidian_note_agent import __version__
from obsidian_note_agent.agent import build_agent
from obsidian_note_agent.config import load_config, validate_runtime_environment
from obsidian_note_agent.state import StateStore


async def _run_urls_async(
    urls: list[str],
    *,
    config_path: Path | None,
    dry_run: bool,
    output_dir: Path | None,
    force: bool,
    model: str | None,
) -> str:
    config, _ = load_config(config_path)
    agent = build_agent(
        config,
        dry_run=dry_run,
        output_dir=output_dir,
        force=force,
        model_override=model,
    )
    runner = InMemoryRunner(agent=agent, app_name="obsidian_note_agent")
    session = await runner.session_service.create_session(
        app_name="obsidian_note_agent",
        user_id="cli-user",
    )

    url_lines = "\n".join(f"- {u}" for u in urls)
    force_clause = " Force regeneration even if already processed." if force else ""
    prompt = (
        f"Generate staged Obsidian note(s) or Update Draft(s) for the following URL(s):{force_clause}\n"
        f"{url_lines}"
    )

    final_chunks: list[str] = []
    async for event in runner.run_async(
        user_id="cli-user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    final_chunks.append(part.text)

    await runner.close()
    return "\n".join(final_chunks).strip()


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        output = asyncio.run(
            _run_urls_async(
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
