"""Data models for signals and backtests."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TrendlinePoint:
    index: int
    price: float


@dataclass
class StructureInfo:
    impulse_start_index: int
    impulse_end_index: int
    pullback_start_index: int
    pullback_end_index: int
    anchor_low: Optional[float]
    anchor_high: Optional[float]
    trendline_points: List[TrendlinePoint]
    measured_distance: float
    projected_target: float


@dataclass
class BollingerContext:
    bb_length: int
    bb_stddev: float
    price_vs_mid: str
    pullback_band_location: str
    extension_state: str


@dataclass
class Signal:
    symbol: str
    asset_class: str
    timeframe: str
    higher_timeframe: str
    signal_type: str
    strategy: str
    trend_state: str
    setup_status: str
    timestamp: str
    entry: float
    stop_loss: float
    target_1: float
    target_2: Optional[float]
    invalidation_level: float
    risk_reward: float
    structure: StructureInfo
    bollinger_context: BollingerContext
    quality_score: int
    quality_grade: str
    trend_maturity: int
    alerts: List[str]
    reason_summary: str
    setup_id: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["structure"]["trendline_points"] = [asdict(p) for p in self.structure.trendline_points]
        return data


@dataclass
class SetupCandidate:
    side: str
    impulse_start: int
    impulse_end: int
    pullback_start: int
    pullback_end: int
    anchor_index: int
    entry_trigger: float
    stop: float
    target: float
    risk_reward: float
    validity_reason: str


@dataclass
class TradeResult:
    symbol: str
    timeframe: str
    side: str
    signal_time: str
    entry_time: str
    exit_time: str
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    pnl_r: float
    pnl_pct: float
    bars_held: int
    trend_maturity: int
    quality_score: int
    bollinger_context: str
    setup_id: str


@dataclass
class PerformanceSummary:
    trades: int
    win_rate: float
    avg_r: float
    expectancy_r: float
    max_drawdown_r: float
    profit_factor: float
    avg_hold_bars: float
    longs: int
    shorts: int
    by_symbol: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_timeframe: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_trend_maturity: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_bollinger_bucket: Dict[str, Dict[str, float]] = field(default_factory=dict)
