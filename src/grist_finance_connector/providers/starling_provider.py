"""Starling Bank provider adapter."""

from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
import json
import logging
from typing import Any
from urllib.parse import urlencode
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.models.records import FetchWindow
from grist_finance_connector.models.records import NormalizedAccount
from grist_finance_connector.models.records import NormalizedSpace
from grist_finance_connector.models.records import NormalizedTransaction
from grist_finance_connector.models.records import ProviderFetchResult
from grist_finance_connector.services.retry import retry_call


class StarlingBankProvider:
    """Fetches transactions from the Starling Bank public API."""

    def __init__(self, settings: Settings) -> None:
        self.name = settings.source_name or "starling_bank"
        self._settings = settings
        self._logger = logging.getLogger("grist_finance_connector.starling")

    def fetch_transactions(self, window: FetchWindow) -> ProviderFetchResult:
        selected_account_uids = set(self._settings.effective_starling_account_uids)
        discovered_accounts: dict[str, dict[str, Any]] = {}
        for token_index, access_token in enumerate(
            self._settings.effective_starling_access_tokens, start=1
        ):
            accounts = retry_call(
                fn=lambda access_token=access_token: self._fetch_accounts(access_token),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            self._logger.info(
                "starling token accounts discovered: token_index=%s account_count=%s account_uids=%s",
                token_index,
                len(accounts),
                [str(account.get("accountUid", "")) for account in accounts],
            )
            for account in accounts:
                account_uid = str(account.get("accountUid", ""))
                if account_uid and account_uid not in discovered_accounts:
                    discovered_accounts[account_uid] = account

        accounts = list(discovered_accounts.values())
        account_uids = [str(account.get("accountUid", "")) for account in accounts]
        self._logger.info(
            "starling accounts discovered: count=%s account_uids=%s selected_account_uids=%s",
            len(accounts),
            account_uids,
            list(selected_account_uids) if selected_account_uids else "<all>",
        )

        normalized_accounts = [self._normalize_account(account) for account in accounts]
        normalized_spaces: list[NormalizedSpace] = []
        transactions: list[NormalizedTransaction] = []
        for account in accounts:
            account_uid = str(account["accountUid"])
            if selected_account_uids and account_uid not in selected_account_uids:
                self._logger.info(
                    "starling account skipped by STARLING_ACCOUNT_UID filter: account_uid=%s",
                    account_uid,
                )
                continue
            access_token = self._required(account, "_access_token")
            savings_goals = retry_call(
                fn=lambda account_uid=account_uid, access_token=access_token: self._fetch_savings_goals(
                    account_uid, access_token
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            category_uid = str(account["defaultCategory"])
            payload = retry_call(
                fn=lambda account_uid=account_uid, category_uid=category_uid, access_token=access_token: self._fetch_feed_items(
                    account_uid, category_uid, window.start, window.end, access_token
                ),
                retries=self._settings.retry_count,
                backoff_ms=self._settings.retry_backoff_ms,
            )
            account_transactions = self._normalize_feed_items(account_uid, payload)
            normalized_spaces.extend(
                self._normalize_spaces(
                    account_uid=account_uid,
                    savings_goals=savings_goals,
                    transactions=account_transactions,
                )
            )
            self._logger.info(
                "starling account transactions fetched: account_uid=%s transaction_count=%s",
                account_uid,
                len(account_transactions),
            )
            transactions.extend(account_transactions)

        if selected_account_uids:
            normalized_accounts = [
                account
                for account in normalized_accounts
                if account.account_id in selected_account_uids
            ]

        return ProviderFetchResult(
            accounts=normalized_accounts,
            spaces=normalized_spaces,
            transactions=transactions,
            next_cursor=None,
        )

    def _fetch_accounts(self, access_token: str) -> list[dict[str, Any]]:
        payload = self._request_json("GET", self._url("/api/v2/accounts"), access_token)
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            raise ValueError("Starling accounts payload did not include an accounts list")
        for account in accounts:
            account["_access_token"] = access_token
        return accounts

    def _fetch_feed_items(
        self,
        account_uid: str,
        category_uid: str,
        start: datetime | None,
        end: datetime | None,
        access_token: str,
    ) -> dict[str, Any]:
        min_timestamp = (start or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        max_timestamp = (end or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        query = urlencode(
            {
                "minTransactionTimestamp": min_timestamp,
                "maxTransactionTimestamp": max_timestamp,
            }
        )
        url = self._url(
            f"/api/v2/feed/account/{quote(account_uid)}/category/{quote(category_uid)}/transactions-between?{query}"
        )
        payload = self._request_json("GET", url, access_token)
        if "feedItems" not in payload or not isinstance(payload["feedItems"], list):
            raise ValueError("Starling feed payload did not include feedItems")
        return payload

    def _fetch_savings_goals(self, account_uid: str, access_token: str) -> dict[str, Any]:
        url = self._url(f"/api/v2/account/{quote(account_uid)}/savings-goals")
        payload = self._request_json("GET", url, access_token)
        if "savingsGoalList" in payload and isinstance(payload["savingsGoalList"], list):
            return payload
        if "savingsGoals" in payload and isinstance(payload["savingsGoals"], list):
            return {"savingsGoalList": payload["savingsGoals"]}
        if "savingsGoalList" not in payload:
            return {"savingsGoalList": []}
        return payload

    def _normalize_feed_items(
        self, account_uid: str, payload: dict[str, Any]
    ) -> list[NormalizedTransaction]:
        items: list[NormalizedTransaction] = []
        for item in payload.get("feedItems", []):
            feed_item_uid = self._required(item, "feedItemUid")
            amount_info = self._required(item, "amount")
            if not isinstance(amount_info, dict):
                raise ValueError("Starling amount payload must be an object")
            minor_units = Decimal(str(self._required(amount_info, "minorUnits")))
            amount = minor_units / Decimal("100")
            if str(item.get("direction", "")).upper() == "OUT":
                amount = amount * Decimal("-1")

            timestamp_value = (
                item.get("transactionTime")
                or item.get("settlementTime")
                or item.get("updatedAt")
            )
            description = (
                item.get("counterPartyName")
                or item.get("reference")
                or item.get("spendingCategory")
                or "Starling transaction"
            )

            items.append(
                NormalizedTransaction(
                    external_id=str(feed_item_uid),
                    source_name=self.name,
                    account_id=account_uid,
                    transaction_date=self._parse_date(timestamp_value),
                    description=str(description),
                    amount=amount,
                    currency=str(amount_info.get("currency", "")),
                    external_reference=str(item.get("reference") or ""),
                )
            )
        return items

    def _normalize_spaces(
        self,
        account_uid: str,
        savings_goals: dict[str, Any],
        transactions: list[NormalizedTransaction],
    ) -> list[NormalizedSpace]:
        spaces: list[NormalizedSpace] = []
        goals = savings_goals.get("savingsGoalList", [])
        for goal in goals:
            space_id = str(
                goal.get("savingsGoalUid")
                or goal.get("uid")
                or goal.get("id")
                or ""
            )
            if not space_id:
                continue

            space_name = (
                str(goal.get("name", "")).strip()
                or str(goal.get("savingsGoalName", "")).strip()
                or space_id
            )
            space_balance = self._parse_minor_units_decimal(
                goal.get("totalSaved") or goal.get("savedAmount") or goal.get("balance")
            )
            space_target = self._parse_minor_units_decimal(
                goal.get("target") or goal.get("targetAmount")
            )
            space_transactions = self._count_space_transactions(space_id, transactions)

            spaces.append(
                NormalizedSpace(
                    space_id=space_id,
                    account_id=account_uid,
                    source_name=self.name,
                    space_name=space_name,
                    space_balance=space_balance,
                    space_target=space_target,
                    space_transactions=space_transactions,
                )
            )

        self._logger.info(
            "starling spaces fetched: account_uid=%s space_count=%s space_ids=%s",
            account_uid,
            len(spaces),
            [space.space_id for space in spaces],
        )
        return spaces

    def _normalize_account(self, account: dict[str, Any]) -> NormalizedAccount:
        account_uid = str(self._required(account, "accountUid"))
        currency = str(account.get("currency", ""))
        account_type = str(account.get("accountType", ""))
        account_name = (
            str(account.get("name", "")).strip()
            or str(account.get("accountType", "")).strip()
            or account_uid
        )
        return NormalizedAccount(
            account_id=account_uid,
            source_name=self.name,
            account_name=account_name,
            currency=currency,
            account_type=account_type,
        )

    def _request_json(self, method: str, url: str, access_token: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            method=method,
        )
        with urlopen(request, timeout=self._settings.source_timeout_ms / 1000) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    def _url(self, path: str) -> str:
        return self._settings.starling_api_base_url.rstrip("/") + path

    @staticmethod
    def _required(item: dict[str, Any], key: str) -> Any:
        if key not in item or item[key] in (None, ""):
            raise ValueError(f"Missing required Starling field: {key}")
        return item[key]

    @staticmethod
    def _parse_date(value: Any) -> date:
        if value in (None, ""):
            raise ValueError("Missing Starling transaction timestamp")
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).date()

    @staticmethod
    def _parse_minor_units_decimal(value: Any) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        if isinstance(value, dict):
            minor_units = value.get("minorUnits", 0)
            return Decimal(str(minor_units)) / Decimal("100")
        return Decimal(str(value)) / Decimal("100")

    @staticmethod
    def _count_space_transactions(
        space_id: str, transactions: list[NormalizedTransaction]
    ) -> int:
        count = 0
        for transaction in transactions:
            if transaction.external_reference and space_id in transaction.external_reference:
                count += 1
        return count
