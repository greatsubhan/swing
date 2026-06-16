import pandas as pd

from parabolic_exhaustion.features.intraday import engineer_intraday_features


def test_engineer_intraday_features_detects_vwap_reclaim_failure() -> None:
    timestamps = pd.date_range("2026-02-02 09:30:00", periods=6, freq="min")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["SMCI"] * len(timestamps),
            "open": [100.0, 102.0, 101.0, 99.0, 98.5, 98.2],
            "high": [102.0, 103.0, 101.5, 100.5, 99.2, 98.8],
            "low": [99.8, 100.5, 98.8, 98.4, 97.8, 97.5],
            "close": [101.8, 101.0, 99.1, 98.9, 98.0, 97.7],
            "volume": [1000, 1200, 1600, 1800, 1700, 1500],
        }
    )

    features = engineer_intraday_features(frame)

    assert features["vwap_session"].notna().all()
    assert features["vwap_cross_down_flag"].any()
    assert features["vwap_reclaim_fail_flag"].any()
    assert features["retest_count_vwap"].max() >= 1
