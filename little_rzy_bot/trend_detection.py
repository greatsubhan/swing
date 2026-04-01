"""Trend detection using MA slope, ADX and pivot structure."""
from typing import List, Tuple
import pandas as pd


def _count_sequence(pivots: List[Tuple[int, float]], bullish: bool) -> int:
    if len(pivots) < 3:
        return 0
    count = 0
    for i in range(1, len(pivots)):
        prev = pivots[i - 1][1]
        cur = pivots[i][1]
        if (bullish and cur > prev) or ((not bullish) and cur < prev):
            count += 1
    return count


def detect_trend_state(
    row: pd.Series,
    pivot_highs: List[Tuple[int, float]],
    pivot_lows: List[Tuple[int, float]],
    min_hhhl_count: int,
    min_ma_slope: float,
    min_adx: float,
) -> str:
    ma_slope = row.get("ema_slow_slope", 0.0)
    adx_v = row.get("adx", 0.0)
    hh = _count_sequence(pivot_highs[-4:], bullish=True)
    hl = _count_sequence(pivot_lows[-4:], bullish=True)
    lh = _count_sequence(pivot_highs[-4:], bullish=False)
    ll = _count_sequence(pivot_lows[-4:], bullish=False)

    if ma_slope > min_ma_slope and adx_v >= min_adx and hh >= min_hhhl_count and hl >= min_hhhl_count:
        return "bullish"
    if ma_slope < -min_ma_slope and adx_v >= min_adx and lh >= min_hhhl_count and ll >= min_hhhl_count:
        return "bearish"
    return "sideways"
