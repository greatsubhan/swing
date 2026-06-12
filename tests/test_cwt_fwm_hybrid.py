from __future__ import annotations

import pandas as pd

from research.cwt_fwm_hybrid import (
    PendingFwmOrder,
    detect_fwm_candidate,
    maybe_trigger_fwm_order,
)


def _frame_for_long_candidate() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=10, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [101, 101, 100, 100, 99, 98.5, 98.0, 97.7, 98.1, 98.8],
            "high": [102, 102, 101, 101, 100, 99.2, 98.9, 98.8, 99.2, 99.5],
            "low": [100, 100, 99, 99, 98, 97.8, 97.3, 96.8, 97.9, 98.4],
            "close": [101, 100.5, 100, 99.8, 98.8, 98.2, 98.5, 98.6, 99.0, 99.3],
            "jaw": [100.5, 100.3, 100.1, 99.9, 99.7, 99.4, 99.1, 98.7, 98.5, 98.4],
            "teeth": [100.2, 100.0, 99.8, 99.6, 99.4, 99.0, 98.8, 98.5, 98.4, 98.3],
            "lips": [99.9, 99.7, 99.5, 99.3, 99.0, 98.6, 98.3, 98.4, 98.6, 98.8],
            "atr14": [0.4] * 10,
            "bias_signal": [1] * 10,
        },
        index=index,
    )
    return frame


def test_detect_fwm_candidate_long() -> None:
    frame = _frame_for_long_candidate()
    candidate = detect_fwm_candidate(frame, 7, 1)
    assert candidate is not None
    assert candidate["side"] == "long"
    assert float(candidate["trigger_price"]) > float(frame.iloc[7]["high"])
    assert float(candidate["stop_price"]) < float(frame.iloc[7]["low"])


def test_detect_fwm_candidate_rejects_wrong_bias() -> None:
    frame = _frame_for_long_candidate()
    candidate = detect_fwm_candidate(frame, 7, -1)
    assert candidate is None


def test_pending_fwm_order_expires_after_two_bars() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.1, 100.2, 100.1, 100.0, 99.9],
            "high": [100.2, 100.3, 100.4, 100.45, 100.3, 100.2],
            "low": [99.8, 99.9, 99.95, 99.9, 99.8, 99.7],
            "close": [100.1, 100.2, 100.15, 100.0, 99.95, 99.85],
            "bias_signal": [1] * 6,
        },
        index=index,
    )
    order = PendingFwmOrder(
        symbol="EUR_USD",
        timeframe="5m",
        side="long",
        signal_time=index[0],
        signal_index=0,
        activate_index=1,
        expire_index=2,
        trigger_price=101.0,
        stop_price=99.0,
        target_price=103.0,
        initial_risk=2.0,
    )
    pending, position = maybe_trigger_fwm_order(order, frame, 3)
    assert pending is None
    assert position is None
