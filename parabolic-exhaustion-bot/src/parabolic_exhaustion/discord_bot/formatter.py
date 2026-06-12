from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    timestamp: pd.Timestamp
    state: str
    setup_id: str
    side: str
    reason: str
    entry_price: float | None = None
    stop_price: float | None = None
    first_target_price: float | None = None
    kill_zone_name: str | None = None
    alert_priority: str = "normal"


def format_discord_message(event: AlertEvent, *, timezone: str = "America/New_York") -> dict[str, str]:
    timestamp = pd.Timestamp(event.timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    local_time = timestamp.tz_convert(timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
    kill_zone_text = event.kill_zone_name or "outside kill zone"

    lines = [
        f"Symbol: {event.symbol}",
        f"Timestamp: {local_time}",
        f"State: {event.state}",
        f"Side: {event.side}",
        f"Entry: {_fmt_price(event.entry_price)}",
        f"Stop: {_fmt_price(event.stop_price)}",
        f"First Target: {_fmt_price(event.first_target_price)}",
        f"Kill Zone: {kill_zone_text}",
        f"Reason: {event.reason}",
    ]
    header = f"[{event.alert_priority.upper()}] {event.symbol} {event.state}"
    return {"content": header + "\n" + "\n".join(lines)}


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
