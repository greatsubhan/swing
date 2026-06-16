from __future__ import annotations

import pandas as pd

from research.cwt_sl_forensics import (
    VariantSpec,
    _select_first_signals,
    _simulate_variant,
)


def test_select_first_signals_suppresses_post_tp_cluster_but_allows_after_sl() -> None:
    entries = [
        {
            "setup_id": "a",
            "symbol": "NAS100_USD",
            "timeframe": "5m",
            "side": "long",
            "signal_timestamp": "2026-04-15T10:00:00+00:00",
            "status": "closed",
            "outcome": "tp_hit",
            "is_root_signal": True,
        },
        {
            "setup_id": "b",
            "symbol": "NAS100_USD",
            "timeframe": "5m",
            "side": "long",
            "signal_timestamp": "2026-04-15T10:20:00+00:00",
            "status": "closed",
            "outcome": "sl_hit",
            "is_root_signal": True,
        },
        {
            "setup_id": "c",
            "symbol": "NAS100_USD",
            "timeframe": "5m",
            "side": "long",
            "signal_timestamp": "2026-04-15T11:10:00+00:00",
            "status": "closed",
            "outcome": "sl_hit",
            "is_root_signal": True,
        },
        {
            "setup_id": "d",
            "symbol": "NAS100_USD",
            "timeframe": "5m",
            "side": "long",
            "signal_timestamp": "2026-04-15T11:20:00+00:00",
            "status": "closed",
            "outcome": "tp_hit",
            "is_root_signal": True,
        },
    ]

    selected, suppressed = _select_first_signals(entries)

    assert [entry["setup_id"] for entry in selected] == ["a", "c", "d"]
    assert suppressed == {"b": "same_direction_post_tp_cluster"}


def test_wider_stop_cannot_stop_earlier_than_baseline() -> None:
    frame = pd.DataFrame(
        [
            {"timestamp": "2026-04-15T10:00:00+00:00", "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "atr14": 4.0},
            {"timestamp": "2026-04-15T10:05:00+00:00", "open": 100.0, "high": 100.2, "low": 98.9, "close": 99.4, "atr14": 4.0},
            {"timestamp": "2026-04-15T10:10:00+00:00", "open": 99.4, "high": 101.5, "low": 99.2, "close": 101.2, "atr14": 4.0},
        ]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp")

    trade = {
        "symbol": "NAS100_USD",
        "side": "long",
        "entry": 100.0,
        "stop_loss": 99.0,
        "target_1": 101.0,
        "_entry_index": 0,
        "duplicate_cluster_exposure": False,
        "high_noise_session": False,
    }

    baseline = _simulate_variant(
        trade,
        frame,
        VariantSpec("baseline", "Baseline"),
        {"NAS100_USD": 1.0},
    )
    widened = _simulate_variant(
        trade,
        frame,
        VariantSpec("wider", "Wider", stop_scale=1.2),
        {"NAS100_USD": 1.0},
    )

    assert baseline["outcome"] == "sl_hit"
    assert widened["outcome"] == "tp_hit"
    assert widened["bars_checked"] >= baseline["bars_checked"]
