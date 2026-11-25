"""SQLite WAL state store for URL and content-hash deduplication and run history."""

from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS note_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_url TEXT,
    content_sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,
    note_action TEXT NOT NULL DEFAULT 'create',
    target_note TEXT,
    source_title TEXT NOT NULL,
    status TEXT NOT NULL,
    recommended_category TEXT,
    note_title TEXT,
    output_note_path TEXT,
    tags_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_note_runs_url_status
    ON note_runs (canonical_url, status);

CREATE INDEX IF NOT EXISTS idx_note_runs_sha_status
    ON note_runs (content_sha256, status);
"""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class NoteRunRecord:
    id: int
    canonical_url: str | None
    content_sha256: str
    source_type: str
    note_action: str
    target_note: str | None
    source_title: str
    status: str
    recommended_category: str | None
    note_title: str | None
    output_note_path: str | None
    tags: list[str]
    error: str | None
    created_at: str
    updated_at: str


class StateStore:
    """Persistent SQLite WAL ledger for generated Obsidian notes and update drafts."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> NoteRunRecord:
        tags_raw = row["tags_json"]
        tags = json.loads(tags_raw) if tags_raw else []
        return NoteRunRecord(
            id=int(row["id"]),
            canonical_url=row["canonical_url"],
            content_sha256=str(row["content_sha256"]),
            source_type=str(row["source_type"]),
            note_action=str(row["note_action"]),
            target_note=row["target_note"],
            source_title=str(row["source_title"]),
            status=str(row["status"]),
            recommended_category=row["recommended_category"],
            note_title=row["note_title"],
            output_note_path=row["output_note_path"],
            tags=[str(t) for t in tags],
            error=row["error"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def get_completed_by_url(self, canonical_url: str) -> NoteRunRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM note_runs
            WHERE canonical_url = ? AND status = 'completed'
            ORDER BY id DESC LIMIT 1
            """,
            (canonical_url,),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_completed_by_hash(self, content_sha256: str) -> NoteRunRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM note_runs
            WHERE content_sha256 = ? AND status = 'completed'
            ORDER BY id DESC LIMIT 1
            """,
            (content_sha256,),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def record_completed(
        self,
        *,
        canonical_url: str | None,
        content_sha256: str,
        source_type: str,
        note_action: str,
        target_note: str | None,
        source_title: str,
        recommended_category: str,
        note_title: str,
        output_note_path: Path,
        tags: list[str],
    ) -> int:
        now = _utc_now_iso()
        cur = self._conn.execute(
            """
            INSERT INTO note_runs (
                canonical_url, content_sha256, source_type, note_action, target_note,
                source_title, status, recommended_category, note_title, output_note_path,
                tags_json, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                canonical_url,
                content_sha256,
                source_type,
                note_action,
                target_note,
                source_title,
                recommended_category,
                note_title,
                str(output_note_path),
                json.dumps(tags),
                now,
                now,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def record_failed(
        self,
        *,
        canonical_url: str | None,
        content_sha256: str,
        source_type: str,
        source_title: str,
        error: str,
    ) -> int:
        now = _utc_now_iso()
        cur = self._conn.execute(
            """
            INSERT INTO note_runs (
                canonical_url, content_sha256, source_type, note_action, target_note,
                source_title, status, error, created_at, updated_at
            ) VALUES (?, ?, ?, 'create', NULL, ?, 'failed', ?, ?, ?)
            """,
            (canonical_url, content_sha256, source_type, source_title, error[:2000], now, now),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_recent(self, *, limit: int = 20) -> list[NoteRunRecord]:
        rows = self._conn.execute(
            "SELECT * FROM note_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]
