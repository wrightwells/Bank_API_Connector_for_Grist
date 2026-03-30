"""Runtime settings and validation for the connector service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_allowed(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip()
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        raise ValueError(f"Invalid value for {name}: {value}. Allowed values: {values}")
    return value


def _get_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    log_level: str
    service_host: str
    service_port: int
    scheduler_enabled: bool
    source_schedule: str
    source_enabled: bool
    source_provider: str
    source_name: str
    source_base_url: str
    source_transactions_path: str
    source_auth_method: str
    source_api_key: str
    source_api_key_header: str
    source_bearer_token: str
    starling_api_base_url: str
    starling_access_token: str
    starling_access_tokens: tuple[str, ...]
    starling_account_uid: str
    starling_account_uids: tuple[str, ...]
    source_timeout_ms: int
    retry_count: int
    retry_backoff_ms: int
    import_lookback_days: int
    duplicate_mode: str
    dry_run: bool
    batch_size: int
    state_db_path: str
    grist_base_url: str
    grist_doc_id: str
    grist_api_key: str
    grist_transactions_table: str
    grist_accounts_table: str
    grist_spaces_table: str
    grist_import_log_table: str
    external_id_column: str
    source_name_column: str
    transaction_date_column: str
    description_column: str
    amount_column: str
    currency_column: str
    account_id_column: str
    external_reference_column: str
    account_name_column: str
    account_type_column: str
    space_id_column: str
    space_name_column: str
    space_balance_column: str
    space_target_column: str
    space_transactions_column: str
    run_sync_on_startup: bool
    enable_manual_sync_endpoint: bool

    @property
    def state_db_parent(self) -> Path:
        return Path(self.state_db_path).expanduser().resolve().parent

    @property
    def effective_starling_access_tokens(self) -> tuple[str, ...]:
        if self.starling_access_tokens:
            return self.starling_access_tokens
        if self.starling_access_token:
            return (self.starling_access_token,)
        return ()

    @property
    def effective_starling_account_uids(self) -> tuple[str, ...]:
        if self.starling_account_uids:
            return self.starling_account_uids
        if self.starling_account_uid:
            return (self.starling_account_uid,)
        return ()


def load_settings() -> Settings:
    settings = Settings(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        service_host=os.getenv("SERVICE_HOST", "0.0.0.0"),
        service_port=_get_int("SERVICE_PORT", 8080),
        scheduler_enabled=_get_bool("SCHEDULER_ENABLED", True),
        source_schedule=os.getenv("SOURCE_SCHEDULE", "0 * * * *"),
        source_enabled=_get_bool("SOURCE_ENABLED", True),
        source_provider=_get_allowed(
            "SOURCE_PROVIDER", "generic_json", {"generic_json", "starling"}
        ),
        source_name=os.getenv("SOURCE_NAME", "example_provider"),
        source_base_url=os.getenv("SOURCE_BASE_URL", ""),
        source_transactions_path=os.getenv("SOURCE_TRANSACTIONS_PATH", "/transactions"),
        source_auth_method=_get_allowed(
            "SOURCE_AUTH_METHOD", "api_key", {"api_key", "bearer", "none"}
        ),
        source_api_key=os.getenv("SOURCE_API_KEY", ""),
        source_api_key_header=os.getenv("SOURCE_API_KEY_HEADER", "X-API-Key"),
        source_bearer_token=os.getenv("SOURCE_BEARER_TOKEN", ""),
        starling_api_base_url=os.getenv(
            "STARLING_API_BASE_URL", "https://api.starlingbank.com"
        ),
        starling_access_token=os.getenv("STARLING_ACCESS_TOKEN", ""),
        starling_access_tokens=_get_csv("STARLING_ACCESS_TOKENS"),
        starling_account_uid=os.getenv("STARLING_ACCOUNT_UID", ""),
        starling_account_uids=_get_csv("STARLING_ACCOUNT_UIDS"),
        source_timeout_ms=_get_int("API_TIMEOUT_MS", 15000),
        retry_count=_get_int("RETRY_COUNT", 3),
        retry_backoff_ms=_get_int("RETRY_BACKOFF_MS", 1000),
        import_lookback_days=_get_int("IMPORT_LOOKBACK_DAYS", 30),
        duplicate_mode=_get_allowed(
            "DUPLICATE_MODE",
            "skip_existing",
            {"skip_existing", "update_matching", "log_conflict_continue"},
        ),
        dry_run=_get_bool("DRY_RUN", False),
        batch_size=_get_int("BATCH_SIZE", 100),
        state_db_path=os.getenv("STATE_DB_PATH", "/data/state/connector.sqlite3"),
        grist_base_url=_get_required("GRIST_BASE_URL"),
        grist_doc_id=_get_required("GRIST_DOC_ID"),
        grist_api_key=_get_required("GRIST_API_KEY"),
        grist_transactions_table=os.getenv(
            "GRIST_TRANSACTIONS_TABLE", "Raw_Import_Transactions"
        ),
        grist_accounts_table=os.getenv("GRIST_ACCOUNTS_TABLE", "Accounts"),
        grist_spaces_table=os.getenv("GRIST_SPACES_TABLE", "Spaces"),
        grist_import_log_table=os.getenv("GRIST_IMPORT_LOG_TABLE", "Import_Log"),
        external_id_column=os.getenv("GRIST_EXTERNAL_ID_COLUMN", "external_id"),
        source_name_column=os.getenv("GRIST_SOURCE_COLUMN", "source_name"),
        transaction_date_column=os.getenv("GRIST_TRANSACTION_DATE_COLUMN", "transaction_date"),
        description_column=os.getenv("GRIST_DESCRIPTION_COLUMN", "description"),
        amount_column=os.getenv("GRIST_AMOUNT_COLUMN", "amount"),
        currency_column=os.getenv("GRIST_CURRENCY_COLUMN", "currency"),
        account_id_column=os.getenv("GRIST_ACCOUNT_ID_COLUMN", "account_id"),
        external_reference_column=os.getenv(
            "GRIST_EXTERNAL_REFERENCE_COLUMN", "external_reference"
        ),
        account_name_column=os.getenv("GRIST_ACCOUNT_NAME_COLUMN", "account_name"),
        account_type_column=os.getenv("GRIST_ACCOUNT_TYPE_COLUMN", "account_type"),
        space_id_column=os.getenv("GRIST_SPACE_ID_COLUMN", "space_id"),
        space_name_column=os.getenv("GRIST_SPACE_NAME_COLUMN", "space_name"),
        space_balance_column=os.getenv("GRIST_SPACE_BALANCE_COLUMN", "space_balance"),
        space_target_column=os.getenv("GRIST_SPACE_TARGET_COLUMN", "space_target"),
        space_transactions_column=os.getenv(
            "GRIST_SPACE_TRANSACTIONS_COLUMN", "space_transactions"
        ),
        run_sync_on_startup=_get_bool("RUN_SYNC_ON_STARTUP", False),
        enable_manual_sync_endpoint=_get_bool("ENABLE_MANUAL_SYNC_ENDPOINT", True),
    )
    _validate_settings(settings)
    return settings


def _validate_settings(settings: Settings) -> None:
    if settings.source_provider == "generic_json":
        if not settings.source_base_url:
            raise ValueError("SOURCE_BASE_URL is required when SOURCE_PROVIDER=generic_json")
        if settings.source_auth_method == "api_key" and not settings.source_api_key:
            raise ValueError("SOURCE_API_KEY is required when SOURCE_AUTH_METHOD=api_key")
        if settings.source_auth_method == "bearer" and not settings.source_bearer_token:
            raise ValueError("SOURCE_BEARER_TOKEN is required when SOURCE_AUTH_METHOD=bearer")
    if settings.source_provider == "starling" and not settings.effective_starling_access_tokens:
        raise ValueError(
            "STARLING_ACCESS_TOKEN or STARLING_ACCESS_TOKENS is required when SOURCE_PROVIDER=starling"
        )
    if settings.batch_size <= 0:
        raise ValueError("BATCH_SIZE must be greater than zero")
    if settings.import_lookback_days < 0:
        raise ValueError("IMPORT_LOOKBACK_DAYS cannot be negative")
    if settings.retry_count < 0:
        raise ValueError("RETRY_COUNT cannot be negative")
    if settings.retry_backoff_ms < 0:
        raise ValueError("RETRY_BACKOFF_MS cannot be negative")
    if settings.service_port <= 0:
        raise ValueError("SERVICE_PORT must be greater than zero")
