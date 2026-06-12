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
    max_trend_maturity: int = 99


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
    trendline_touch_tolerance_atr: float = 0.35
    max_breakout_bars_after_pullback: int = 3


@dataclass
class RiskConfig:
    atr_stop_padding: float = 0.25
    min_rr: float = 1.2
    stop_priority_when_both_hit: bool = True
    commission_per_trade: float = 0.0
    spread_points: float = 0.0
    slippage_points: float = 0.0


@dataclass
class PortfolioConstraintConfig:
    max_open_risk: float | None = None
    max_trades_per_day: int | None = None
    max_trades_per_symbol_per_day: int | None = None
    max_daily_drawdown: float | None = None
    allow_partial_size: bool = True


@dataclass
class ExecutionFilterConfig:
    allowed_sessions: tuple[str, ...] = ()
    min_atr_to_spread_ratio: float = 0.0
    min_bar_range_to_spread_ratio: float = 0.0
    use_htf_bias: bool = False
    htf_granularity: str = "1d"
    log_signals: bool = False
    log_filtered_setups: bool = False


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
    profile_name: str = "baseline"
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    pivots: PivotConfig = field(default_factory=PivotConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    portfolio: PortfolioConstraintConfig = field(default_factory=PortfolioConstraintConfig)
    execution: ExecutionFilterConfig = field(default_factory=ExecutionFilterConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    entry_on_break_of_prior_bar: bool = True
    require_confirmed_candle: bool = True
    require_higher_timeframe_confirmation: bool = False
    require_rejection_candle: bool = False
