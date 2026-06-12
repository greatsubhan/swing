from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd

from parabolic_exhaustion.config import (
    BacktestConfig,
    FlowStrategyConfig,
    FlowValidationParameterSetConfig,
    StrategyConfig,
)


@dataclass(frozen=True)
class FlowParameterSet:
    id: str
    symbols: tuple[str, ...]
    opening_window_variant: str
    min_daily_atr_pct: float
    min_vwap_slope_atr: float
    pullback_distance_atr: float
    max_extension_atr: float
    stop_atr_buffer: float
    stop_lookback_bars: int
    target_r: float
    partial_take_r: float
    killzone_only: bool
    max_trades_per_day: int
    notes: str | None = None


def parameter_set_from_config(config: FlowValidationParameterSetConfig) -> FlowParameterSet:
    return FlowParameterSet(
        id=config.id,
        symbols=tuple(config.symbols),
        opening_window_variant=config.opening_window_variant,
        min_daily_atr_pct=float(config.min_daily_atr_pct),
        min_vwap_slope_atr=float(config.min_vwap_slope_atr),
        pullback_distance_atr=float(config.pullback_distance_atr),
        max_extension_atr=float(config.max_extension_atr),
        stop_atr_buffer=float(config.stop_atr_buffer),
        stop_lookback_bars=int(config.stop_lookback_bars),
        target_r=float(config.target_r),
        partial_take_r=float(config.partial_take_r),
        killzone_only=bool(config.killzone_only),
        max_trades_per_day=int(config.max_trades_per_day),
        notes=config.notes,
    )


def build_flow_strategy_variant(
    *,
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> StrategyConfig:
    variant = strategy_config.model_copy(deep=True)
    variant.intraday_timeframes = [variant.flow_strategy.signal_timeframe]
    variant.signal_timeframe = variant.flow_strategy.signal_timeframe
    variant.flow_strategy.opening_window_variant = parameter_set.opening_window_variant
    variant.flow_strategy.min_daily_atr_pct = parameter_set.min_daily_atr_pct
    variant.flow_strategy.min_vwap_slope_atr = parameter_set.min_vwap_slope_atr
    variant.flow_strategy.pullback_distance_atr = parameter_set.pullback_distance_atr
    variant.flow_strategy.max_extension_atr = parameter_set.max_extension_atr
    variant.flow_strategy.stop_atr_buffer = parameter_set.stop_atr_buffer
    variant.flow_strategy.stop_lookback_bars = parameter_set.stop_lookback_bars
    variant.flow_strategy.max_trades_per_day = parameter_set.max_trades_per_day
    variant.flow_strategy.use_kill_zones = parameter_set.killzone_only
    variant.risk.partial_take_r = parameter_set.partial_take_r
    return variant


def build_flow_backtest_variant(
    *,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
) -> BacktestConfig:
    variant = backtest_config.model_copy(deep=True)
    variant.target_r = parameter_set.target_r
    variant.replay.use_kill_zones_for_entry = parameter_set.killzone_only
    return variant


def resolve_flow_defaults(config: StrategyConfig) -> FlowStrategyConfig:
    return config.flow_strategy.model_copy(deep=True)


def apply_opening_window_filter(
    frame: pd.DataFrame,
    *,
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    opening_window = strategy_config.flow_strategy.opening_windows[parameter_set.opening_window_variant]
    localized = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(opening_window.timezone)
    local_time = localized.dt.time
    start = _parse_time(opening_window.start_time)
    end = _parse_time(opening_window.end_time)
    filtered = frame.loc[local_time.map(lambda value: start <= value <= end)].copy()
    filtered["opening_window_variant"] = parameter_set.opening_window_variant
    return filtered


def _parse_time(value: str) -> time:
    hour_text, minute_text = value.split(":")
    return time(hour=int(hour_text), minute=int(minute_text))
