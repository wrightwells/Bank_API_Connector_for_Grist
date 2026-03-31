#!/usr/bin/env python3
"""Fetch and print normalized Starling transactions without writing to Grist.

Usage:
  python3 scripts/preview_starling_transactions.py --env-file .env
  python3 scripts/preview_starling_transactions.py --env-file .env --days 7 --limit 10
"""

from __future__ import annotations

import argparse
from datetime import UTC
from datetime import datetime
from datetime import timedelta
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grist_finance_connector.config.settings import load_settings  # noqa: E402
from grist_finance_connector.models.records import FetchWindow  # noqa: E402
from grist_finance_connector.providers.factory import build_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview normalized Starling transactions without pushing to Grist."
    )
    parser.add_argument(
        "--env-file",
        help="Env file to read settings from, for example .env",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="How many days of Starling transactions to request. Default: 7",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="How many normalized transactions to print. Default: 5",
    )
    args = parser.parse_args()

    if args.days <= 0:
        raise SystemExit("--days must be greater than zero")
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")

    if args.env_file:
        load_env_file(Path(args.env_file))

    settings = load_settings()
    if settings.source_provider != "starling":
        raise SystemExit("This helper requires SOURCE_PROVIDER=starling")

    provider = build_provider(settings)
    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)
    result = provider.fetch_transactions(FetchWindow(start=start, end=end, cursor=None))

    print(f"source_provider: {settings.source_provider}")
    print(f"source_name: {settings.source_name}")
    print(f"lookback_days: {args.days}")
    print(f"fetched_count: {len(result.transactions)}")
    print(f"showing_first: {min(args.limit, len(result.transactions))}")

    sample = result.transactions[: args.limit]
    serialized = [
        {
            "external_id": tx.external_id,
            "source_name": tx.source_name,
            "account_id": tx.account_id,
            "transaction_date": tx.transaction_date.isoformat(),
            "description": tx.description,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "external_reference": tx.external_reference,
        }
        for tx in sample
    ]
    print(json.dumps(serialized, indent=2))
    return 0


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Env file not found: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    raise SystemExit(main())
