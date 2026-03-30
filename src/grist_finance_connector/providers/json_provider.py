"""Generic JSON-over-HTTP provider adapter."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from decimal import Decimal
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.models.records import FetchWindow
from grist_finance_connector.models.records import NormalizedTransaction
from grist_finance_connector.models.records import ProviderFetchResult
from grist_finance_connector.services.retry import retry_call


class JsonApiProvider:
    """Fetches transaction records from a configurable JSON HTTP endpoint.

    Expected response body shapes:
    - {"transactions": [...], "next_cursor": "..."}
    - {"data": [...], "next_cursor": "..."}
    - [...]
    """

    def __init__(self, settings: Settings) -> None:
        self.name = settings.source_name
        self._settings = settings

    def fetch_transactions(self, window: FetchWindow) -> ProviderFetchResult:
        transactions: list[NormalizedTransaction] = []
        cursor = window.cursor

        while True:
            payload = retry_call(
                fn=lambda: self._fetch_page(window.start, window.end, cursor),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            items = self._extract_items(payload)
            transactions.extend(self._normalize_items(items))
            cursor = self._extract_next_cursor(payload)
            if not cursor:
                break

        return ProviderFetchResult(
            accounts=[],
            spaces=[],
            transactions=transactions,
            next_cursor=cursor,
        )

    def _fetch_page(
        self, start: datetime | None, end: datetime | None, cursor: str | None
    ) -> Any:
        params: dict[str, str] = {}
        if start is not None:
            params["from"] = start.isoformat()
        if end is not None:
            params["to"] = end.isoformat()
        if cursor:
            params["cursor"] = cursor

        url = self._settings.source_base_url.rstrip("/") + self._settings.source_transactions_path
        if params:
            url = f"{url}?{urlencode(params)}"

        request = Request(url, headers=self._build_headers(), method="GET")
        with urlopen(request, timeout=self._settings.source_timeout_ms / 1000) as response:
            body = response.read().decode("utf-8")
        return json.loads(body)

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._settings.source_auth_method == "api_key":
            headers[self._settings.source_api_key_header] = self._settings.source_api_key
        elif self._settings.source_auth_method == "bearer":
            headers["Authorization"] = f"Bearer {self._settings.source_bearer_token}"
        return headers

    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("transactions"), list):
                return payload["transactions"]
            if isinstance(payload.get("data"), list):
                return payload["data"]
        raise ValueError("Source payload does not contain a transaction list")

    @staticmethod
    def _extract_next_cursor(payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ("next_cursor", "nextCursor", "cursor"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
        return None

    def _normalize_items(self, items: list[dict[str, Any]]) -> list[NormalizedTransaction]:
        normalized: list[NormalizedTransaction] = []
        for item in items:
            normalized.append(
                NormalizedTransaction(
                    external_id=str(self._required(item, "external_id", "id")),
                    source_name=self.name,
                    account_id=str(self._required(item, "account_id", "account")),
                    transaction_date=self._parse_date(
                        self._required(item, "transaction_date", "date")
                    ),
                    description=str(self._required(item, "description", "name", "merchant")),
                    amount=Decimal(str(self._required(item, "amount"))),
                    currency=str(self._required(item, "currency")),
                    external_reference=self._optional(
                        item, "external_reference", "reference", "ref"
                    ),
                )
            )
        return normalized

    @staticmethod
    def _required(item: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in item and item[key] not in (None, ""):
                return item[key]
        joined = ", ".join(keys)
        raise ValueError(f"Missing required transaction field. Tried keys: {joined}")

    @staticmethod
    def _optional(item: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            if key in item and item[key] not in (None, ""):
                return str(item[key])
        return None

    @staticmethod
    def _parse_date(value: Any) -> date:
        text = str(value)
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text)
