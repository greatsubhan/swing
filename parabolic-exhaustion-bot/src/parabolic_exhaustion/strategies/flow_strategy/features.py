from __future__ import annotations

import numpy as np
import pandas as pd

from parabolic_exhaustion.config import FlowStrategyConfig


def engineer_flow_features(
    intraday_features: pd.DataFrame,
    *,
    daily_features: pd.DataFrame,
    flow_config: FlowStrategyConfig,
) -> pd.DataFrame:
    data = intraday_features.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    data = data.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    grouped = data.groupby("symbol", group_keys=False)
    prev_close = grouped["close"].shift(1)
    prev_high = grouped["high"].shift(1)
    prev_low = grouped["low"].shift(1)

    true_range = pd.concat(
        [
            (data["high"] - data["low"]).abs(),
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["intraday_atr"] = true_range.groupby(data["symbol"]).transform(
        lambda series: series.rolling(flow_config.intraday_atr_length, min_periods=1).mean()
    )
    data["ema_fast"] = grouped["close"].transform(
        lambda series: series.ewm(span=flow_config.ema_fast_length, adjust=False).mean()
    )
    data["ema_slow"] = grouped["close"].transform(
        lambda series: series.ewm(span=flow_config.ema_slow_length, adjust=False).mean()
    )
    data["distance_from_vwap_points"] = data["close"] - data["vwap_session"]
    data["distance_from_vwap_atr"] = (
        data["distance_from_vwap_points"] / data["intraday_atr"].replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)
    vwap_shifted = grouped["vwap_session"].shift(flow_config.vwap_slope_lookback)
    slope_denominator = data["intraday_atr"].replace(0.0, np.nan) * flow_config.vwap_slope_lookback
    data["vwap_slope_points"] = (data["vwap_session"] - vwap_shifted).fillna(0.0)
    data["vwap_slope_atr"] = (
        data["vwap_slope_points"] / slope_denominator
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    data["higher_high_flag"] = (data["high"] > prev_high).fillna(False)
    data["higher_low_flag"] = (data["low"] > prev_low).fillna(False)
    data["bullish_body"] = data["close"] > data["open"]
    data["bearish_body"] = data["close"] < data["open"]
    data["prev_high"] = prev_high
    data["prev_low"] = prev_low

    daily_context = _prepare_daily_context(daily_features)
    data = pd.merge_asof(
        data.sort_values(["symbol", "timestamp"]),
        daily_context.sort_values(["symbol", "timestamp"]),
        by="symbol",
        on="timestamp",
        direction="backward",
    )
    data["prev_daily_atr_pct"] = data["prev_daily_atr_pct"].fillna(0.0)
    data["prev_daily_atr_14"] = data["prev_daily_atr_14"].fillna(0.0)
    data["daily_context_eligible"] = data["prev_daily_atr_pct"] >= flow_config.min_daily_atr_pct
    return data.reset_index(drop=True)


def _prepare_daily_context(daily_features: pd.DataFrame) -> pd.DataFrame:
    daily = daily_features.copy()
    daily["timestamp"] = pd.to_datetime(daily["timestamp"], utc=True)
    daily = daily.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    grouped = daily.groupby("symbol", group_keys=False)
    daily["prev_daily_atr_14"] = grouped["atr_14"].shift(1)
    daily["prev_daily_close"] = grouped["close"].shift(1)
    daily["prev_daily_atr_pct"] = (
        (daily["prev_daily_atr_14"] / grouped["close"].shift(1).replace(0.0, np.nan)) * 100.0
    ).replace([np.inf, -np.inf], np.nan)
    daily["prev_daily_sma_20"] = grouped["sma_20"].shift(1)
    return daily.loc[
        :,
        [
            "symbol",
            "timestamp",
            "prev_daily_atr_14",
            "prev_daily_close",
            "prev_daily_atr_pct",
            "prev_daily_sma_20",
        ],
    ]
