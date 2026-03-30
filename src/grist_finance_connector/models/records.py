"""Domain models used by the connector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedTransaction:
    external_id: str
    source_name: str
    account_id: str
    transaction_date: date
    description: str
    amount: Decimal
    currency: str
    external_reference: str | None = None


@dataclass(frozen=True)
class NormalizedAccount:
    account_id: str
    source_name: str
    account_name: str
    currency: str
    account_type: str


@dataclass(frozen=True)
class NormalizedSpace:
    space_id: str
    account_id: str
    source_name: str
    space_name: str
    space_balance: Decimal
    space_target: Decimal
    space_transactions: int


@dataclass(frozen=True)
class ExistingTransaction:
    row_id: int
    external_id: str
    source_name: str


@dataclass(frozen=True)
class ExistingAccount:
    row_id: int
    account_id: str
    source_name: str


@dataclass(frozen=True)
class ExistingSpace:
    row_id: int
    space_id: str
    source_name: str


@dataclass(frozen=True)
class FetchWindow:
    start: datetime | None
    end: datetime | None
    cursor: str | None = None


@dataclass(frozen=True)
class ProviderFetchResult:
    accounts: list[NormalizedAccount]
    spaces: list[NormalizedSpace]
    transactions: list[NormalizedTransaction]
    next_cursor: str | None = None


@dataclass(frozen=True)
class SyncState:
    source_name: str
    last_successful_sync_at: datetime | None = None
    cursor: str | None = None


@dataclass(frozen=True)
class SyncJobResult:
    source_name: str
    fetched_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    success: bool
    started_at: datetime
    finished_at: datetime
    message: str = ""


@dataclass(frozen=True)
class WritePlan:
    to_insert: list[NormalizedTransaction]
    to_update: list[tuple[int, NormalizedTransaction]]
    skipped_count: int
    conflict_count: int
