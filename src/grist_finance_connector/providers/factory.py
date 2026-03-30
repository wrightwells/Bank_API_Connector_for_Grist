"""Provider construction helpers."""

from __future__ import annotations

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.providers.base import ProviderAdapter
from grist_finance_connector.providers.json_provider import JsonApiProvider
from grist_finance_connector.providers.starling_provider import StarlingBankProvider


def build_provider(settings: Settings) -> ProviderAdapter:
    if settings.source_provider == "starling":
        return StarlingBankProvider(settings)
    return JsonApiProvider(settings)
