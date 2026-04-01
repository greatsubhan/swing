"""Little RZY structure detection."""
from typing import List, Optional, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import SetupCandidate
from .trendline import line_from_points, line_value


def _find_last_pivot_before(pivots: List[Tuple[int, float]], idx: int) -> Optional[Tuple[int, float]]:
    prior = [p for p in pivots if p[0] < idx]
    return prior[-1] if prior else None


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
        end_high = _find_last_pivot_before(pivot_highs, i)
        if not anchor or not end_high:
            return None
        impulse_start_idx = max(0, anchor[0] - cfg.structure.max_impulse_bars)
        impulse_slice = df.iloc[impulse_start_idx : anchor[0] + 1]
        impulse_high = float(impulse_slice["high"].max())
        impulse_size = impulse_high - anchor[1]
        impulse_peak_offset = int(impulse_slice["high"].to_numpy().argmax())
        impulse_peak_idx = impulse_start_idx + impulse_peak_offset
        impulse_bars = anchor[0] - impulse_peak_idx
        retrace = (end_high[1] - anchor[1]) / max(impulse_size, 1e-9)
        if impulse_size / atr_v < cfg.structure.min_impulse_atr:
            return None
        if not (cfg.structure.min_impulse_bars <= impulse_bars <= cfg.structure.max_impulse_bars):
            return None
        if not (cfg.structure.pullback_min_retrace <= retrace <= cfg.structure.pullback_max_retrace):
            return None
        if i - anchor[0] > cfg.structure.max_setup_age_bars:
            return None

        p1, p2 = end_high, (i, float(df["high"].iloc[i]))
        if p2[0] <= p1[0]:
            return None
        slope, intercept = line_from_points(p1, p2)
        if not (-cfg.structure.trendline_max_abs_slope <= slope < 0):
            return None

        trendline_at_anchor = line_value(slope, intercept, anchor[0])
        measured = trendline_at_anchor - anchor[1]
        if measured <= 0:
            return None
        target = anchor[1] - measured
        entry = float(df["low"].iloc[i - 1]) if i > 0 else float(df["low"].iloc[i])
        stop = max(end_high[1], line_value(slope, intercept, i)) + cfg.risk.atr_stop_padding * atr_v
        rr = (entry - target) / max(stop - entry, 1e-9)
        if rr < cfg.risk.min_rr:
            return None
        return SetupCandidate(
            side="short",
            impulse_start=impulse_start_idx,
            impulse_end=anchor[0],
            pullback_start=anchor[0] + 1,
            pullback_end=i,
            anchor_index=anchor[0],
            entry_trigger=entry,
            stop=stop,
            target=target,
            risk_reward=rr,
            validity_reason="Valid bearish Little RZY candidate",
        )

    anchor = _find_last_pivot_before(pivot_highs, i)
    end_low = _find_last_pivot_before(pivot_lows, i)
    if not anchor or not end_low:
        return None
    impulse_start_idx = max(0, anchor[0] - cfg.structure.max_impulse_bars)
    impulse_slice = df.iloc[impulse_start_idx : anchor[0] + 1]
    impulse_low = float(impulse_slice["low"].min())
    impulse_size = anchor[1] - impulse_low
    impulse_trough_offset = int(impulse_slice["low"].to_numpy().argmin())
    impulse_trough_idx = impulse_start_idx + impulse_trough_offset
    impulse_bars = anchor[0] - impulse_trough_idx
    retrace = (anchor[1] - end_low[1]) / max(impulse_size, 1e-9)
    if impulse_size / atr_v < cfg.structure.min_impulse_atr:
        return None
    if not (cfg.structure.min_impulse_bars <= impulse_bars <= cfg.structure.max_impulse_bars):
        return None
    if not (cfg.structure.pullback_min_retrace <= retrace <= cfg.structure.pullback_max_retrace):
        return None
    if i - anchor[0] > cfg.structure.max_setup_age_bars:
        return None

    p1, p2 = end_low, (i, float(df["low"].iloc[i]))
    if p2[0] <= p1[0]:
        return None
    slope, intercept = line_from_points(p1, p2)
    if not (0 < slope <= cfg.structure.trendline_max_abs_slope):
        return None

    trendline_at_anchor = line_value(slope, intercept, anchor[0])
    measured = anchor[1] - trendline_at_anchor
    if measured <= 0:
        return None
    target = anchor[1] + measured
    entry = float(df["high"].iloc[i - 1]) if i > 0 else float(df["high"].iloc[i])
    stop = min(end_low[1], line_value(slope, intercept, i)) - cfg.risk.atr_stop_padding * atr_v
    rr = (target - entry) / max(entry - stop, 1e-9)
    if rr < cfg.risk.min_rr:
        return None
    return SetupCandidate(
        side="long",
        impulse_start=impulse_start_idx,
        impulse_end=anchor[0],
        pullback_start=anchor[0] + 1,
        pullback_end=i,
        anchor_index=anchor[0],
        entry_trigger=entry,
        stop=stop,
        target=target,
        risk_reward=rr,
        validity_reason="Valid bullish Little RZY candidate",
    )
