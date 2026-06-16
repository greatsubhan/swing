import pandas as pd

from parabolic_exhaustion.features.daily import engineer_daily_features


def test_engineer_daily_features_computes_multiple_extension_metrics() -> None:
    timestamps = pd.date_range("2026-01-01", periods=40, freq="D")
    closes = [100 + i for i in range(15)] + [114, 114, 115, 116, 118] + [125, 132, 145, 160, 180] + [190] * 15
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": closes,
            "high": [value * 1.02 for value in closes],
            "low": [value * 0.98 for value in closes],
            "close": closes,
            "volume": [1_000 + (i * 25) for i in range(len(timestamps))],
            "asset_class": ["metal"] * len(timestamps),
        }
    )

    features = engineer_daily_features(frame)
    latest = features.iloc[-1]

    assert latest["recent_base_price"] > 0
    assert latest["extension_from_base_points"] > 0
    assert latest["extension_from_base_pct"] > 40
    assert latest["extension_from_base_atr"] > 1
    assert 0 <= latest["parabolic_slope_score"] <= 100
