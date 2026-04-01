"""Configuration models for Little RZY signal engine."""
from dataclasses import dataclass, field


@dataclass
class IndicatorConfig:
    atr_length: int = 14
    bb_length: int = 20
    bb_stddev: float = 2.0
    ema_fast: int = 20
    ema_slow: int = 50
    adx_length: int = 14


@dataclass
class PivotConfig:
    left_bars: int = 2
    right_bars: int = 2


@dataclass
class TrendConfig:
    min_ma_slope: float = 0.0
    min_adx: float = 18.0
    min_hhhl_count: int = 2


@dataclass
class StructureConfig:
    min_impulse_atr: float = 1.8
    min_impulse_bars: int = 3
    max_impulse_bars: int = 25
    pullback_min_retrace: float = 0.25
    pullback_max_retrace: float = 0.65
    pullback_min_bars: int = 2
    pullback_max_bars: int = 12
    max_setup_age_bars: int = 10
    trendline_max_abs_slope: float = 3.0
    trendline_min_touches: int = 2


@dataclass
class RiskConfig:
    atr_stop_padding: float = 0.25
    min_rr: float = 1.2
    fee_bps: float = 2.0
    slippage_bps: float = 3.0
    stop_priority_when_both_hit: bool = True


@dataclass
class ScoreWeights:
    trend_clarity: int = 15
    impulse_quality: int = 15
    pullback_cleanliness: int = 12
    trendline_quality: int = 12
    bollinger_context: int = 10
    trend_maturity: int = 10
    rr_quality: int = 12
    regime_suitability: int = 8
    freshness: int = 6


@dataclass
class EngineConfig:
    strategy_name: str = "Little RZY"
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    pivots: PivotConfig = field(default_factory=PivotConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    entry_on_break_of_prior_bar: bool = True
    require_confirmed_candle: bool = True
