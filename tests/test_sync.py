from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
import tempfile
import unittest

from grist_finance_connector.models.records import ExistingAccount
from grist_finance_connector.models.records import ExistingSpace
from grist_finance_connector.models.records import ExistingTransaction
from grist_finance_connector.models.records import NormalizedAccount
from grist_finance_connector.models.records import NormalizedSpace
from grist_finance_connector.models.records import NormalizedTransaction
from grist_finance_connector.models.records import ProviderFetchResult
from grist_finance_connector.services.sync import SyncService
from grist_finance_connector.state.store import StateStore


class FakeSettings:
    source_name = "example_provider"
    import_lookback_days = 30
    duplicate_mode = "skip_existing"
    dry_run = False
    batch_size = 100


class FakeProvider:
    name = "example_provider"

    def __init__(
        self,
        transactions: list[NormalizedTransaction],
        accounts: list[NormalizedAccount] | None = None,
        spaces: list[NormalizedSpace] | None = None,
    ) -> None:
        self._transactions = transactions
        self._accounts = accounts or []
        self._spaces = spaces or []

    def fetch_transactions(self, window):  # noqa: ANN001
        return ProviderFetchResult(
            accounts=self._accounts,
            spaces=self._spaces,
            transactions=self._transactions,
            next_cursor="cursor-2",
        )


class FakeGristClient:
    def __init__(
        self,
        existing: dict[str, ExistingTransaction] | None = None,
        existing_accounts: dict[str, ExistingAccount] | None = None,
        existing_spaces: dict[str, ExistingSpace] | None = None,
    ) -> None:
        self.existing = existing or {}
        self.existing_accounts = existing_accounts or {}
        self.existing_spaces = existing_spaces or {}
        self.inserted_accounts: list[NormalizedAccount] = []
        self.updated_accounts: list[tuple[int, NormalizedAccount]] = []
        self.inserted_spaces: list[NormalizedSpace] = []
        self.updated_spaces: list[tuple[int, NormalizedSpace]] = []
        self.inserted: list[NormalizedTransaction] = []
        self.updated: list[tuple[int, NormalizedTransaction]] = []
        self.import_logs: list[dict[str, object]] = []

    def get_existing_accounts(self, source_name: str, account_ids: set[str]):
        return {
            key: value for key, value in self.existing_accounts.items() if key in account_ids
        }

    def get_existing_transactions(self, source_name: str, external_ids: set[str]):
        return {key: value for key, value in self.existing.items() if key in external_ids}

    def get_existing_spaces(self, source_name: str, space_ids: set[str]):
        return {key: value for key, value in self.existing_spaces.items() if key in space_ids}

    def insert_accounts(self, accounts: list[NormalizedAccount]) -> int:
        self.inserted_accounts.extend(accounts)
        return len(accounts)

    def update_accounts(self, rows: list[tuple[int, NormalizedAccount]]) -> int:
        self.updated_accounts.extend(rows)
        return len(rows)

    def insert_spaces(self, spaces: list[NormalizedSpace]) -> int:
        self.inserted_spaces.extend(spaces)
        return len(spaces)

    def update_spaces(self, rows: list[tuple[int, NormalizedSpace]]) -> int:
        self.updated_spaces.extend(rows)
        return len(rows)

    def insert_transactions(self, transactions: list[NormalizedTransaction]) -> int:
        self.inserted.extend(transactions)
        return len(transactions)

    def update_transactions(self, rows: list[tuple[int, NormalizedTransaction]]) -> int:
        self.updated.extend(rows)
        return len(rows)

    def append_import_log(self, fields: dict[str, object]) -> None:
        self.import_logs.append(fields)


def make_transaction(external_id: str) -> NormalizedTransaction:
    return NormalizedTransaction(
        external_id=external_id,
        source_name="example_provider",
        account_id="acc-1",
        transaction_date=date(2026, 3, 30),
        description="Coffee",
        amount=Decimal("4.50"),
        currency="GBP",
        external_reference="ref-1",
    )


