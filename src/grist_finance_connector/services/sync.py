"""Sync orchestration."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
import logging

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.grist.client import GristClient
from grist_finance_connector.models.records import FetchWindow
from grist_finance_connector.models.records import NormalizedAccount
from grist_finance_connector.models.records import NormalizedSpace
from grist_finance_connector.models.records import SyncJobResult
from grist_finance_connector.models.records import SyncState
from grist_finance_connector.models.records import WritePlan
from grist_finance_connector.providers.base import ProviderAdapter
from grist_finance_connector.state.store import StateStore


class SyncService:
    """Coordinates a source sync and persists the final outcome."""

    def __init__(
        self,
        settings: Settings,
        provider: ProviderAdapter,
        grist_client: GristClient,
        state_store: StateStore,
        logger: logging.Logger,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._grist_client = grist_client
        self._state_store = state_store
        self._logger = logger

    def run(self, source_name: str) -> SyncJobResult:
        started_at = datetime.now(UTC)
        self._logger.info("sync started", extra={"source_name": source_name})

        try:
            state = self._state_store.load(source_name)
            window = self._build_window(state)
            fetch_result = self._provider.fetch_transactions(window)
            account_inserted_count, account_updated_count = self._sync_accounts(
                fetch_result.accounts
            )
            space_inserted_count, space_updated_count = self._sync_spaces(
                fetch_result.spaces
            )
            plan = self._build_write_plan(fetch_result.transactions)

            inserted_count = len(plan.to_insert)
            updated_count = len(plan.to_update)
            skipped_count = plan.skipped_count + plan.conflict_count

            if not self._settings.dry_run:
                inserted_count = self._grist_client.insert_transactions(plan.to_insert)
                updated_count = self._grist_client.update_transactions(plan.to_update)

            finished_at = datetime.now(UTC)
            result = SyncJobResult(
                source_name=source_name,
                fetched_count=len(fetch_result.transactions),
                inserted_count=inserted_count,
                updated_count=updated_count,
                skipped_count=skipped_count,
                failed_count=0,
                success=True,
                started_at=started_at,
                finished_at=finished_at,
                message="dry-run completed" if self._settings.dry_run else "sync completed",
            )
            self._state_store.record_job(result)
            self._state_store.save(
                SyncState(
                    source_name=source_name,
                    last_successful_sync_at=finished_at,
                    cursor=fetch_result.next_cursor,
                )
            )
            self._write_import_log(result)
            self._logger.info(
                "sync completed",
                extra={
                    "source_name": source_name,
                    "accounts_fetched": len(fetch_result.accounts),
                    "accounts_inserted": account_inserted_count,
                    "accounts_updated": account_updated_count,
                    "spaces_fetched": len(fetch_result.spaces),
                    "spaces_inserted": space_inserted_count,
                    "spaces_updated": space_updated_count,
                    "fetched": result.fetched_count,
                    "inserted": result.inserted_count,
                    "updated": result.updated_count,
                    "skipped": result.skipped_count,
                    "dry_run": self._settings.dry_run,
                },
            )
            return result
        except Exception as exc:
            finished_at = datetime.now(UTC)
            result = SyncJobResult(
                source_name=source_name,
                fetched_count=0,
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                failed_count=1,
                success=False,
                started_at=started_at,
                finished_at=finished_at,
                message=str(exc),
            )
            self._state_store.record_job(result)
            self._write_import_log(result)
            self._logger.exception("sync failed", extra={"source_name": source_name})
            return result

    def _sync_accounts(self, accounts: list[NormalizedAccount]) -> tuple[int, int]:
        if not accounts:
            return 0, 0

        account_ids = {account.account_id for account in accounts}
        existing = self._grist_client.get_existing_accounts(
            self._settings.source_name, account_ids
        )

        to_insert: list[NormalizedAccount] = []
        to_update: list[tuple[int, NormalizedAccount]] = []
        for account in accounts:
            match = existing.get(account.account_id)
            if match is None:
                to_insert.append(account)
            else:
                to_update.append((match.row_id, account))

        inserted_count = len(to_insert)
        updated_count = len(to_update)
        if not self._settings.dry_run:
            inserted_count = self._grist_client.insert_accounts(to_insert)
            updated_count = self._grist_client.update_accounts(to_update)

        self._logger.info(
            "account sync completed",
            extra={
                "source_name": self._settings.source_name,
                "accounts_fetched": len(accounts),
                "accounts_inserted": inserted_count,
                "accounts_updated": updated_count,
                "dry_run": self._settings.dry_run,
            },
        )
        return inserted_count, updated_count

    def _sync_spaces(self, spaces: list[NormalizedSpace]) -> tuple[int, int]:
        if not spaces:
            return 0, 0

        space_ids = {space.space_id for space in spaces}
        existing = self._grist_client.get_existing_spaces(
            self._settings.source_name, space_ids
        )

        to_insert: list[NormalizedSpace] = []
        to_update: list[tuple[int, NormalizedSpace]] = []
        for space in spaces:
            match = existing.get(space.space_id)
            if match is None:
                to_insert.append(space)
            else:
                to_update.append((match.row_id, space))

        inserted_count = len(to_insert)
        updated_count = len(to_update)
        if not self._settings.dry_run:
            inserted_count = self._grist_client.insert_spaces(to_insert)
            updated_count = self._grist_client.update_spaces(to_update)

        self._logger.info(
            "space sync completed",
            extra={
                "source_name": self._settings.source_name,
                "spaces_fetched": len(spaces),
                "spaces_inserted": inserted_count,
                "spaces_updated": updated_count,
                "dry_run": self._settings.dry_run,
            },
        )
        return inserted_count, updated_count

    def _build_window(self, state: SyncState) -> FetchWindow:
        end = datetime.now(UTC)
        if state.last_successful_sync_at:
            start = state.last_successful_sync_at
        else:
            start = end - timedelta(days=self._settings.import_lookback_days)
        return FetchWindow(start=start, end=end, cursor=state.cursor)

    def _build_write_plan(self, transactions) -> WritePlan:
        external_ids = {tx.external_id for tx in transactions}
        existing = self._grist_client.get_existing_transactions(
            self._settings.source_name, external_ids
        )

        to_insert = []
        to_update = []
        skipped_count = 0
        conflict_count = 0

        for transaction in transactions:
            match = existing.get(transaction.external_id)
            if match is None:
                to_insert.append(transaction)
                continue

            if self._settings.duplicate_mode == "skip_existing":
                skipped_count += 1
            elif self._settings.duplicate_mode == "update_matching":
                to_update.append((match.row_id, transaction))
            else:
                conflict_count += 1
                self._logger.warning(
                    "duplicate encountered; skipping record",
                    extra={
                        "source_name": transaction.source_name,
                        "external_id": transaction.external_id,
                    },
                )

        return WritePlan(
            to_insert=to_insert,
            to_update=to_update,
            skipped_count=skipped_count,
            conflict_count=conflict_count,
        )

    def _write_import_log(self, result: SyncJobResult) -> None:
        self._grist_client.append_import_log(
            {
                "source_name": result.source_name,
                "start_time": result.started_at.isoformat(),
                "end_time": result.finished_at.isoformat(),
                "duration_seconds": int(
                    (result.finished_at - result.started_at).total_seconds()
                ),
                "fetched_count": result.fetched_count,
                "inserted_count": result.inserted_count,
                "updated_count": result.updated_count,
                "skipped_count": result.skipped_count,
                "failed_count": result.failed_count,
                "status": "success" if result.success else "failed",
                "message": result.message,
            }
        )
