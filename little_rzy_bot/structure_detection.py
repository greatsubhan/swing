"""Little RZY structure detection."""
from typing import List, Optional, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import SetupCandidate
from .trendline import line_from_points, line_value


def _find_last_pivot_before(pivots: List[Tuple[int, float]], idx: int) -> Optional[Tuple[int, float]]:
    prior = [p for p in pivots if p[0] < idx]
    return prior[-1] if prior else None


def _find_pivots_between(pivots: List[Tuple[int, float]], start_idx: int, end_idx: int) -> List[Tuple[int, float]]:
    return [pivot for pivot in pivots if start_idx < pivot[0] < end_idx]


def _count_line_touches(
    df: pd.DataFrame,
    price_column: str,
    start_idx: int,
    end_idx: int,
    slope: float,
    intercept: float,
    tolerance: float,
) -> int:
    touches = 0
    for idx in range(start_idx, end_idx + 1):
        line_at_idx = line_value(slope, intercept, idx)
        if abs(float(df[price_column].iloc[idx]) - line_at_idx) <= tolerance:
            touches += 1
    return touches


def _violates_trendline_close(
    df: pd.DataFrame,
    side: str,
    start_idx: int,
    end_idx: int,
    slope: float,
    intercept: float,
    tolerance: float,
) -> bool:
    for idx in range(start_idx, end_idx + 1):
        close = float(df["close"].iloc[idx])
        line_at_idx = line_value(slope, intercept, idx)
        if side == "short" and close > line_at_idx + tolerance:
            return True
        if side == "long" and close < line_at_idx - tolerance:
            return True
    return False


