from __future__ import annotations

import math

import numpy as np
import pandas as pd


REQUIRED_DAILY_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")


def engineer_daily_features(
    bars: pd.DataFrame,
    *,
    base_lookback: int = 60,
    base_touch_tolerance_pct: float = 1.0,
) -> pd.DataFrame:
    """Compute machine-readable daily features for parabolic exhaustion research."""

    _validate_columns(bars, REQUIRED_DAILY_COLUMNS)
    data = bars.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data = data.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    grouped = data.groupby("symbol", group_keys=False)
    data["sma_20"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    data["sma_50"] = grouped["close"].transform(lambda s: s.rolling(50, min_periods=1).mean())

    prev_close = grouped["close"].shift(1)
    true_range = pd.concat(
        [
            (data["high"] - data["low"]).abs(),
            (data["high"] - prev_close).abs(),
            (data["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr_14"] = true_range.groupby(data["symbol"]).transform(
        lambda s: s.rolling(14, min_periods=1).mean()
    )
    data["distance_from_sma20_pct"] = ((data["close"] / data["sma_20"]) - 1.0) * 100.0
    data["rolling_volume_rank_60d"] = grouped["volume"].transform(_rolling_percentile_rank)
    data["highest_close_20d"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=1).max())
    data["gap_pct"] = ((data["open"] / prev_close) - 1.0).fillna(0.0) * 100.0
    score_frames: list[pd.Series] = []
    base_frames: list[pd.DataFrame] = []
    for _, frame in grouped:
        score_frames.append(_compute_parabolic_slope_score(frame))
        base_frames.append(
            _detect_recent_base_features(
                frame,
                lookback=base_lookback,
                touch_tolerance_pct=base_touch_tolerance_pct,
            )
        )

    data["parabolic_slope_score"] = pd.concat(score_frames).sort_index()
    base_features = pd.concat(base_frames).sort_index()
    data["recent_base_date"] = base_features["recent_base_date"]
    data["recent_base_price"] = base_features["recent_base_price"]
    data["extension_from_base_points"] = data["close"] - data["recent_base_price"]
    data["extension_from_base_pct"] = (
        ((data["close"] / data["recent_base_price"]) - 1.0) * 100.0
    ).replace([np.inf, -np.inf], np.nan)
    data["extension_from_base_atr"] = (
        data["extension_from_base_points"] / data["atr_14"].replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)
    data["round_number_proximity"] = data["close"].map(_round_number_distance_pct)

    if "asset_class" not in data.columns:
        data["asset_class"] = "unknown"

    return data


def _validate_columns(frame: pd.DataFrame, required: tuple[str, ...]) -> None:
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _rolling_percentile_rank(series: pd.Series, window: int = 60) -> pd.Series:
    def rank_last(values: np.ndarray) -> float:
        if len(values) == 1:
            return 1.0
        last = values[-1]
        return float(np.sum(values <= last) / len(values))

    return series.rolling(window, min_periods=1).apply(rank_last, raw=True)


def _compute_parabolic_slope_score(frame: pd.DataFrame) -> pd.Series:
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    return_5 = close.pct_change(5).fillna(0.0)
    return_20 = close.pct_change(20).fillna(0.0)
    acceleration = (return_5 - (return_20 / 4.0)).clip(lower=0.0)
    daily_range = ((high - low) / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    range_expansion = daily_range.rolling(5, min_periods=1).mean()
    volume_surge = (volume / volume.rolling(20, min_periods=1).mean()).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(1.0)

    raw = (acceleration * 0.5) + (range_expansion * 0.3) + ((volume_surge - 1.0).clip(lower=0.0) * 0.2)
    rolling_min = raw.rolling(60, min_periods=1).min()
    rolling_max = raw.rolling(60, min_periods=1).max()
    score = ((raw - rolling_min) / (rolling_max - rolling_min).replace(0.0, np.nan)).fillna(0.0)
    return (score.clip(0.0, 1.0) * 100.0).round(2)


def _detect_recent_base_features(
    frame: pd.DataFrame,
    *,
    lookback: int,
    touch_tolerance_pct: float,
) -> pd.DataFrame:
    timestamps = frame["timestamp"].to_list()
    lows = frame["low"].to_numpy(dtype=float)
    closes = frame["close"].to_numpy(dtype=float)
    sma20 = frame["sma_20"].to_numpy(dtype=float)
    tolerance = touch_tolerance_pct / 100.0

    recent_base_dates: list[pd.Timestamp] = []
    recent_base_prices: list[float] = []

    for index in range(len(frame)):
        start = max(0, index - lookback)
        recent_date = pd.NaT
        recent_price = np.nan
        for candidate in range(index - 1, start - 1, -1):
            lower_bound = sma20[candidate] * (1.0 - tolerance)
            upper_bound = sma20[candidate] * (1.0 + tolerance)
            touches_sma = lower_bound <= closes[candidate] <= upper_bound or lows[candidate] <= upper_bound
            if touches_sma:
                recent_date = pd.Timestamp(timestamps[candidate])
                recent_price = closes[candidate]
                break
        recent_base_dates.append(recent_date)
        recent_base_prices.append(recent_price)

    return pd.DataFrame(
        {
            "recent_base_date": recent_base_dates,
            "recent_base_price": recent_base_prices,
        },
        index=frame.index,
    )


def _round_number_distance_pct(price: float) -> float:
    if not np.isfinite(price) or price <= 0:
        return np.nan
    magnitude = 10 ** max(int(math.floor(math.log10(price))) - 1, 0)
    anchors = np.array([1, 3, 5, 10], dtype=float) * magnitude * 10
    nearest = anchors[np.argmin(np.abs(anchors - price))]
    return abs(price - nearest) / nearest * 100.0
