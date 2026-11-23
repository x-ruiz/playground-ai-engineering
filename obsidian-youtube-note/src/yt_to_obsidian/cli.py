"""Command-line interface for yt-to-obsidian."""

from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
import threading
from pathlib import Path

from yt_to_obsidian import __version__
from yt_to_obsidian.config import (
    load_config,
    repo_root,
    skill_project_root,
    validate_runtime_environment,
)
from yt_to_obsidian.logging_setup import setup_logging
from yt_to_obsidian.queue_worker import QueueWorker, TranscriptProcessor
from yt_to_obsidian.runner import AgyCliRunner
from yt_to_obsidian.state import StateStore
from yt_to_obsidian.watcher import TranscriptWatcher

logger = logging.getLogger("yt_to_obsidian.cli")


def _cmd_validate_config(args: argparse.Namespace) -> int:
    try:
        config, found = load_config(args.config)
    except Exception as exc:
        print(f"[FAIL] Config error: {exc}", file=sys.stderr)
        return 1

    print(f"Config source: {found if found else 'built-in defaults'}")
    print(f"Staging target: {config.staging_path}")
    checks = validate_runtime_environment(config)
    has_failure = False
    for check in checks:
        tag = check.status.upper()
        print(f"  [{tag:4s}] {check.name}: {check.detail}")
        if check.status == "fail":
            has_failure = True
    return 1 if has_failure else 0