def detect_candidate(
    df: pd.DataFrame,
    i: int,
    trend_state: str,
    pivot_highs: List[Tuple[int, float]],
    pivot_lows: List[Tuple[int, float]],
    cfg: EngineConfig,
) -> Optional[SetupCandidate]:
    if trend_state not in {"bullish", "bearish"}:
        return None

    atr_v = float(df["atr"].iloc[i])
    if atr_v <= 0:
        return None

    if trend_state == "bearish":
        anchor = _find_last_pivot_before(pivot_lows, i)
        if not anchor:
            return None

        pullback_highs = _find_pivots_between(pivot_highs, anchor[0], i)
        if not pullback_highs:
            return None

        trendline_start = pullback_highs[0]
        trendline_end = pullback_highs[-1] if len(pullback_highs) >= 2 else (i, float(df["high"].iloc[i]))
        if trendline_end[0] <= trendline_start[0]:
            return None
        last_pullback_high = pullback_highs[-1]
        if i - last_pullback_high[0] > cfg.structure.max_breakout_bars_after_pullback:
            return None

        impulse_start_idx = max(0, anchor[0] - cfg.structure.max_impulse_bars)
        impulse_slice = df.iloc[impulse_start_idx : anchor[0] + 1]
        impulse_high = float(impulse_slice["high"].max())
        impulse_size = impulse_high - anchor[1]
        impulse_peak_offset = int(impulse_slice["high"].to_numpy().argmax())
        impulse_peak_idx = impulse_start_idx + impulse_peak_offset
        impulse_bars = anchor[0] - impulse_peak_idx
        pullback_slice = df.iloc[anchor[0] + 1 : trendline_end[0] + 1]
        if pullback_slice.empty:
            return None

        pullback_high = float(pullback_slice["high"].max())
        pullback_bars = trendline_end[0] - anchor[0]
        retrace = (pullback_high - anchor[1]) / max(impulse_size, 1e-9)
        if impulse_size / atr_v < cfg.structure.min_impulse_atr:
            return None
        if not (cfg.structure.min_impulse_bars <= impulse_bars <= cfg.structure.max_impulse_bars):
            return None
        if not (cfg.structure.pullback_min_retrace <= retrace <= cfg.structure.pullback_max_retrace):
            return None
        if not (cfg.structure.pullback_min_bars <= pullback_bars <= cfg.structure.pullback_max_bars):
            return None
        if i - anchor[0] > cfg.structure.max_setup_age_bars:
            return None

        slope, intercept = line_from_points(trendline_start, trendline_end)
        if not (-cfg.structure.trendline_max_abs_slope <= slope < 0):
            return None
        touch_tolerance = cfg.structure.trendline_touch_tolerance_atr * atr_v
        touches = _count_line_touches(df, "high", trendline_start[0], trendline_end[0], slope, intercept, touch_tolerance)
        if touches < cfg.structure.trendline_min_touches:
            return None
        if _violates_trendline_close(df, "short", trendline_start[0], i, slope, intercept, touch_tolerance):
            return None

        trendline_at_anchor = line_value(slope, intercept, anchor[0])
        measured = trendline_at_anchor - anchor[1]
        if measured <= 0:
            return None
        target = anchor[1] - measured
        entry = float(df["low"].iloc[i - 1]) if i > 0 else float(df["low"].iloc[i])
        trendline_now = line_value(slope, intercept, i)
        stop = pullback_high + cfg.risk.atr_stop_padding * atr_v
        rr = (entry - target) / max(stop - entry, 1e-9)
        if rr < cfg.risk.min_rr:
            return None
        return SetupCandidate(
            side="short",
            impulse_start=impulse_start_idx,
            impulse_end=anchor[0],
            pullback_start=anchor[0] + 1,
            pullback_end=trendline_end[0],
            anchor_index=anchor[0],
            trendline_start_index=trendline_start[0],
            trendline_start_price=trendline_start[1],
            trendline_end_index=trendline_end[0],
            trendline_end_price=trendline_end[1],
            entry_trigger=entry,
            stop=stop,
            invalidation_level=trendline_now,
            trendline_tolerance=touch_tolerance,
            target=target,
            measured_distance=measured,
            risk_reward=rr,
            validity_reason="Valid bearish Little RZY candidate",
        )

    anchor = _find_last_pivot_before(pivot_highs, i)
    if not anchor:
        return None
    pullback_lows = _find_pivots_between(pivot_lows, anchor[0], i)
    if not pullback_lows:
        return None

    trendline_start = pullback_lows[0]
    trendline_end = pullback_lows[-1] if len(pullback_lows) >= 2 else (i, float(df["low"].iloc[i]))
    if trendline_end[0] <= trendline_start[0]:
        return None
    last_pullback_low = pullback_lows[-1]
    if i - last_pullback_low[0] > cfg.structure.max_breakout_bars_after_pullback:
        return None

    impulse_start_idx = max(0, anchor[0] - cfg.structure.max_impulse_bars)
    impulse_slice = df.iloc[impulse_start_idx : anchor[0] + 1]
    impulse_low = float(impulse_slice["low"].min())
    impulse_size = anchor[1] - impulse_low
    impulse_trough_offset = int(impulse_slice["low"].to_numpy().argmin())
    impulse_trough_idx = impulse_start_idx + impulse_trough_offset
    impulse_bars = anchor[0] - impulse_trough_idx
    pullback_slice = df.iloc[anchor[0] + 1 : trendline_end[0] + 1]
    if pullback_slice.empty:
        return None

    pullback_low = float(pullback_slice["low"].min())
    pullback_bars = trendline_end[0] - anchor[0]
    retrace = (anchor[1] - pullback_low) / max(impulse_size, 1e-9)
    if impulse_size / atr_v < cfg.structure.min_impulse_atr:
        return None
    if not (cfg.structure.min_impulse_bars <= impulse_bars <= cfg.structure.max_impulse_bars):
        return None
    if not (cfg.structure.pullback_min_retrace <= retrace <= cfg.structure.pullback_max_retrace):
        return None
    if not (cfg.structure.pullback_min_bars <= pullback_bars <= cfg.structure.pullback_max_bars):
        return None
    if i - anchor[0] > cfg.structure.max_setup_age_bars:
        return None

    slope, intercept = line_from_points(trendline_start, trendline_end)
    if not (0 < slope <= cfg.structure.trendline_max_abs_slope):
        return None
    touch_tolerance = cfg.structure.trendline_touch_tolerance_atr * atr_v
    touches = _count_line_touches(df, "low", trendline_start[0], trendline_end[0], slope, intercept, touch_tolerance)
    if touches < cfg.structure.trendline_min_touches:
        return None
    if _violates_trendline_close(df, "long", trendline_start[0], i, slope, intercept, touch_tolerance):
        return None

    trendline_at_anchor = line_value(slope, intercept, anchor[0])
    measured = anchor[1] - trendline_at_anchor
    if measured <= 0:
        return None
    target = anchor[1] + measured
    entry = float(df["high"].iloc[i - 1]) if i > 0 else float(df["high"].iloc[i])
    trendline_now = line_value(slope, intercept, i)
    stop = pullback_low - cfg.risk.atr_stop_padding * atr_v
    rr = (target - entry) / max(entry - stop, 1e-9)
    if rr < cfg.risk.min_rr:
        return None
    return SetupCandidate(
        side="long",
        impulse_start=impulse_start_idx,
        impulse_end=anchor[0],
        pullback_start=anchor[0] + 1,
        pullback_end=trendline_end[0],
        anchor_index=anchor[0],
        trendline_start_index=trendline_start[0],
        trendline_start_price=trendline_start[1],
        trendline_end_index=trendline_end[0],
        trendline_end_price=trendline_end[1],
        entry_trigger=entry,
        stop=stop,
        invalidation_level=trendline_now,
        trendline_tolerance=touch_tolerance,
        target=target,
        measured_distance=measured,
        risk_reward=rr,
        validity_reason="Valid bullish Little RZY candidate",
    )
