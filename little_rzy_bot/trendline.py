"""Trendline helpers for structure validation."""
from typing import Tuple


def line_from_points(p1: Tuple[int, float], p2: Tuple[int, float]) -> Tuple[float, float]:
    x1, y1 = p1
    x2, y2 = p2
    slope = (y2 - y1) / (x2 - x1)
    intercept = y1 - slope * x1
    return slope, intercept


def line_value(slope: float, intercept: float, x: int) -> float:
    return slope * x + intercept
