"""Provider adapter interfaces."""

from __future__ import annotations

from typing import Protocol

from grist_finance_connector.models.records import FetchWindow
from grist_finance_connector.models.records import ProviderFetchResult


class ProviderAdapter(Protocol):
    name: str

    def fetch_transactions(self, window: FetchWindow) -> ProviderFetchResult:
        """Return normalized accounts and transactions for the requested window."""
