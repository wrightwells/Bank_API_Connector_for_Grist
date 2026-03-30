"""Minimal internal scheduler with cron-like matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class CronSchedule:
    minute: str
    hour: str
    day: str
    month: str
    weekday: str

    @classmethod
    def parse(cls, expr: str) -> "CronSchedule":
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError("Cron schedule must have 5 fields")
        return cls(*parts)

    def matches(self, dt: datetime) -> bool:
        return (
            _field_matches(self.minute, dt.minute)
            and _field_matches(self.hour, dt.hour)
            and _field_matches(self.day, dt.day)
            and _field_matches(self.month, dt.month)
            and _field_matches(self.weekday, dt.weekday())
        )


class SchedulerService:
    """Runs a single scheduled callback for the configured source."""

    def __init__(self, schedule_expr: str, callback: Callable[[], None]) -> None:
        self._schedule = CronSchedule.parse(schedule_expr)
        self._callback = callback
        self._stop = threading.Event()
        self._last_run_key: str | None = None

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run_forever, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()

    def _run_forever(self) -> None:
        while not self._stop.is_set():
            now = datetime.utcnow()
            run_key = now.strftime("%Y-%m-%dT%H:%M")
            if self._schedule.matches(now) and self._last_run_key != run_key:
                self._last_run_key = run_key
                self._callback()
            time.sleep(1)


def _field_matches(expr: str, value: int) -> bool:
    if expr == "*":
        return True
    if expr.startswith("*/"):
        step = int(expr[2:])
        return value % step == 0
    if "," in expr:
        return any(_field_matches(part.strip(), value) for part in expr.split(","))
    return int(expr) == value
