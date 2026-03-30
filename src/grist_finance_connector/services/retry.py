"""Retry helpers for transient operational failures."""

from __future__ import annotations

import time
from typing import Callable
from typing import TypeVar
from urllib.error import HTTPError
from urllib.error import URLError


T = TypeVar("T")


def retry_call(fn: Callable[[], T], retries: int, backoff_ms: int) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except (TimeoutError, ConnectionError, URLError, HTTPError) as exc:
            attempt += 1
            if attempt > retries or isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                raise
            time.sleep((backoff_ms / 1000.0) * attempt)
