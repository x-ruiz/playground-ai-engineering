"""Single-threaded sequential transcript processing queue and post-processing."""

from __future__ import annotations

import logging
import queue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from yt_to_obsidian.config import AppConfig
from yt_to_obsidian.notifier import send_notification
from yt_to_obsidian.parser import TranscriptParseError, parse_transcript
from yt_to_obsidian.runner import AgentRunner, RunnerError, RunRequest, RunResult
from yt_to_obsidian.state import StateStore

logger = logging.getLogger("yt_to_obsidian.worker")

ProcessStatus = Literal["completed", "skipped", "failed"]


@dataclass(frozen=True)
class ProcessOutcome:
    status: ProcessStatus
    source_path: Path
    sha256: str | None = None
    result: RunResult | None = None
    error: str | None = None
    archived_path: Path | None = None


def _archive_transcript(source_path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / source_path.name
    if target.exists():
        stem = source_path.stem
        suffix = source_path.suffix
        counter = 1
        while True:
            candidate = archive_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                target = candidate
                break
            counter += 1
    shutil.move(str(source_path), str(target))
    return target.resolve()


class TranscriptProcessor:
    """Executes the parse -> dedup -> agent runner -> state -> archive lifecycle."""

    def __init__(
        self,
        *,
        config: AppConfig,
        state_store: StateStore,
        runner: AgentRunner,
    ) -> None:
        self.config = config
        self.state_store = state_store
        self.runner = runner

    def process_file(
        self,
        path: Path,
        *,
        dry_run: bool = False,
        output_dir: Path | None = None,
        force: bool = False,
        model_override: str | None = None,
        effort_override: str | None = None,
    ) -> ProcessOutcome:
        source_path = path.expanduser().resolve()
        started = time.monotonic()

        try:
            doc = parse_transcript(source_path)
        except TranscriptParseError as exc:
            logger.warning("Skipping invalid transcript %s: %s", source_path, exc)
            return ProcessOutcome(status="failed", source_path=source_path, error=str(exc))

        if not force:
            existing = self.state_store.get_completed(doc.sha256)
            if existing is not None:
                logger.info(
                    "Skipping duplicate transcript '%s' (sha256=%s, already staged at %s)",
                    source_path.name,
                    doc.sha256[:12],
                    existing.output_note_path,
                )
                return ProcessOutcome(status="skipped", source_path=source_path, sha256=doc.sha256)

        run_id: int | None = None
        if not dry_run:
            run_id = self.state_store.record_start(
                sha256=doc.sha256,
                source_path=source_path,
                fallback_title=doc.fallback_title,
            )

        if output_dir is not None:
            resolved_output_dir = output_dir.expanduser().resolve()
        elif dry_run:
            resolved_output_dir = Path(tempfile.mkdtemp(prefix="yt-to-obsidian-dryrun-")).resolve()
        else:
            resolved_output_dir = self.config.staging_path

        request = RunRequest(
            transcript=doc,
            output_dir=resolved_output_dir,
            vault_path=self.config.vault.path,
            dry_run=dry_run,
            model_override=model_override,
            effort_override=effort_override,
        )

        try:
            result = self.runner.run(request)
        except (RunnerError, Exception) as exc:
            elapsed = round(time.monotonic() - started, 2)
            error_msg = str(exc)
            logger.error("Failed processing '%s' after %.2fs: %s", source_path.name, elapsed, error_msg)
            if run_id is not None:
                self.state_store.record_failed(run_id, error=error_msg, duration_seconds=elapsed)
            if not dry_run:
                send_notification(
                    "yt-to-obsidian failed",
                    f"{doc.fallback_title}: {error_msg[:120]}",
                    enabled=self.config.notifications.enabled,
                )
            return ProcessOutcome(
                status="failed",
                source_path=source_path,
                sha256=doc.sha256,
                error=error_msg,
            )

        elapsed = round(time.monotonic() - started, 2)
        if run_id is not None:
            self.state_store.record_completed(
                run_id,
                category=result.recommended_category,
                note_title=result.note_title,
                output_note_path=result.output_path,
                tags=result.tags,
                duration_seconds=elapsed,
            )

        archived_path: Path | None = None
        if not dry_run and self.config.post_process.action == "move":
            try:
                archived_path = _archive_transcript(source_path, self.config.post_process.archive_dir)
                logger.info("Archived source transcript to %s", archived_path)
            except OSError as exc:
                logger.warning("Note staged, but failed to archive %s: %s", source_path, exc)

        logger.info(
            "Staged '%s' -> %s [%s] (%.2fs)",
            doc.fallback_title,
            result.output_path,
            result.recommended_category,
            elapsed,
        )
        if not dry_run:
            send_notification(
                "Obsidian note staged",
                f"{result.note_title} ({result.recommended_category})",
                enabled=self.config.notifications.enabled,
            )

        return ProcessOutcome(
            status="completed",
            source_path=source_path,
            sha256=doc.sha256,
            result=result,
            archived_path=archived_path,
        )


class QueueWorker:
    """Single sequential background thread consuming queued transcript paths."""

    def __init__(
        self,
        *,
        processor: TranscriptProcessor,
        dry_run: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        self._processor = processor
        self._dry_run = dry_run
        self._output_dir = output_dir
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="yt-to-obsidian-worker",
            daemon=True,
        )
        self._stopped = threading.Event()

    def start(self) -> None:
        self._thread.start()

    def enqueue(self, path: Path) -> None:
        if self._stopped.is_set():
            return
        logger.info("Enqueued transcript: %s", path.name)
        self._queue.put(path)

    def stop(self, *, wait: bool = True) -> None:
        if not self._stopped.is_set():
            self._stopped.set()
            self._queue.put(None)
        if wait and self._thread.is_alive():
            self._thread.join(timeout=30.0)

    def wait_until_idle(self) -> None:
        self._queue.join()

    def _run_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                self._processor.process_file(
                    item,
                    dry_run=self._dry_run,
                    output_dir=self._output_dir,
                )
            except Exception:
                logger.exception("Unhandled error while processing queued item: %s", item)
            finally:
                self._queue.task_done()
