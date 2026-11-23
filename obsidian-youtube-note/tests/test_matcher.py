"""Tests for yt_to_obsidian.matcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from yt_to_obsidian.matcher import extract_fallback_title, match_transcript_path


@pytest.mark.parametrize(
    ("filename", "expected_title"),
    [
        ("Protocol_Buffers_Crash_Course_transcript", "Protocol Buffers Crash Course"),
        ("Protocol_Buffers_Crash_Course_TRANSCRIPT", "Protocol Buffers Crash Course"),
        ("System_Design_101_transcript.txt", "System Design 101"),
        ("Kafka_Internals_transcript.md", "Kafka Internals"),
        ("gRPC_Deep_Dive_transcript.srt", "gRPC Deep Dive"),
        ("Iceberg_Architecture_transcript.VTT", "Iceberg Architecture"),
        ("My__Spaced_Video_transcript.txt", "My Spaced Video"),
    ],
)
def test_matches_valid_transcript_filenames(filename: str, expected_title: str) -> None:
    match = match_transcript_path(Path("/tmp/Downloads") / filename)
    assert match is not None
    assert match.fallback_title == expected_title


@pytest.mark.parametrize(
    "filename",
    [
        "Protocol_Buffers_Crash_Course_transcript.crdownload",
        "Protocol_Buffers_Crash_Course_transcript.txt.crdownload",
        "Protocol_Buffers_Crash_Course_transcript.part",
        "Protocol_Buffers_Crash_Course_transcript.download",
        "Protocol_Buffers_Crash_Course_transcript.tmp",
        "Protocol_Buffers_Crash_Course_transcript.pdf",
        "Protocol_Buffers_Crash_Course_transcript.zip",
        ".Protocol_Buffers_Crash_Course_transcript",
        ".DS_Store",
        "_transcript",
        "_transcript.txt",
        "random_notes.txt",
        "transcript_at_start.txt",
    ],
)
def test_ignores_temp_hidden_and_unrelated_files(filename: str) -> None:
    assert match_transcript_path(Path("/tmp/Downloads") / filename) is None


def test_extract_fallback_title_handles_mixed_separators() -> None:
    assert extract_fallback_title("Apache_Iceberg___Crash_Course_transcript") == "Apache Iceberg Crash Course"
