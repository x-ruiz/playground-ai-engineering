"""Tests for yt_to_obsidian.parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from yt_to_obsidian.parser import TranscriptParseError, parse_transcript

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "Protocol_Buffers_Crash_Course_transcript"


def test_parse_real_fixture_extracts_headers_and_strips_timestamps() -> None:
    doc = parse_transcript(FIXTURE_PATH)
    assert doc.detected_format == "timestamped"
    assert doc.fallback_title == "Protocol Buffers Crash Course"
    assert doc.detected_title == "Protocol Buffers Crash Course"
    assert doc.channel == "Backend Engineering Deep Dives"
    assert doc.url == "https://www.youtube.com/watch?v=protobuf-crash-course-fixture"
    assert len(doc.sha256) == 64
    assert "00:00" not in doc.cleaned_text
    assert "05:30" not in doc.cleaned_text
    assert "TableCommitEvent" in doc.cleaned_text
    rendered = doc.render_for_agent()
    assert rendered.startswith("Title: Protocol Buffers Crash Course")


def test_parse_vtt_deduplicates_rolling_captions(tmp_path: Path) -> None:
    vtt_file = tmp_path / "Kafka_Internals_transcript.vtt"
    vtt_file.write_text(
        """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000 align:start position:0%
<c>Kafka stores records</c> in an append-only log

00:00:03.000 --> 00:00:05.000
Kafka stores records in an append-only log
Partitions enable horizontal parallelism
""",
        encoding="utf-8-sig",
    )
    doc = parse_transcript(vtt_file)
    assert doc.detected_format == "vtt"
    assert doc.cleaned_text.count("Kafka stores records in an append-only log") == 1
    assert "Partitions enable horizontal parallelism" in doc.cleaned_text
    assert "WEBVTT" not in doc.cleaned_text
    assert "-->" not in doc.cleaned_text


def test_parse_srt_strips_indices_and_timings(tmp_path: Path) -> None:
    srt_file = tmp_path / "Redis_Caching_transcript.srt"
    srt_file.write_text(
        """1
00:00:00,000 --> 00:00:02,500
<i>Redis</i> is single-threaded for command execution.

2
00:00:02,500 --> 00:00:05,000
Avoid KEYS * in production.
""",
        encoding="utf-8",
    )
    doc = parse_transcript(srt_file)
    assert doc.detected_format == "srt"
    assert "Redis is single-threaded for command execution." in doc.cleaned_text
    assert "Avoid KEYS * in production." in doc.cleaned_text
    assert "00:00:00,000" not in doc.cleaned_text


def test_parse_rejects_empty_and_binary_files(tmp_path: Path) -> None:
    empty_file = tmp_path / "Empty_transcript"
    empty_file.write_bytes(b"")
    with pytest.raises(TranscriptParseError, match="empty"):
        parse_transcript(empty_file)

    binary_file = tmp_path / "Binary_transcript"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    with pytest.raises(TranscriptParseError, match="binary"):
        parse_transcript(binary_file)
