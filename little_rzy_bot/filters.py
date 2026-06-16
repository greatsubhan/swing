"""Session and pre-dispatch filters for Little RZY variants."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from .config import EngineConfig
from .data_models import Signal


def session_tags(timestamp: str) -> set[str]:
    """Return normalized session tags for a UTC timestamp."""
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
    hour = dt.hour

    tags: set[str] = set()
    if 0 <= hour < 7:
        tags.add("asia")
    if 7 <= hour < 16:
        tags.add("london")
    if 12 <= hour < 21:
        tags.add("new_york")
    if 12 <= hour < 16:
        tags.add("london_new_york")
    if not tags:
        tags.add("off_hours")
    return tags


def primary_session(timestamp: str) -> str:
    tags = session_tags(timestamp)
    if "london_new_york" in tags:
        return "london_new_york"
    if "london" in tags:
        return "london"
    if "new_york" in tags:
        return "new_york"
    if "asia" in tags:
        return "asia"
    return "off_hours"


def filter_signal(signal: Signal, cfg: EngineConfig) -> list[str]:
    """Return a list of filter reasons for a signal; empty means the signal passes."""
    reasons: list[str] = []
    allowed_sessions = set(cfg.execution.allowed_sessions)
    if allowed_sessions and signal.session:
        if not (session_tags(signal.timestamp) & allowed_sessions):
            reasons.append("session")

    spread = cfg.risk.spread_points
    if spread > 0 and signal.atr_at_entry is not None and cfg.execution.min_atr_to_spread_ratio > 0:
        if (signal.atr_at_entry / spread) < cfg.execution.min_atr_to_spread_ratio:
            reasons.append("volatility_atr")

    if spread > 0 and signal.bar_range_at_entry is not None and cfg.execution.min_bar_range_to_spread_ratio > 0:
        if (signal.bar_range_at_entry / spread) < cfg.execution.min_bar_range_to_spread_ratio:
            reasons.append("volatility_range")

    return reasons


def filter_signals(signals: Iterable[Signal], cfg: EngineConfig) -> tuple[list[Signal], list[tuple[Signal, list[str]]]]:
    passed: list[Signal] = []
    filtered: list[tuple[Signal, list[str]]] = []
    for signal in signals:
        reasons = filter_signal(signal, cfg)
        if reasons:
            filtered.append((signal, reasons))
        else:
            passed.append(signal)
    return passed, filtered
