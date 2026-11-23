"""Cross-platform event-driven directory watcher with non-blocking write-stability debounce."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from yt_to_obsidian.matcher import DEFAULT_ALLOWED_EXTENSIONS, match_transcript_path

logger = logging.getLogger("yt_to_obsidian.watcher")


@dataclass
class _PendingEntry:
    first_seen: float
    last_event_at: float
    last_check_at: float
    last_sig: tuple[int, int] | None = None
    stable_count: int = 0


class StabilityDebouncer:
    """Coalesces OS events and waits until a file is non-empty and stops changing."""

    def __init__(
        self,
        *,
        on_ready: Callable[[Path], None],
        debounce_ms: int = 500,
        stability_checks: int = 2,
        stability_timeout_seconds: float = 15.0,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        self._on_ready = on_ready
        self._debounce_seconds = debounce_ms / 1000.0
        self._stability_checks = max(1, stability_checks)
        self._timeout_seconds = stability_timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._lock = threading.Lock()
        self._pending: dict[Path, _PendingEntry] = {}
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="yt-to-obsidian-debouncer",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def notify(self, path: Path) -> None:
        resolved = path.resolve()
        now = time.monotonic()
        with self._lock:
            existing = self._pending.get(resolved)
            if existing is None:
                self._pending[resolved] = _PendingEntry(
                    first_seen=now,
                    last_event_at=now,
                    last_check_at=now,
                )
            else:
                existing.last_event_at = now
                existing.stable_count = 0

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            ready_paths: list[Path] = []
            now = time.monotonic()

            with self._lock:
                for path in list(self._pending):
                    entry = self._pending[path]
                    if now - entry.first_seen > self._timeout_seconds:
                        logger.warning(
                            "Dropping unstable or empty file after %.1fs: %s",
                            self._timeout_seconds,
                            path,
                        )
                        del self._pending[path]
                        continue

                    if now - entry.last_event_at < self._debounce_seconds:
                        continue
                    if now - entry.last_check_at < self._debounce_seconds:
                        continue

                    entry.last_check_at = now
                    try:
                        stat = path.stat()
                    except FileNotFoundError:
                        logger.debug("Pending file vanished before stabilizing: %s", path)
                        del self._pending[path]
                        continue
                    except OSError as exc:
                        logger.debug("Stat failed for %s: %s", path, exc)
                        continue

                    if stat.st_size <= 0:
                        entry.last_sig = None
                        entry.stable_count = 0
                        continue

                    sig = (stat.st_size, stat.st_mtime_ns)
                    if sig == entry.last_sig:
                        entry.stable_count += 1
                    else:
                        entry.last_sig = sig
                        entry.stable_count = 1

                    if entry.stable_count >= self._stability_checks:
                        ready_paths.append(path)
                        del self._pending[path]

            for ready in ready_paths:
                try:
                    self._on_ready(ready)
                except Exception:
                    logger.exception("Error dispatching stabilized file: %s", ready)

            self._stop_event.wait(self._poll_interval)


class TranscriptEventHandler(FileSystemEventHandler):
    """Watchdog handler listening for created, moved, and modified transcript files."""

    def __init__(
        self,
        *,
        debouncer: StabilityDebouncer,
        allowed_extensions: Iterable[str] = DEFAULT_ALLOWED_EXTENSIONS,
    ) -> None:
        super().__init__()
        self._debouncer = debouncer
        self._allowed_extensions = tuple(allowed_extensions)

    def _handle_candidate(self, raw_path: str | bytes) -> None:
        path_str = raw_path.decode() if isinstance(raw_path, bytes) else raw_path
        path = Path(path_str)
        match = match_transcript_path(path, allowed_extensions=self._allowed_extensions)
        if match is None:
            return
        logger.debug("Matched transcript event: %s", path)
        self._debouncer.notify(path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_candidate(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_candidate(event.dest_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_candidate(event.src_path)


class TranscriptWatcher:
    """High-level watcher owning watchdog Observer and StabilityDebouncer."""

    def __init__(
        self,
        *,
        watch_dir: Path,
        on_ready: Callable[[Path], None],
        recursive: bool = False,
        allowed_extensions: Iterable[str] = DEFAULT_ALLOWED_EXTENSIONS,
        debounce_ms: int = 500,
        stability_checks: int = 2,
        stability_timeout_seconds: float = 15.0,
    ) -> None:
        self.watch_dir = watch_dir.expanduser().resolve()
        self.recursive = recursive
        self._debouncer = StabilityDebouncer(
            on_ready=on_ready,
            debounce_ms=debounce_ms,
            stability_checks=stability_checks,
            stability_timeout_seconds=stability_timeout_seconds,
        )
        self._handler = TranscriptEventHandler(
            debouncer=self._debouncer,
            allowed_extensions=allowed_extensions,
        )
        self._observer = Observer()

    def start(self) -> None:
        if not self.watch_dir.is_dir():
            raise FileNotFoundError(f"Watch directory does not exist: {self.watch_dir}")
        self._debouncer.start()
        self._observer.schedule(self._handler, str(self.watch_dir), recursive=self.recursive)
        self._observer.start()
        logger.info("Watching %s (recursive=%s)", self.watch_dir, self.recursive)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5.0)
        self._debouncer.stop()
        logger.info("Stopped watcher for %s", self.watch_dir)

    def __enter__(self) -> TranscriptWatcher:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
