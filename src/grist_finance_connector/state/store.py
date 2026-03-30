"""SQLite-backed sync state persistence."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import sqlite3

from grist_finance_connector.models.records import SyncJobResult
from grist_finance_connector.models.records import SyncState


class StateStore:
    """Persists successful sync state and job history."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._initialise()

    def load(self, source_name: str) -> SyncState:
        with closing(sqlite3.connect(self._db_path)) as connection:
            row = connection.execute(
                """
                SELECT source_name, last_successful_sync_at, cursor
                FROM sync_state
                WHERE source_name = ?
                """,
                (source_name,),
            ).fetchone()

        if row is None:
            return SyncState(source_name=source_name)

        last_successful_sync_at = (
            datetime.fromisoformat(row[1]) if row[1] else None
        )
        return SyncState(
            source_name=row[0],
            last_successful_sync_at=last_successful_sync_at,
            cursor=row[2],
        )

    def save(self, state: SyncState) -> None:
        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.execute(
                """
                INSERT INTO sync_state (source_name, last_successful_sync_at, cursor)
                VALUES (?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    last_successful_sync_at = excluded.last_successful_sync_at,
                    cursor = excluded.cursor
                """,
                (
                    state.source_name,
                    state.last_successful_sync_at.isoformat()
                    if state.last_successful_sync_at
                    else None,
                    state.cursor,
                ),
            )
            connection.commit()

    def record_job(self, job: SyncJobResult) -> None:
        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.execute(
                """
                INSERT INTO job_history (
                    source_name,
                    started_at,
                    finished_at,
                    success,
                    fetched_count,
                    inserted_count,
                    updated_count,
                    skipped_count,
                    failed_count,
                    message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.source_name,
                    job.started_at.isoformat(),
                    job.finished_at.isoformat(),
                    1 if job.success else 0,
                    job.fetched_count,
                    job.inserted_count,
                    job.updated_count,
                    job.skipped_count,
                    job.failed_count,
                    job.message,
                ),
            )
            connection.commit()

    def recent_jobs(self, limit: int = 10) -> list[dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as connection:
            rows = connection.execute(
                """
                SELECT source_name, started_at, finished_at, success, fetched_count,
                       inserted_count, updated_count, skipped_count, failed_count, message
                FROM job_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "source_name": row[0],
                "started_at": row[1],
                "finished_at": row[2],
                "success": bool(row[3]),
                "fetched_count": row[4],
                "inserted_count": row[5],
                "updated_count": row[6],
                "skipped_count": row[7],
                "failed_count": row[8],
                "message": row[9],
            }
            for row in rows
        ]

    def _initialise(self) -> None:
        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    source_name TEXT PRIMARY KEY,
                    last_successful_sync_at TEXT,
                    cursor TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    fetched_count INTEGER NOT NULL,
                    inserted_count INTEGER NOT NULL,
                    updated_count INTEGER NOT NULL,
                    skipped_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            connection.commit()
