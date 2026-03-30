#!/usr/bin/env python3
"""Print Starling account UIDs safely from Starling access tokens in the environment.

Usage:
  STARLING_ACCESS_TOKEN=... python3 scripts/print_starling_accounts.py
  python3 scripts/print_starling_accounts.py --env-file .env.starling
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request
from urllib.request import urlopen


DEFAULT_API_BASE_URL = "https://api.starlingbank.com"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print Starling accountUid values from the Starling accounts API."
    )
    parser.add_argument(
        "--env-file",
        help="Optional env file to read STARLING_ACCESS_TOKEN and STARLING_API_BASE_URL from.",
    )
    args = parser.parse_args()

    if args.env_file:
        load_env_file(Path(args.env_file))

    access_tokens = get_access_tokens()
    if not access_tokens:
        raise SystemExit(
            "Missing STARLING_ACCESS_TOKEN or STARLING_ACCESS_TOKENS. Set one in the environment or provide --env-file."
        )

    api_base_url = os.getenv("STARLING_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    for token_index, access_token in enumerate(access_tokens, start=1):
        payload = fetch_accounts(api_base_url, access_token)
        print_accounts(payload, token_index)
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


def fetch_accounts(api_base_url: str, access_token: str) -> dict[str, Any]:
    url = f"{api_base_url}/api/v2/accounts"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="GET",
    )
    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def get_access_tokens() -> tuple[str, ...]:
    raw_many = os.getenv("STARLING_ACCESS_TOKENS", "").strip()
    if raw_many:
        tokens = tuple(part.strip() for part in raw_many.split(",") if part.strip())
        if tokens:
            return tokens
    raw_one = os.getenv("STARLING_ACCESS_TOKEN", "").strip()
    if raw_one:
        return (raw_one,)
    return ()


def print_accounts(payload: dict[str, Any], token_index: int) -> None:
    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        raise SystemExit("Starling API response did not include an accounts list.")

    if not accounts:
        print(f"Token {token_index}: no Starling accounts were returned by the API.")
        return

    print(f"Token {token_index}")
    for index, account in enumerate(accounts, start=1):
        account_uid = account.get("accountUid", "")
        account_type = account.get("accountType", "")
        default_category = account.get("defaultCategory", "")
        currency = account.get("currency", "")

        print(f"Account {index}")
        print(f"  accountUid: {account_uid}")
        print(f"  accountType: {account_type}")
        print(f"  defaultCategory: {default_category}")
        print(f"  currency: {currency}")


if __name__ == "__main__":
    raise SystemExit(main())
