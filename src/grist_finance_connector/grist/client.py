"""Grist REST API client."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.models.records import ExistingAccount
from grist_finance_connector.models.records import ExistingSpace
from grist_finance_connector.models.records import ExistingTransaction
from grist_finance_connector.models.records import NormalizedAccount
from grist_finance_connector.models.records import NormalizedSpace
from grist_finance_connector.models.records import NormalizedTransaction
from grist_finance_connector.services.retry import retry_call


@dataclass(frozen=True)
class GristTarget:
    base_url: str
    document_id: str
    accounts_table: str
    spaces_table: str
    transactions_table: str
    import_log_table: str


class GristClient:
    """Encapsulates Grist reads and writes through the REST API only."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.target = GristTarget(
            base_url=settings.grist_base_url.rstrip("/"),
            document_id=settings.grist_doc_id,
            accounts_table=settings.grist_accounts_table,
            spaces_table=settings.grist_spaces_table,
            transactions_table=settings.grist_transactions_table,
            import_log_table=settings.grist_import_log_table,
        )

    def healthcheck(self) -> bool:
        response = self._request("GET", self._doc_url())
        return isinstance(response, dict)

    def get_existing_transactions(
        self, source_name: str, external_ids: set[str]
    ) -> dict[str, ExistingTransaction]:
        if not external_ids:
            return {}

        response = self._request("GET", self._table_records_url(self.target.transactions_table))
        records = response.get("records", [])
        existing: dict[str, ExistingTransaction] = {}
        for record in records:
            fields = record.get("fields", {})
            if fields.get(self._settings.source_name_column) != source_name:
                continue
            external_id = fields.get(self._settings.external_id_column)
            if external_id in external_ids:
                existing[str(external_id)] = ExistingTransaction(
                    row_id=int(record["id"]),
                    external_id=str(external_id),
                    source_name=str(fields.get(self._settings.source_name_column, source_name)),
                )
        return existing

    def get_existing_accounts(
        self, source_name: str, account_ids: set[str]
    ) -> dict[str, ExistingAccount]:
        if not account_ids:
            return {}

        response = self._request("GET", self._table_records_url(self.target.accounts_table))
        records = response.get("records", [])
        existing: dict[str, ExistingAccount] = {}
        for record in records:
            fields = record.get("fields", {})
            if fields.get(self._settings.source_name_column) != source_name:
                continue
            account_id = fields.get(self._settings.account_id_column)
            if account_id in account_ids:
                existing[str(account_id)] = ExistingAccount(
                    row_id=int(record["id"]),
                    account_id=str(account_id),
                    source_name=str(fields.get(self._settings.source_name_column, source_name)),
                )
        return existing

    def insert_accounts(self, accounts: list[NormalizedAccount]) -> int:
        if not accounts:
            return 0
        inserted = 0
        for batch in self._batch(accounts):
            payload = {"records": [{"fields": self._to_account_fields(account)} for account in batch]}
            retry_call(
                fn=lambda payload=payload: self._request(
                    "POST",
                    self._table_records_url(self.target.accounts_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            inserted += len(batch)
        return inserted

    def update_accounts(self, rows: list[tuple[int, NormalizedAccount]]) -> int:
        if not rows:
            return 0
        updated = 0
        for batch in self._batch(rows):
            payload = {
                "records": [
                    {"id": row_id, "fields": self._to_account_fields(account)}
                    for row_id, account in batch
                ]
            }
            retry_call(
                fn=lambda payload=payload: self._request(
                    "PATCH",
                    self._table_records_url(self.target.accounts_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            updated += len(batch)
        return updated

    def get_existing_spaces(
        self, source_name: str, space_ids: set[str]
    ) -> dict[str, ExistingSpace]:
        if not space_ids:
            return {}

        response = self._request("GET", self._table_records_url(self.target.spaces_table))
        records = response.get("records", [])
        existing: dict[str, ExistingSpace] = {}
        for record in records:
            fields = record.get("fields", {})
            if fields.get(self._settings.source_name_column) != source_name:
                continue
            space_id = fields.get(self._settings.space_id_column)
            if space_id in space_ids:
                existing[str(space_id)] = ExistingSpace(
                    row_id=int(record["id"]),
                    space_id=str(space_id),
                    source_name=str(fields.get(self._settings.source_name_column, source_name)),
                )
        return existing

    def insert_spaces(self, spaces: list[NormalizedSpace]) -> int:
        if not spaces:
            return 0
        inserted = 0
        for batch in self._batch(spaces):
            payload = {"records": [{"fields": self._to_space_fields(space)} for space in batch]}
            retry_call(
                fn=lambda payload=payload: self._request(
                    "POST",
                    self._table_records_url(self.target.spaces_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            inserted += len(batch)
        return inserted

    def update_spaces(self, rows: list[tuple[int, NormalizedSpace]]) -> int:
        if not rows:
            return 0
        updated = 0
        for batch in self._batch(rows):
            payload = {
                "records": [
                    {"id": row_id, "fields": self._to_space_fields(space)}
                    for row_id, space in batch
                ]
            }
            retry_call(
                fn=lambda payload=payload: self._request(
                    "PATCH",
                    self._table_records_url(self.target.spaces_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            updated += len(batch)
        return updated

    def insert_transactions(self, transactions: list[NormalizedTransaction]) -> int:
        if not transactions:
            return 0
        batches = self._batch(transactions)
        inserted = 0
        for batch in batches:
            payload = {"records": [{"fields": self._to_fields(tx)} for tx in batch]}
            retry_call(
                fn=lambda payload=payload: self._request(
                    "POST",
                    self._table_records_url(self.target.transactions_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            inserted += len(batch)
        return inserted

    def update_transactions(
        self, rows: list[tuple[int, NormalizedTransaction]]
    ) -> int:
        if not rows:
            return 0
        updated = 0
        for batch in self._batch(rows):
            payload = {
                "records": [
                    {"id": row_id, "fields": self._to_fields(transaction)}
                    for row_id, transaction in batch
                ]
            }
            retry_call(
                fn=lambda payload=payload: self._request(
                    "PATCH",
                    self._table_records_url(self.target.transactions_table),
                    payload,
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            updated += len(batch)
        return updated

    def append_import_log(self, fields: dict[str, Any]) -> None:
        payload = {"records": [{"fields": fields}]}
        try:
            self._request("POST", self._table_records_url(self.target.import_log_table), payload)
        except HTTPError:
            # Import log failures should not hide the primary sync result.
            return

    def _batch(self, items: list[Any]) -> list[list[Any]]:
        size = self._settings.batch_size
        return [items[index : index + size] for index in range(0, len(items), size)]

    def _to_fields(self, transaction: NormalizedTransaction) -> dict[str, Any]:
        return {
            self._settings.external_id_column: transaction.external_id,
            self._settings.source_name_column: transaction.source_name,
            self._settings.transaction_date_column: transaction.transaction_date.isoformat(),
            self._settings.description_column: transaction.description,
            self._settings.amount_column: str(transaction.amount),
            self._settings.currency_column: transaction.currency,
            self._settings.account_id_column: transaction.account_id,
            self._settings.external_reference_column: transaction.external_reference or "",
        }

    def _to_account_fields(self, account: NormalizedAccount) -> dict[str, Any]:
        return {
            self._settings.account_id_column: account.account_id,
            self._settings.source_name_column: account.source_name,
            self._settings.account_name_column: account.account_name,
            self._settings.currency_column: account.currency,
            self._settings.account_type_column: account.account_type,
        }

    def _to_space_fields(self, space: NormalizedSpace) -> dict[str, Any]:
        return {
            self._settings.space_id_column: space.space_id,
            self._settings.account_id_column: space.account_id,
            self._settings.source_name_column: space.source_name,
            self._settings.space_name_column: space.space_name,
            self._settings.space_balance_column: str(space.space_balance),
            self._settings.space_target_column: str(space.space_target),
            self._settings.space_transactions_column: space.space_transactions,
        }

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._settings.grist_api_key}",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method)
        with urlopen(request, timeout=self._settings.source_timeout_ms / 1000) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    def _doc_url(self) -> str:
        return f"{self.target.base_url}/api/docs/{quote(self.target.document_id)}"

    def _table_records_url(self, table_name: str) -> str:
        return (
            f"{self.target.base_url}/api/docs/{quote(self.target.document_id)}"
            f"/tables/{quote(table_name)}/records"
        )
