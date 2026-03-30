"""Application entrypoint for the connector service."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.config.settings import load_settings
from grist_finance_connector.grist.client import GristClient
from grist_finance_connector.logging.setup import configure_logging
from grist_finance_connector.providers.factory import build_provider
from grist_finance_connector.scheduler.service import SchedulerService
from grist_finance_connector.services.sync import SyncService
from grist_finance_connector.state.store import StateStore


class ConnectorApplication:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = configure_logging(settings.log_level)
        settings.state_db_parent.mkdir(parents=True, exist_ok=True)
        self.state_store = StateStore(settings.state_db_path)
        self.provider = build_provider(settings)
        self.grist_client = GristClient(settings)
        self.sync_service = SyncService(
            settings=settings,
            provider=self.provider,
            grist_client=self.grist_client,
            state_store=self.state_store,
            logger=self.logger,
        )
        self._scheduler: SchedulerService | None = None

    def run_sync(self) -> dict[str, Any]:
        result = self.sync_service.run(self.settings.source_name)
        return {
            "source_name": result.source_name,
            "success": result.success,
            "fetched_count": result.fetched_count,
            "inserted_count": result.inserted_count,
            "updated_count": result.updated_count,
            "skipped_count": result.skipped_count,
            "failed_count": result.failed_count,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat(),
            "message": result.message,
            "dry_run": self.settings.dry_run,
        }

    def health_payload(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "source_enabled": self.settings.source_enabled,
            "dry_run": self.settings.dry_run,
            "scheduler_enabled": self.settings.scheduler_enabled,
            "source_provider": self.settings.source_provider,
            "state_db_path": self.settings.state_db_path,
            "recent_jobs": self.state_store.recent_jobs(limit=5),
        }

    def start_scheduler(self) -> threading.Thread | None:
        if not self.settings.scheduler_enabled or not self.settings.source_enabled:
            return None

        self._scheduler = SchedulerService(
            self.settings.source_schedule,
            callback=lambda: self.run_sync(),
        )
        return self._scheduler.start()

    def stop_scheduler(self) -> None:
        if self._scheduler is not None:
            self._scheduler.stop()


def main() -> int:
    settings = load_settings()
    app = ConnectorApplication(settings)
    app.logger.info(
        "connector service starting",
        extra={
            "source_name": settings.source_name,
            "source_provider": settings.source_provider,
            "scheduler_enabled": settings.scheduler_enabled,
            "dry_run": settings.dry_run,
        },
    )

    if settings.run_sync_on_startup and settings.source_enabled:
        app.run_sync()

    app.start_scheduler()
    httpd = ThreadingHTTPServer((settings.service_host, settings.service_port), _handler(app))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop_scheduler()
        httpd.server_close()
    return 0


def _handler(app: ConnectorApplication):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write_json(HTTPStatus.OK, app.health_payload())
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/sync" and app.settings.enable_manual_sync_endpoint:
                payload = app.run_sync()
                status = HTTPStatus.OK if payload["success"] else HTTPStatus.BAD_GATEWAY
                self._write_json(status, payload)
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            app.logger.info(format, *args)

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


if __name__ == "__main__":
    raise SystemExit(main())
