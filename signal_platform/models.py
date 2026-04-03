"""Shared data models for the multi-strategy signal platform."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PlatformSignal:
    strategy_id: str
    strategy_name: str
    symbol: str
    asset_class: str
    timeframe: str
    side: str
    timestamp: str
    setup_id: str
    summary: str
    alert_text: str
    quality_score: int | None = None
    quality_grade: str | None = None
    risk_reward: float | None = None
    entry: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    raw_signal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    strategy_id: str
    strategy_name: str
    watchlist: str
    signals: list[PlatformSignal]
    rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "watchlist": self.watchlist,
            "signals": [signal.to_dict() for signal in self.signals],
            "rows": self.rows,
        }


@dataclass
class SignalStatsSnapshot:
    total_signals: int
    closed_signals: int
    open_signals: int
    tp_hits: int
    sl_hits: int
    other_closures: int
    win_rate: float
    avg_hold_hours: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JournalEntry:
    strategy_id: str
    strategy_name: str
    setup_id: str
    symbol: str
    asset_class: str
    timeframe: str
    side: str
    signal_timestamp: str
    dispatched_at_utc: str
    entry: float
    stop_loss: float
    target_1: float
    risk_reward: float | None
    quality_score: int | None
    quality_grade: str | None
    status: str
    outcome: str | None = None
    outcome_timestamp: str | None = None
    exit_price: float | None = None
    outcome_notified: bool = False
    last_checked_utc: str | None = None
    bars_checked: int = 0
    raw_signal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hold_hours(self) -> float | None:
        if not self.outcome_timestamp:
            return None
        start = datetime.fromisoformat(self.signal_timestamp.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.outcome_timestamp.replace("Z", "+00:00"))
        return (end - start).total_seconds() / 3600.0
