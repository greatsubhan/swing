"""Shared data models for the multi-strategy signal platform."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