def _cmd_install_skill(args: argparse.Namespace) -> int:
    installer = repo_root() / "scripts" / "install_skill.py"
    if installer.is_file():
        cmd = [sys.executable, str(installer), skill_project_root().name]
        if args.check:
            cmd.append("--check")
        elif args.uninstall:
            cmd.append("--uninstall")
        if args.force:
            cmd.append("--force")
        if args.target_dir:
            cmd.extend(["--target-dir", str(args.target_dir)])
        proc = subprocess.run(cmd, check=False)
        return proc.returncode

    # Standalone fallback if installed outside the monorepo
    source = skill_project_root()
    target_dir = (args.target_dir or (Path.home() / ".gemini" / "config" / "skills")).expanduser()
    target = target_dir / source.name
    if args.check:
        if target.is_symlink() and target.resolve() == source.resolve():
            print(f"[OK] {target} -> {source.resolve()}")
            return 0
        print(f"[FAIL] Skill symlink not installed at {target}", file=sys.stderr)
        return 1
    if args.uninstall:
        if target.is_symlink():
            target.unlink()
            print(f"[REMOVED] {target}")
            return 0
        print(f"[OK] Not installed: {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        if target.exists() and target.resolve() == source.resolve():
            print(f"[OK] Already installed: {target} -> {source.resolve()}")
            return 0
        if not args.force:
            print("[ERROR] Symlink points elsewhere; pass --force.", file=sys.stderr)
            return 1
        target.unlink()
    target.symlink_to(source.resolve(), target_is_directory=True)
    print(f"[INSTALLED] {target} -> {source.resolve()}")
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    config, _ = load_config(args.config)
    with StateStore(config.state.db_path) as store:
        records = store.list_recent(limit=args.limit)
    if not records:
        print(f"No transcript runs recorded yet in {config.state.db_path}")
        return 0
    for rec in records:
        dest = rec.output_note_path or rec.error or "-"
        cat = rec.recommended_category or "-"
        print(f"#{rec.id:03d} | {rec.updated_at} | {rec.status:10s} | {cat:20s} | {rec.fallback_title} -> {dest}")
    return 0


def _cmd_process(args: argparse.Namespace) -> int:
    config, found = load_config(args.config)
    log_level = args.log_level or config.state.log_level
    setup_logging(log_file=None if args.dry_run else config.state.log_file, level=log_level)
    logger.info("Loaded config from %s", found if found else "built-in defaults")

    with StateStore(config.state.db_path) as store:
        runner = AgyCliRunner(config)
        processor = TranscriptProcessor(config=config, state_store=store, runner=runner)
        outcome = processor.process_file(
            args.file,
            dry_run=args.dry_run,
            output_dir=args.output_dir,
            force=args.force,
            model_override=args.model,
            effort_override=args.effort,
        )

    if outcome.status == "completed" and outcome.result is not None:
        print(f"[CREATED] {outcome.result.output_path}")
        print(f"  Category: {outcome.result.recommended_category}")
        print(f"  Tags:     {', '.join(outcome.result.tags)}")
        if outcome.result.existing_wikilinks:
            print(f"  Links:    {', '.join(outcome.result.existing_wikilinks)}")
        if outcome.archived_path:
            print(f"  Archived: {outcome.archived_path}")
        return 0
    if outcome.status == "skipped":
        print(f"[SKIPPED] Already processed (sha256={outcome.sha256[:12] if outcome.sha256 else '?'}); pass --force to reprocess.")
        return 0
    print(f"[FAILED] {outcome.error}", file=sys.stderr)
    return 1


def _cmd_watch(args: argparse.Namespace) -> int:
    config, found = load_config(args.config)
    log_level = args.log_level or config.state.log_level
    setup_logging(log_file=None if args.dry_run else config.state.log_file, level=log_level)

    watch_dir = args.watch_dir.expanduser().resolve() if args.watch_dir else config.watch.path
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else None

    logger.info("Starting yt-to-obsidian v%s watcher", __version__)
    logger.info("Config: %s | Watch: %s | Vault: %s | Dry-run: %s", found or "defaults", watch_dir, config.vault.path, args.dry_run)

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d; shutting down cleanly...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    with StateStore(config.state.db_path) as store:
        runner = AgyCliRunner(config)
        processor = TranscriptProcessor(config=config, state_store=store, runner=runner)
        worker = QueueWorker(processor=processor, dry_run=args.dry_run, output_dir=output_dir)
        watcher = TranscriptWatcher(
            watch_dir=watch_dir,
            on_ready=worker.enqueue,
            recursive=config.watch.recursive,
            allowed_extensions=config.watch.allowed_extensions,
            debounce_ms=config.watch.debounce_ms,
            stability_checks=config.watch.stability_checks,
            stability_timeout_seconds=config.watch.stability_timeout_seconds,
        )

        worker.start()
        try:
            watcher.start()
            while not stop_event.is_set():
                stop_event.wait(0.5)
        finally:
            watcher.stop()
            worker.stop(wait=True)

    logger.info("Shutdown complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-to-obsidian",
        description="Watch Downloads for YouTube transcripts and generate staged Obsidian notes via Antigravity.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # watch
    p_watch = sub.add_parser("watch", help="Run the continuous directory watcher daemon.")
    p_watch.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_watch.add_argument("--watch-dir", type=Path, default=None, help="Override watched directory.")
    p_watch.add_argument("--dry-run", action="store_true", help="Write notes to a preview dir without touching state DB or vault staging.")
    p_watch.add_argument("--output-dir", type=Path, default=None, help="Override note staging/output directory.")
    p_watch.add_argument("--log-level", default=None, help="Override log level (DEBUG, INFO, WARNING, ERROR).")
    p_watch.set_defaults(func=_cmd_watch)

    # process
    p_proc = sub.add_parser("process", help="Process a single transcript file immediately.")
    p_proc.add_argument("file", type=Path, help="Path to the YouTube transcript file.")
    p_proc.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_proc.add_argument("--dry-run", action="store_true", help="Write to preview directory without updating state DB.")
    p_proc.add_argument("--output-dir", type=Path, default=None, help="Override note output directory.")
    p_proc.add_argument("--force", action="store_true", help="Reprocess even if SHA-256 already completed.")
    p_proc.add_argument("--model", default=None, help="Override agy --model.")
    p_proc.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default=None, help="Override agy --effort.")
    p_proc.add_argument("--log-level", default=None, help="Override log level.")
    p_proc.set_defaults(func=_cmd_process)

    # validate-config
    p_val = sub.add_parser("validate-config", help="Validate config.yaml, paths, agy binary, and skill installation.")
    p_val.add_argument("--config", type=Path, default=None, help="Path to config.yaml.")
    p_val.set_defaults(func=_cmd_validate_config)

    # install-skill
    p_inst = sub.add_parser("install-skill", help="Install or verify the obsidian-youtube-note skill symlink.")
    mode = p_inst.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Verify symlink status.")
    mode.add_argument("--uninstall", action="store_true", help="Remove symlink.")
    p_inst.add_argument("--force", action="store_true", help="Replace existing symlink.")
    p_inst.add_argument("--target-dir", type=Path, default=None, help="Override target skills directory.")
    p_inst.set_defaults(func=_cmd_install_skill)

    # history
    p_hist = sub.add_parser("history", help="Display recent transcript processing runs from state.db.")
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
