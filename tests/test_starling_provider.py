from __future__ import annotations

from datetime import UTC
from datetime import datetime
import io
import json
import unittest
from unittest.mock import patch

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.models.records import FetchWindow
from grist_finance_connector.providers.starling_provider import StarlingBankProvider


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def make_settings() -> Settings:
    return Settings(
        log_level="INFO",
        service_host="0.0.0.0",
        service_port=8080,
        scheduler_enabled=False,
        source_schedule="0 * * * *",
        source_enabled=True,
        source_provider="starling",
        source_name="starling_bank",
        source_base_url="",
        source_transactions_path="/transactions",
        source_auth_method="none",
        source_api_key="",
        source_api_key_header="X-API-Key",
        source_bearer_token="",
        starling_api_base_url="https://api.starlingbank.com",
        starling_access_token="token",
        starling_access_tokens=(),
        starling_account_uid="",
        starling_account_uids=(),
        source_timeout_ms=15000,
        retry_count=0,
        retry_backoff_ms=0,
        import_lookback_days=30,
        duplicate_mode="skip_existing",
        dry_run=True,
        batch_size=100,
        state_db_path="/tmp/state.sqlite3",
        grist_base_url="http://grist:8484",
        grist_doc_id="doc123",
        grist_api_key="secret",
        grist_transactions_table="Raw_Import_Transactions",
        grist_accounts_table="Accounts",
        grist_spaces_table="Spaces",
        grist_import_log_table="Import_Log",
        external_id_column="external_id",
        source_name_column="source_name",
        transaction_date_column="transaction_date",
        description_column="description",
        amount_column="amount",
        currency_column="currency",
        account_id_column="account_id",
        external_reference_column="external_reference",
        account_name_column="account_name",
        account_type_column="account_type",
        space_id_column="space_id",
        space_name_column="space_name",
        space_balance_column="space_balance",
        space_target_column="space_target",
        space_transactions_column="space_transactions",
        run_sync_on_startup=False,
        enable_manual_sync_endpoint=True,
    )


class StarlingProviderTests(unittest.TestCase):
    def test_fetch_transactions_discovers_accounts_and_normalizes_feed_items(self) -> None:
        provider = StarlingBankProvider(make_settings())
        responses = [
            FakeResponse(
                {
                    "accounts": [
                        {
                            "accountUid": "acc-1",
                            "defaultCategory": "cat-1",
                        }
                    ]
                }
            ),
            FakeResponse(
                {
                    "savingsGoalList": [
                        {
                            "savingsGoalUid": "space-1",
                            "name": "Holiday Fund",
                            "target": {"currency": "GBP", "minorUnits": 10000},
                            "totalSaved": {"currency": "GBP", "minorUnits": 2500},
                        }
                    ]
                }
            ),
            FakeResponse(
                {
                    "feedItems": [
                        {
                            "feedItemUid": "feed-1",
                            "transactionTime": "2026-03-30T08:30:00.000Z",
                            "direction": "OUT",
                            "reference": "Coffee shop",
                            "counterPartyName": "Coffee Shop",
                            "amount": {
                                "currency": "GBP",
                                "minorUnits": 450,
                            },
                        }
                    ]
                }
            ),
        ]

        with patch(
            "grist_finance_connector.providers.starling_provider.urlopen",
            side_effect=responses,
        ):
            result = provider.fetch_transactions(
                FetchWindow(
                    start=datetime(2026, 3, 29, tzinfo=UTC),
                    end=datetime(2026, 3, 30, tzinfo=UTC),
                    cursor=None,
                )
            )

        self.assertEqual(len(result.transactions), 1)
        transaction = result.transactions[0]
        self.assertEqual(transaction.external_id, "feed-1")
        self.assertEqual(transaction.account_id, "acc-1")
        self.assertEqual(transaction.currency, "GBP")
        self.assertEqual(str(transaction.amount), "-4.5")
        self.assertEqual(transaction.description, "Coffee Shop")
        self.assertEqual(len(result.accounts), 1)
        account = result.accounts[0]
        self.assertEqual(account.account_id, "acc-1")
        self.assertEqual(account.source_name, "starling_bank")
        self.assertEqual(len(result.spaces), 1)
        space = result.spaces[0]
        self.assertEqual(space.space_id, "space-1")
        self.assertEqual(space.space_name, "Holiday Fund")
        self.assertEqual(str(space.space_balance), "25")
        self.assertEqual(str(space.space_target), "100")

    def test_fetch_transactions_supports_multiple_tokens(self) -> None:
        settings = make_settings()
        settings = Settings(
            **{**settings.__dict__, "starling_access_token": "", "starling_access_tokens": ("token-a", "token-b")}
        )
        provider = StarlingBankProvider(settings)
        responses = [
            FakeResponse(
                {"accounts": [{"accountUid": "acc-1", "defaultCategory": "cat-1"}]}
            ),
            FakeResponse(
                {"accounts": [{"accountUid": "acc-2", "defaultCategory": "cat-2"}]}
            ),
            FakeResponse({"savingsGoalList": []}),
            FakeResponse({"feedItems": []}),
            FakeResponse({"savingsGoalList": []}),
            FakeResponse({"feedItems": []}),
        ]
        with patch(
            "grist_finance_connector.providers.starling_provider.urlopen",
            side_effect=responses,
        ):
            result = provider.fetch_transactions(
                FetchWindow(
                    start=datetime(2026, 3, 29, tzinfo=UTC),
                    end=datetime(2026, 3, 30, tzinfo=UTC),
                    cursor=None,
                )
            )

        self.assertEqual(sorted(account.account_id for account in result.accounts), ["acc-1", "acc-2"])


if __name__ == "__main__":
    unittest.main()
