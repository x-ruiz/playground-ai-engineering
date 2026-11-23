"""SQLite WAL state ledger for SHA-256 deduplication and run history."""

from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RunStatus = Literal["processing", "completed", "failed"]

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transcript_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT NOT NULL,
    source_path TEXT NOT NULL,
    fallback_title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed')),
    recommended_category TEXT,
    note_title TEXT,
    output_note_path TEXT,
    tags_json TEXT,
    error TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transcript_runs_sha256_status
    ON transcript_runs (sha256, status);
"""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class LedgerRecord:
    id: int
    sha256: str
    source_path: str
    fallback_title: str
    status: RunStatus
    recommended_category: str | None
    note_title: str | None
    output_note_path: str | None
    tags: list[str]
    error: str | None
    duration_seconds: float | None
    created_at: str
    updated_at: str


class StateStore:
    """Thread-safe SQLite store tracking processed YouTube transcripts."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA busy_timeout=5000;")
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> LedgerRecord:
        raw_tags = row["tags_json"]
        tags = json.loads(raw_tags) if raw_tags else []
        return LedgerRecord(
            id=int(row["id"]),
            sha256=str(row["sha256"]),
            source_path=str(row["source_path"]),
            fallback_title=str(row["fallback_title"]),
            status=row["status"],
            recommended_category=row["recommended_category"],
            note_title=row["note_title"],
            output_note_path=row["output_note_path"],
            tags=tags,
            error=row["error"],
            duration_seconds=row["duration_seconds"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def get_completed(self, sha256: str) -> LedgerRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM transcript_runs
                WHERE sha256 = ? AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (sha256,),
            ).fetchone()
            return self._row_to_record(row) if row is not None else None

    def is_completed(self, sha256: str) -> bool:
        return self.get_completed(sha256) is not None

    def record_start(self, *, sha256: str, source_path: Path, fallback_title: str) -> int:
        now = _utc_now_iso()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO transcript_runs (
                    sha256, source_path, fallback_title, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'processing', ?, ?)
                """,
                (sha256, str(source_path), fallback_title, now, now),
            )
            self._conn.commit()
            assert cur.lastrowid is not None
            return int(cur.lastrowid)

    def record_completed(
        self,
        run_id: int,
        *,
        category: str,
        note_title: str,
        output_note_path: Path,
        tags: list[str],
        duration_seconds: float,
    ) -> None:
        now = _utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                UPDATE transcript_runs
                SET status = 'completed',
                    recommended_category = ?,
                    note_title = ?,
                    output_note_path = ?,
                    tags_json = ?,
                    error = NULL,
                    duration_seconds = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    category,
                    note_title,
                    str(output_note_path),
                    json.dumps(tags),
                    duration_seconds,
                    now,
                    run_id,
                ),
            )
            self._conn.commit()

    def record_failed(self, run_id: int, *, error: str, duration_seconds: float) -> None:
        now = _utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                UPDATE transcript_runs
                SET status = 'failed',
                    error = ?,
                    duration_seconds = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (error, duration_seconds, now, run_id),
            )
            self._conn.commit()

    def list_recent(self, *, limit: int = 20) -> list[LedgerRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM transcript_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]
