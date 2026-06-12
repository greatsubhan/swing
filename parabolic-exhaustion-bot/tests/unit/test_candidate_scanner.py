import pandas as pd

from parabolic_exhaustion.config import StrategyConfig
from parabolic_exhaustion.signals.candidates import scan_daily_candidates


def test_candidate_scanner_flags_high_extension_candidate() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=3, freq="D"),
            "symbol": ["XAU_USD"] * 3,
            "extension_from_base_atr": [1.5, 2.2, 3.8],
            "extension_from_base_points": [10.0, 15.0, 24.0],
            "extension_from_base_pct": [4.5, 6.5, 10.0],
            "rolling_volume_rank_60d": [0.6, 0.8, 0.98],
            "highest_close_20d": [110.0, 115.0, 120.0],
            "close": [108.5, 114.8, 119.8],
            "parabolic_slope_score": [45.0, 62.0, 91.0],
            "round_number_proximity": [1.5, 0.7, 0.2],
            "asset_class": ["metal", "metal", "metal"],
        }
    )

    results = scan_daily_candidates(frame, StrategyConfig())
    latest = results.iloc[-1]

    assert bool(latest["daily_candidate"]) is True
    assert latest["parabolic_exhaustion_score"] > 50
    assert latest["extension_metric_name"] == "extension_from_base_atr"
    assert "extension_from_base_atr" in latest["candidate_reason"]
