"""Tests for yt_to_obsidian.watcher."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from yt_to_obsidian.watcher import TranscriptWatcher


def test_watcher_handles_created_and_atomic_moved_rename_with_debounce(tmp_path: Path) -> None:
    received: list[Path] = []
    ready_event = threading.Event()
    second_event = threading.Event()

    def on_ready(path: Path) -> None:
        received.append(path)
        if len(received) == 1:
            ready_event.set()
        elif len(received) == 2:
            second_event.set()

    with TranscriptWatcher(
        watch_dir=tmp_path,
        on_ready=on_ready,
        debounce_ms=80,
        stability_checks=2,
        stability_timeout_seconds=5.0,
    ):
        # Give OS observer a brief moment to attach
        time.sleep(0.15)

        # 1. Unrelated and temp files must be ignored
        (tmp_path / "unrelated.txt").write_text("hello", encoding="utf-8")
        temp_download = tmp_path / "Protocol_Buffers_transcript.crdownload"
        temp_download.write_text("partial chunk 1\n", encoding="utf-8")
        time.sleep(0.25)
        assert received == []

        # 2. Atomic rename simulating Chromium download completion -> on_moved
        final_file = tmp_path / "Protocol_Buffers_transcript"
        temp_download.rename(final_file)
        assert ready_event.wait(timeout=3.0), f"Timed out waiting for moved file; got {received}"
        assert received[0] == final_file.resolve()

        # 3. Direct creation with chunked writes -> on_created + stability debounce
        created_file = tmp_path / "Kafka_Streams_transcript.txt"
        created_file.write_text("chunk 1\n", encoding="utf-8")
        time.sleep(0.03)
        created_file.write_text("chunk 1\nchunk 2\n", encoding="utf-8")
        assert second_event.wait(timeout=3.0), f"Timed out waiting for created file; got {received}"
        assert received[1] == created_file.resolve()

        # Ensure coalescing did not double-fire
        time.sleep(0.25)
        assert len(received) == 2
