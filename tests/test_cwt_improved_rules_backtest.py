from __future__ import annotations

import pandas as pd

from research.cwt_improved_rules_backtest import _max_drawdown_pct, _simulate_improved_combo


def test_max_drawdown_pct_uses_equity_curve() -> None:
    curve = [100_000.0, 110_000.0, 99_000.0, 105_000.0]
    assert round(_max_drawdown_pct(curve), 2) == 10.0


def test_improved_combo_waits_for_confirmation_then_enters_next_bar() -> None:
    frame = pd.DataFrame(
        [
            {"timestamp": "2026-04-15T10:00:00+00:00", "open": 100.0, "high": 101.0, "low": 99.8, "close": 100.8, "atr14": 2.0},
            {"timestamp": "2026-04-15T10:05:00+00:00", "open": 100.9, "high": 101.4, "low": 100.7, "close": 101.2, "atr14": 2.0},
            {"timestamp": "2026-04-15T10:10:00+00:00", "open": 101.3, "high": 102.1, "low": 101.1, "close": 101.9, "atr14": 2.0},
        ]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp")
    row = {
        "symbol": "NAS100_USD",
        "side": "long",
        "entry": 100.4,
        "stop_loss": 99.9,
        "target_1": 101.9,
        "_entry_index": 0,
        "duplicate_cluster_exposure": False,
        "high_noise_session": False,
    }

    result = _simulate_improved_combo(row, frame, {"NAS100_USD": 0.5})

    assert result["status"] == "closed"
    assert result["outcome"] == "tp_hit"
    assert result["entry_price"] == 100.9
