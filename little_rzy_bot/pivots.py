"""Confirmed pivot detection to avoid lookahead leak."""
from typing import List, Tuple
import pandas as pd


Pivot = Tuple[int, float]


def detect_pivot_highs(df: pd.DataFrame, left: int, right: int) -> List[Pivot]:
    highs: List[Pivot] = []
    for i in range(left, len(df) - right):
        segment = df["high"].iloc[i - left : i + right + 1]
        if df["high"].iloc[i] == segment.max() and (segment == segment.max()).sum() == 1:
            highs.append((i, float(df["high"].iloc[i])))
    return highs


def detect_pivot_lows(df: pd.DataFrame, left: int, right: int) -> List[Pivot]:
    lows: List[Pivot] = []
    for i in range(left, len(df) - right):
        segment = df["low"].iloc[i - left : i + right + 1]
        if df["low"].iloc[i] == segment.min() and (segment == segment.min()).sum() == 1:
            lows.append((i, float(df["low"].iloc[i])))
    return lows
