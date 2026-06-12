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
    is_tradable: bool = True
    structure_id: str | None = None
    root_signal_id: str | None = None
    reinforcement_count: int = 0
    strength_score: int | None = None
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
    total_realized_r: float = 0.0
    avg_closed_r: float | None = None

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
    is_root_signal: bool = True
    structure_id: str | None = None
    root_signal_id: str | None = None
    reinforcement_count_at_dispatch: int = 0
    strength_score_at_dispatch: int | None = None
    outcome: str | None = None
    outcome_timestamp: str | None = None
    exit_price: float | None = None
    outcome_notified: bool = False
    last_checked_utc: str | None = None
    bars_checked: int = 0
    ladder_sequence_pct: list[float] = field(default_factory=list)
    ladder_step_at_entry: int | None = None
    ladder_risk_pct_at_entry: float | None = None
    ladder_risk_display_at_entry: str | None = None
    ladder_previous_outcome: str | None = None
    ladder_previous_setup_id: str | None = None
    ladder_step_after_outcome: int | None = None
    ladder_next_risk_pct: float | None = None
    ladder_transition_note: str | None = None
    raw_signal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hold_hours(self) -> float | None:
        if not self.outcome_timestamp:
            return None
        start = datetime.fromisoformat(self.signal_timestamp.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.outcome_timestamp.replace("Z", "+00:00"))
        return (end - start).total_seconds() / 3600.0

    def realized_r(self) -> float | None:
        if self.status != "closed" or not self.outcome:
            return None
        if self.outcome == "tp_hit":
            return float(self.risk_reward or 0.0)
        if self.outcome == "sl_hit":
            return -1.0
        if self.outcome in {"break_even", "breakeven"}:
            return 0.0
        return 0.0


@dataclass
class SignalStructure:
    structure_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    side: str
    start_timestamp: str
    last_update_timestamp: str
    status: str
    root_signal_id: str
    reinforcement_count: int
    strength_score: int
    best_quality_score: int | None
    current_status: str
    entry: float | None
    stop_loss: float | None
    target_1: float | None
    last_signal_timestamp: str
    last_signal_id: str | None = None
    htf_alignment_active: bool = True
    effective_r_exposure: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReinforcementConfig:
    enabled: bool = False
    state_file: str | None = None
    decision_log_file: str | None = None
    base_strength_score: int = 50
    max_strength_score: int = 100
    quality_improvement_points: int = 5
    continuation_points: int = 5
    structure_holds_points: int = 3
    htf_alignment_points: int = 3
    enable_r_scaling: bool = False
    r_scale_per_reinforcement: float = 0.25
    max_effective_r_exposure: float = 2.0
    post_tp_cooldown_bars: int = 0
    post_sl_cooldown_bars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
