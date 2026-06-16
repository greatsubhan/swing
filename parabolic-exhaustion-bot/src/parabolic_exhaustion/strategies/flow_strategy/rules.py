from __future__ import annotations

import pandas as pd

from parabolic_exhaustion.config import StrategyConfig
from parabolic_exhaustion.strategies.flow_strategy.config import FlowParameterSet


def build_flow_candidate_table(
    bars: pd.DataFrame,
    *,
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> pd.DataFrame:
    eligible = _eligible_bars(bars, strategy_config=strategy_config, parameter_set=parameter_set)
    if eligible.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "candidate_date",
                "session_name",
                "opening_window_variant",
                "bar_timeframe",
                "daily_context_eligible",
                "killzone_only",
                "candidate_score",
            ]
        )

    grouped = eligible.groupby(["symbol", "trade_date"], as_index=False).agg(
        session_name=("session_name", "first"),
        opening_window_variant=("opening_window_variant", "first"),
        bar_timeframe=("bar_timeframe", "first"),
        daily_context_eligible=("daily_context_eligible", "max"),
        kill_zone_active=("kill_zone_active", "max"),
        candidate_score=("vwap_slope_atr", "max"),
    )
    grouped = grouped.rename(columns={"trade_date": "candidate_date"})
    grouped["killzone_only"] = parameter_set.killzone_only
    return grouped


def build_flow_signal_table(
    bars: pd.DataFrame,
    *,
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()

    eligible = _eligible_bars(bars, strategy_config=strategy_config, parameter_set=parameter_set)
    if eligible.empty:
        return pd.DataFrame()

    grouped = eligible.groupby(["symbol", "trade_date"], group_keys=False)
    eligible["recent_pullback"] = grouped["touch_zone"].transform(
        lambda series: series.shift(1).rolling(strategy_config.flow_strategy.pullback_lookback, min_periods=1).max()
    ).fillna(0.0) > 0

    long_mask = (
        strategy_config.flow_strategy.allow_longs
        and True
    )
    short_mask = (
        strategy_config.flow_strategy.allow_shorts
        and True
    )

    long_signals = eligible.loc[
        eligible["long_trend_bias"]
        & eligible["recent_pullback"]
        & eligible["bullish_body"]
        & (eligible["close"] > eligible["prev_high"].fillna(eligible["close"]))
        & (eligible["distance_from_vwap_atr"] >= 0.0)
        & (eligible["distance_from_vwap_atr"] <= parameter_set.max_extension_atr)
    ].copy()
    short_signals = eligible.loc[
        eligible["short_trend_bias"]
        & eligible["recent_pullback"]
        & eligible["bearish_body"]
        & (eligible["close"] < eligible["prev_low"].fillna(eligible["close"]))
        & (eligible["distance_from_vwap_atr"] <= 0.0)
        & (eligible["distance_from_vwap_atr"].abs() <= parameter_set.max_extension_atr)
    ].copy()
    if not long_mask:
        long_signals = long_signals.iloc[0:0].copy()
    if not short_mask:
        short_signals = short_signals.iloc[0:0].copy()
    if long_signals.empty and short_signals.empty:
        return pd.DataFrame()

    long_signals["direction"] = "long"
    short_signals["direction"] = "short"
    signals = pd.concat([long_signals, short_signals], ignore_index=True)
    signals = signals.sort_values(["symbol", "trade_date", "timestamp", "direction"]).reset_index(drop=True)

    previous_signal_time = signals.groupby(["symbol", "trade_date", "direction"])["timestamp"].transform("shift")
    signals = signals.loc[
        previous_signal_time.isna()
        | ((signals["timestamp"] - previous_signal_time).dt.total_seconds() / 60.0 > 10.0)
    ].copy()

    signals["parameter_set"] = parameter_set.id
    signals["opening_window_variant"] = parameter_set.opening_window_variant
    signals["signal_stage"] = "ENTRY_TRIGGERED"
    signals["bar_timeframe"] = signals["bar_timeframe"].fillna(strategy_config.flow_strategy.signal_timeframe)
    signals["entry_reason"] = signals["direction"].map(
        {
            "long": "VWAP pullback continuation long",
            "short": "VWAP pullback continuation short",
        }
    )
    signals["signal_score"] = (
        signals["vwap_slope_atr"].abs() * 50.0
        + signals["prev_daily_atr_pct"] * 10.0
        + signals["distance_from_vwap_atr"].abs() * 20.0
    ).round(2)
    signals["stop_reference_price"] = signals.apply(
        lambda row: row["rolling_swing_low"] if row["direction"] == "long" else row["rolling_swing_high"],
        axis=1,
    )
    return signals.reset_index(drop=True)


def _eligible_bars(
    bars: pd.DataFrame,
    *,
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> pd.DataFrame:
    eligible = bars.copy()
    eligible["touch_zone"] = _touched_vwap_zone(eligible, parameter_set=parameter_set)
    eligible["long_trend_bias"] = (
        (eligible["ema_fast"] > eligible["ema_slow"])
        & (eligible["close"] > eligible["vwap_session"])
        & (eligible["vwap_slope_atr"] >= parameter_set.min_vwap_slope_atr)
        & (eligible["higher_low_flag"] | (eligible["close"] > eligible["ema_fast"]))
    )
    eligible["short_trend_bias"] = (
        (eligible["ema_fast"] < eligible["ema_slow"])
        & (eligible["close"] < eligible["vwap_session"])
        & (eligible["vwap_slope_atr"] <= -parameter_set.min_vwap_slope_atr)
        & (eligible["lower_high_flag"] | (eligible["close"] < eligible["ema_fast"]))
    )

    active_mask = eligible["session_name"].notna()
    if parameter_set.killzone_only:
        active_mask &= eligible["kill_zone_active"]
    eligible = eligible.loc[
        active_mask
        & eligible["daily_context_eligible"]
        & eligible["intraday_atr"].gt(0.0)
    ].copy()
    return eligible


def _touched_vwap_zone(
    bars: pd.DataFrame,
    *,
    parameter_set: FlowParameterSet,
) -> pd.Series:
    threshold_points = bars["intraday_atr"] * parameter_set.pullback_distance_atr
    return (
        (bars["low"] <= (bars["vwap_session"] + threshold_points))
        & (bars["high"] >= (bars["vwap_session"] - threshold_points))
    ).fillna(False)
