from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, PositiveInt


ExtensionMode = Literal["atr_multiple", "points", "pct_from_base", "distance_from_sma20_pct"]
SessionScope = Literal["london", "new_york", "london_new_york", "full_24h"]
StrategyType = Literal["parabolic_exhaustion", "flow_strategy"]


class SessionWindowConfig(BaseModel):
    timezone: str
    start_time: str
    end_time: str


class KillZoneWindowConfig(BaseModel):
    enabled: bool = True
    start_time: str
    end_time: str


class KillZonesConfig(BaseModel):
    timezone: str = "America/New_York"
    prioritize_overlap: bool = True
    default_alert_priority: Literal["normal", "high"] = "normal"
    overlap_alert_priority: Literal["normal", "high"] = "high"
    overlap: KillZoneWindowConfig = Field(
        default_factory=lambda: KillZoneWindowConfig(
            enabled=True,
            start_time="08:00",
            end_time="10:00",
        )
    )
    london: KillZoneWindowConfig = Field(
        default_factory=lambda: KillZoneWindowConfig(
            enabled=True,
            start_time="02:00",
            end_time="05:00",
        )
    )
    new_york: KillZoneWindowConfig = Field(
        default_factory=lambda: KillZoneWindowConfig(
            enabled=True,
            start_time="07:00",
            end_time="10:00",
        )
    )


class ExtensionFilterConfig(BaseModel):
    mode: ExtensionMode = "atr_multiple"
    min_value: float = 3.0
    per_symbol_overrides: dict[str, float] = Field(default_factory=dict)


class FiltersConfig(BaseModel):
    extension: ExtensionFilterConfig = Field(default_factory=ExtensionFilterConfig)
    volume_rank_min: float = 0.7
    round_number_tolerance_pct: float = 0.75
    min_parabolic_slope_score: float = 55.0
    near_high_threshold_pct: float = 1.5


class IntradayRulesConfig(BaseModel):
    require_lower_high: bool = True
    require_lower_low: bool = True
    require_vwap_loss: bool = True
    require_vwap_reclaim_failure: bool = True
    vwap_retest_max_count: PositiveInt = 2


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = 0.5
    partial_take_r: float = 1.5
    partial_take_size_pct: float = 40.0
    move_stop_to_break_even_after_partial: bool = True
    enable_risk_free_add: bool = True
    add_only_after_second_vwap_failure: bool = True


class FlowStrategyConfig(BaseModel):
    markets: list[str] = Field(default_factory=lambda: ["NAS100_USD", "US30_USD"])
    daily_context_timeframe: str = "1d"
    signal_timeframe: str = "M5"
    opening_window_timezone: str = "America/New_York"
    opening_window_variant: str = "open_0930_1030"
    opening_windows: dict[str, SessionWindowConfig] = Field(
        default_factory=lambda: {
            "open_0930_1030": SessionWindowConfig(
                timezone="America/New_York",
                start_time="09:30",
                end_time="10:30",
            ),
            "open_0935_1030": SessionWindowConfig(
                timezone="America/New_York",
                start_time="09:35",
                end_time="10:30",
            ),
            "open_0945_1030": SessionWindowConfig(
                timezone="America/New_York",
                start_time="09:45",
                end_time="10:30",
            ),
            "open_1000_1100": SessionWindowConfig(
                timezone="America/New_York",
                start_time="10:00",
                end_time="11:00",
            ),
        }
    )
    ema_fast_length: PositiveInt = 9
    ema_slow_length: PositiveInt = 21
    intraday_atr_length: PositiveInt = 14
    vwap_slope_lookback: PositiveInt = 3
    pullback_lookback: PositiveInt = 3
    stop_lookback_bars: PositiveInt = 3
    min_daily_atr_pct: float = 0.60
    min_vwap_slope_atr: float = 0.03
    pullback_distance_atr: float = 0.35
    max_extension_atr: float = 1.25
    stop_atr_buffer: float = 0.75
    max_trades_per_day: PositiveInt = 2
    use_kill_zones: bool = True
    allow_longs: bool = True
    allow_shorts: bool = True
    require_session_alignment: bool = True


class PaperProfileConfig(BaseModel):
    strategy_type: StrategyType = "parabolic_exhaustion"
    markets: list[str] = Field(default_factory=lambda: ["NAS100_USD"])
    parameter_set_id: str = "idx_ps07_baseline_on"
    discord_webhook_env_var: str = "DISCORD_WEBHOOK_URL_NAS100_PARABOLIC_PAPER"
    discord_channel_name: str = "nas100-parabolic-paper"
    output_subdir: str = "nas100_parabolic_paper"
    forward_test_log_filename: str = "forward_test_log_parabolic.csv"
    session_timezone: str = "America/New_York"


