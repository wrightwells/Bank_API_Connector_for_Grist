from __future__ import annotations

from datetime import datetime
import tempfile
import unittest

from grist_finance_connector.models.records import SyncJobResult
from grist_finance_connector.models.records import SyncState
from grist_finance_connector.state.store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_save_and_load_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(f"{tmpdir}/state.sqlite3")
            now = datetime(2026, 3, 30, 12, 0, 0)
            store.save(
                SyncState(
                    source_name="provider-a",
                    last_successful_sync_at=now,
                    cursor="cursor-1",
                )
            )

            loaded = store.load("provider-a")

            self.assertEqual(loaded.source_name, "provider-a")
            self.assertEqual(loaded.cursor, "cursor-1")
            self.assertEqual(loaded.last_successful_sync_at, now)

    def test_record_job_and_read_recent_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(f"{tmpdir}/state.sqlite3")
            store.record_job(
                SyncJobResult(
                    source_name="provider-a",
                    fetched_count=3,
                    inserted_count=2,
                    updated_count=0,
                    skipped_count=1,
                    failed_count=0,
                    success=True,
                    started_at=datetime(2026, 3, 30, 12, 0, 0),
                    finished_at=datetime(2026, 3, 30, 12, 0, 5),
                    message="ok",
                )
            )

            jobs = store.recent_jobs(limit=1)

            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["source_name"], "provider-a")
            self.assertTrue(jobs[0]["success"])


if __name__ == "__main__":
    unittest.main()
