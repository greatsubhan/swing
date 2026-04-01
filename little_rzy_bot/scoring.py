"""Setup scoring for 0-100 quality score."""
from .config import EngineConfig


def score_setup(trend_state: str, rr: float, trend_maturity: int, bb_bias: float, cfg: EngineConfig) -> int:
    w = cfg.score_weights
    score = 0.0
    score += w.trend_clarity if trend_state in {"bullish", "bearish"} else 0
    score += min(w.rr_quality, max(0.0, rr / 3.0) * w.rr_quality)
    score += max(0.0, w.trend_maturity - max(0, trend_maturity - 2) * 2)
    score += min(w.bollinger_context, max(0.0, bb_bias) * w.bollinger_context)
    score += w.setup_freshness if hasattr(w, "setup_freshness") else w.freshness
    score += w.impulse_quality * 0.8
    score += w.pullback_cleanliness * 0.8
    score += w.trendline_quality * 0.8
    score += w.regime_suitability * 0.8
    return int(max(0, min(100, round(score))))


def grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"