class StrategyConfig(BaseModel):
    provider: Literal["oanda"] = "oanda"
    market_scope: Literal["multi_asset"] = "multi_asset"
    session_scope: SessionScope = "london_new_york"
    daily_context_timeframe: str = "1d"
    intraday_timeframes: list[str] = Field(default_factory=lambda: ["1m", "5m"])
    signal_timeframe: str = "1m"
    max_attempts_per_symbol_per_day: PositiveInt = 2
    close_all_minutes_before_close: PositiveInt = 5
    sessions: dict[str, SessionWindowConfig] = Field(
        default_factory=lambda: {
            "london": SessionWindowConfig(
                timezone="Europe/London",
                start_time="07:00",
                end_time="11:00",
            ),
            "new_york": SessionWindowConfig(
                timezone="America/New_York",
                start_time="09:30",
                end_time="12:00",
            ),
        }
    )
    kill_zones: KillZonesConfig = Field(default_factory=KillZonesConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    intraday: IntradayRulesConfig = Field(default_factory=IntradayRulesConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    flow_strategy: FlowStrategyConfig = Field(default_factory=FlowStrategyConfig)
    paper_profiles: dict[str, PaperProfileConfig] = Field(default_factory=dict)


class InstrumentConfig(BaseModel):
    symbol: str
    display_name: str
    asset_class: Literal["metal", "energy", "index"]
    point_size: float
    round_number_step: float


class UniverseScannerConfig(BaseModel):
    max_daily_candidates: PositiveInt = 5
    prefer_highest_score: bool = True


class AssetUniverseConfig(BaseModel):
    provider: Literal["oanda"] = "oanda"
    selection_mode: Literal["scanner"] = "scanner"
    instruments: list[InstrumentConfig] = Field(default_factory=list)
    scanner: UniverseScannerConfig = Field(default_factory=UniverseScannerConfig)


class WalkForwardWindow(BaseModel):
    name: str
    in_sample_start: str | date
    in_sample_end: str | date
    validation_start: str | date
    validation_end: str | date
    out_of_sample_start: str | date
    out_of_sample_end: str | date


class ParameterGridConfig(BaseModel):
    extension_modes: list[ExtensionMode] = Field(default_factory=lambda: ["atr_multiple"])
    extension_values: list[float] = Field(default_factory=lambda: [3.0])
    volume_rank_values: list[float] = Field(default_factory=lambda: [0.7])
    slope_score_values: list[float] = Field(default_factory=lambda: [55.0])
    signal_timeframes: list[str] = Field(default_factory=lambda: ["1m"])
    target_r_values: list[float] = Field(default_factory=lambda: [1.5])
    stop_buffer_points: list[float] = Field(default_factory=lambda: [0.0])


class ReplayConfig(BaseModel):
    use_kill_zones_for_entry: bool = True
    use_5m_context_filter: bool = False
    allowed_5m_trend_states: list[Literal["down", "transition", "up"]] = Field(
        default_factory=lambda: ["down", "transition"]
    )
    require_5m_below_vwap_for_entry: bool = False
    pre_entry_invalidation_on_close_above_vwap: bool = True
    post_entry_invalidation_on_close_above_vwap: bool = True
    add_size_pct_of_initial: float = 40.0
    max_adds_per_trade: PositiveInt = 1


class ValidationParameterSetConfig(BaseModel):
    id: str
    market_family: Literal["all", "metals", "indices"] = "all"
    extension_mode: ExtensionMode = "atr_multiple"
    extension_value: float
    volume_rank_min: float
    slope_score_min: float
    target_r: float
    partial_take_r: float
    stop_buffer_points: float = 0.0
    killzone_only: bool = True
    notes: str | None = None


class FlowValidationParameterSetConfig(BaseModel):
    id: str
    symbols: list[str] = Field(default_factory=lambda: ["NAS100_USD", "US30_USD"])
    opening_window_variant: str = "open_0930_1030"
    min_daily_atr_pct: float
    min_vwap_slope_atr: float
    pullback_distance_atr: float
    max_extension_atr: float
    stop_atr_buffer: float
    stop_lookback_bars: PositiveInt
    target_r: float
    partial_take_r: float
    killzone_only: bool = True
    max_trades_per_day: PositiveInt = 2
    notes: str | None = None


class BacktestConfig(BaseModel):
    signal_expiry_sessions: PositiveInt = 2
    entry_mode: Literal["bar_close", "next_bar_open"] = "next_bar_open"
    stop_reference: Literal["signal_bar_high", "session_high"] = "signal_bar_high"
    stop_buffer_points: float = 0.0
    target_r: float = 1.5
    intrabar_priority: Literal["stop_first", "target_first"] = "stop_first"
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_points: float = 0.0
    borrow_cost_points_per_day: float = 0.0
    force_exit_minutes_before_close: PositiveInt = 5
    parameter_grid: ParameterGridConfig = Field(default_factory=ParameterGridConfig)
    replay: ReplayConfig = Field(default_factory=ReplayConfig)
    validation_parameter_sets: list[ValidationParameterSetConfig] = Field(default_factory=list)
    flow_validation_parameter_sets: list[FlowValidationParameterSetConfig] = Field(default_factory=list)
    flow_open_validation_parameter_sets: list[FlowValidationParameterSetConfig] = Field(default_factory=list)
    walk_forward_windows: list[WalkForwardWindow] = Field(default_factory=list)


class DiscordConfig(BaseModel):
    enabled: bool = True
    webhook_env_var: str = "DISCORD_WEBHOOK_URL"
    channel_name: str | None = None
    username: str = "Parabolic Exhaustion Bot"
    avatar_url: str | None = None
    rate_limit_per_minute: PositiveInt = 20
    retry_attempts: PositiveInt = 3
    retry_backoff_seconds: float = 2.0


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping at {path}, received {type(data)!r}")
    return data


def load_strategy_config(path: str | Path) -> StrategyConfig:
    return StrategyConfig.model_validate(_load_yaml(path))


def load_assets_config(path: str | Path) -> AssetUniverseConfig:
    return AssetUniverseConfig.model_validate(_load_yaml(path))


def load_backtest_config(path: str | Path) -> BacktestConfig:
    return BacktestConfig.model_validate(_load_yaml(path))


def load_discord_config(path: str | Path) -> DiscordConfig:
    return DiscordConfig.model_validate(_load_yaml(path))
