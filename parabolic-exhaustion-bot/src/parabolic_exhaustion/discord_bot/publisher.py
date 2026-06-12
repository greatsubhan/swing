from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import pandas as pd

from parabolic_exhaustion.config import DiscordConfig
from parabolic_exhaustion.discord_bot.formatter import AlertEvent, format_discord_message


class WebhookTransport(Protocol):
    async def post(self, url: str, json: dict[str, str]) -> object: ...


@dataclass(frozen=True)
class AlertDeliveryResult:
    delivered: bool
    deduplicated: bool
    status_code: int | None
    message: str


class HttpxWebhookTransport:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def post(self, url: str, json: dict[str, str]) -> httpx.Response:
        return await self._client.post(url, json=json)


class InMemoryAlertSink:
    def __init__(self) -> None:
        self.payloads: list[dict[str, str]] = []

    async def post(self, url: str, json: dict[str, str]) -> object:
        self.payloads.append(json)
        return type("Response", (), {"status_code": 204, "text": "ok"})()


class DiscordAlertPublisher:
    def __init__(
        self,
        *,
        config: DiscordConfig,
        transport: WebhookTransport | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or HttpxWebhookTransport()
        self.webhook_url = os.getenv(config.webhook_env_var, "")
        self.sent_keys: set[tuple[str, str]] = set()
        self.sent_timestamps: deque[pd.Timestamp] = deque()
        self.log_path = Path(log_path) if log_path is not None else None

    async def publish(self, event: AlertEvent) -> AlertDeliveryResult:
        key = (event.symbol, event.state, event.setup_id)
        if key in self.sent_keys:
            result = AlertDeliveryResult(
                delivered=False,
                deduplicated=True,
                status_code=None,
                message="duplicate alert suppressed",
            )
            self._append_log(event, result)
            return result

        await self._apply_rate_limit(pd.Timestamp(event.timestamp))
        if not self.config.enabled or not self.webhook_url:
            result = AlertDeliveryResult(
                delivered=False,
                deduplicated=False,
                status_code=None,
                message="webhook disabled or missing",
            )
            self._append_log(event, result)
            self.sent_keys.add(key)
            return result

        payload = format_discord_message(event)
        response = None
        error_message = ""
        for attempt in range(self.config.retry_attempts):
            try:
                response = await self.transport.post(self.webhook_url, payload)
                break
            except Exception as exc:  # pragma: no cover - defensive network path
                error_message = str(exc)
                if attempt + 1 < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_backoff_seconds)
        if response is None:
            result = AlertDeliveryResult(
                delivered=False,
                deduplicated=False,
                status_code=None,
                message=error_message or "webhook post failed",
            )
        else:
            status_code = getattr(response, "status_code", None)
            delivered = status_code is not None and 200 <= int(status_code) < 300
            result = AlertDeliveryResult(
                delivered=delivered,
                deduplicated=False,
                status_code=status_code,
                message=getattr(response, "text", ""),
            )

        self.sent_keys.add(key)
        self._append_log(event, result)
        return result

    async def _apply_rate_limit(self, timestamp: pd.Timestamp) -> None:
        window_start = timestamp - pd.Timedelta(minutes=1)
        while self.sent_timestamps and self.sent_timestamps[0] < window_start:
            self.sent_timestamps.popleft()
        if len(self.sent_timestamps) >= self.config.rate_limit_per_minute:
            sleep_for = (self.sent_timestamps[0] + pd.Timedelta(minutes=1) - timestamp).total_seconds()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            while self.sent_timestamps and self.sent_timestamps[0] < window_start:
                self.sent_timestamps.popleft()
        self.sent_timestamps.append(timestamp)

    def _append_log(self, event: AlertEvent, result: AlertDeliveryResult) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp(event.timestamp),
                    "symbol": event.symbol,
                    "state": event.state,
                    "delivered": result.delivered,
                    "deduplicated": result.deduplicated,
                    "status_code": result.status_code,
                    "message": result.message,
                }
            ]
        )
        header = not self.log_path.exists()
        frame.to_csv(self.log_path, mode="a", header=header, index=False)
