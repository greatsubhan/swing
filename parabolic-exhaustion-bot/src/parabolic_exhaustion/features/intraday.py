from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_INTRADAY_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")


def engineer_intraday_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Compute session-aware intraday features used for live and replay logic."""

    _validate_columns(bars, REQUIRED_INTRADAY_COLUMNS)
    data = bars.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data = data.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    data["session_date"] = data["timestamp"].dt.date

    grouped = data.groupby(["symbol", "session_date"], group_keys=False)
    typical_price = (data["high"] + data["low"] + data["close"]) / 3.0
    cumulative_tpv = (typical_price * data["volume"]).groupby([data["symbol"], data["session_date"]]).cumsum()
    cumulative_volume = data["volume"].groupby([data["symbol"], data["session_date"]]).cumsum()
    data["vwap_session"] = cumulative_tpv / cumulative_volume.replace(0.0, np.nan)
    data["distance_from_vwap_pct"] = ((data["close"] / data["vwap_session"]) - 1.0).fillna(0.0) * 100.0
    data["high_of_day"] = grouped["high"].cummax()
    data["low_of_day"] = grouped["low"].cummin()

    prev_high = grouped["high"].shift(1)
    prev_low = grouped["low"].shift(1)
    prev_close = grouped["close"].shift(1)
    prev_vwap = grouped["vwap_session"].shift(1)

    data["lower_high_flag"] = (data["high"] < prev_high).fillna(False)
    data["lower_low_flag"] = (data["low"] < prev_low).fillna(False)
    higher_high = (data["high"] > prev_high).fillna(False)
    higher_low = (data["low"] > prev_low).fillna(False)
    data["trend_state"] = np.select(
        [data["lower_high_flag"] & data["lower_low_flag"], higher_high & higher_low],
        ["down", "up"],
        default="transition",
    )
    data["vwap_cross_down_flag"] = ((data["close"] < data["vwap_session"]) & (prev_close >= prev_vwap)).fillna(False)
    data["vwap_reclaim_fail_flag"] = (
        (prev_close < prev_vwap) & (data["high"] >= data["vwap_session"]) & (data["close"] < data["vwap_session"])
    ).fillna(False)

    bar_range = (data["high"] - data["low"]).abs()
    baseline_range = grouped["high"].transform(lambda s: s.rolling(20, min_periods=1).max()) - grouped["low"].transform(
        lambda s: s.rolling(20, min_periods=1).min()
    )
    data["intraday_range_expansion"] = (bar_range / baseline_range.replace(0.0, np.nan)).fillna(0.0)
    data["intraday_volume_relative"] = (
        data["volume"] / grouped["volume"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    session_open = grouped["timestamp"].transform("min")
    delta = data["timestamp"] - session_open
    data["time_since_open_minutes"] = delta.dt.total_seconds().div(60.0)
    data["retest_count_vwap"] = grouped["vwap_reclaim_fail_flag"].cumsum()

    return data


def _validate_columns(frame: pd.DataFrame, required: tuple[str, ...]) -> None:
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