def make_account(account_id: str) -> NormalizedAccount:
    return NormalizedAccount(
        account_id=account_id,
        source_name="example_provider",
        account_name="Main Account",
        currency="GBP",
        account_type="PRIMARY",
    )


def make_space(space_id: str, account_id: str) -> NormalizedSpace:
    return NormalizedSpace(
        space_id=space_id,
        account_id=account_id,
        source_name="example_provider",
        space_name="Holiday Fund",
        space_balance=Decimal("50.00"),
        space_target=Decimal("200.00"),
        space_transactions=2,
    )


class SyncServiceTests(unittest.TestCase):
    def test_sync_inserts_new_records_and_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = StateStore(f"{tmpdir}/state.sqlite3")
            grist_client = FakeGristClient()
            service = SyncService(
                settings=FakeSettings(),
                provider=FakeProvider(
                    [make_transaction("tx-1")],
                    [make_account("acc-1")],
                    [make_space("space-1", "acc-1")],
                ),
                grist_client=grist_client,
                state_store=state_store,
                logger=logging.getLogger("test-sync"),
            )

            result = service.run("example_provider")

            self.assertTrue(result.success)
            self.assertEqual(result.inserted_count, 1)
            self.assertEqual(result.updated_count, 0)
            self.assertEqual(len(grist_client.inserted), 1)
            self.assertEqual(len(grist_client.inserted_accounts), 1)
            self.assertEqual(len(grist_client.inserted_spaces), 1)
            self.assertIsNotNone(state_store.load("example_provider").last_successful_sync_at)

    def test_sync_skips_duplicates_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = StateStore(f"{tmpdir}/state.sqlite3")
            grist_client = FakeGristClient(
                existing={
                    "tx-1": ExistingTransaction(
                        row_id=99, external_id="tx-1", source_name="example_provider"
                    )
                }
            )
            service = SyncService(
                settings=FakeSettings(),
                provider=FakeProvider([make_transaction("tx-1")]),
                grist_client=grist_client,
                state_store=state_store,
                logger=logging.getLogger("test-sync"),
            )

            result = service.run("example_provider")

            self.assertTrue(result.success)
            self.assertEqual(result.inserted_count, 0)
            self.assertEqual(result.skipped_count, 1)

    def test_sync_updates_existing_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = StateStore(f"{tmpdir}/state.sqlite3")
            grist_client = FakeGristClient(
                existing_accounts={
                    "acc-1": ExistingAccount(
                        row_id=7,
                        account_id="acc-1",
                        source_name="example_provider",
                    )
                }
            )
            service = SyncService(
                settings=FakeSettings(),
                provider=FakeProvider([make_transaction("tx-1")], [make_account("acc-1")]),
                grist_client=grist_client,
                state_store=state_store,
                logger=logging.getLogger("test-sync"),
            )

            result = service.run("example_provider")

            self.assertTrue(result.success)
            self.assertEqual(len(grist_client.inserted_accounts), 0)
            self.assertEqual(len(grist_client.updated_accounts), 1)

    def test_sync_updates_existing_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_store = StateStore(f"{tmpdir}/state.sqlite3")
            grist_client = FakeGristClient(
                existing_spaces={
                    "space-1": ExistingSpace(
                        row_id=10,
                        space_id="space-1",
                        source_name="example_provider",
                    )
                }
            )
            service = SyncService(
                settings=FakeSettings(),
                provider=FakeProvider(
                    [make_transaction("tx-1")],
                    [make_account("acc-1")],
                    [make_space("space-1", "acc-1")],
                ),
                grist_client=grist_client,
                state_store=state_store,
                logger=logging.getLogger("test-sync"),
            )

            result = service.run("example_provider")

            self.assertTrue(result.success)
            self.assertEqual(len(grist_client.inserted_spaces), 0)
            self.assertEqual(len(grist_client.updated_spaces), 1)


if __name__ == "__main__":
    unittest.main()
