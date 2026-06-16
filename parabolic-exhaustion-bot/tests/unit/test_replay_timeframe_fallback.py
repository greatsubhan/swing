from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.replay import run_event_driven_replay
from parabolic_exhaustion.config import BacktestConfig, StrategyConfig


def test_replay_accepts_single_m15_timeframe(tmp_path: Path) -> None:
    strategy = StrategyConfig()
    strategy.filters.extension.mode = "atr_multiple"
    strategy.filters.extension.min_value = 2.0
    strategy.filters.volume_rank_min = 0.6
    strategy.filters.min_parabolic_slope_score = 20.0
    strategy.risk.partial_take_r = 1.0
    strategy.sessions["new_york"].end_time = "09:45"

    backtest = BacktestConfig()
    backtest.target_r = 2.0
    backtest.entry_mode = "bar_close"
    backtest.force_exit_minutes_before_close = 0

    result = run_event_driven_replay(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={"M15": _build_m15_bars()},
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path,
    )

    assert not result.transition_log.empty
    assert set(result.transition_log["bar_timeframe"]) == {"M15"}


def _build_daily_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=30, freq="D")
    closes = [100, 101, 102, 103, 104, 104, 104, 105, 106, 108, 110, 113, 116, 120, 123, 126, 129, 133, 138, 143, 148, 150, 152, 154, 156, 158, 160, 162, 165, 168]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": closes,
            "high": [price + 1.5 for price in closes],
            "low": [price - 1.0 for price in closes],
            "close": closes,
            "volume": [1000 + (idx * 50) for idx in range(len(timestamps))],
            "asset_class": ["metal"] * len(timestamps),
        }
    )


def _build_m15_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=6, freq="15min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 168.6, 168.0, 167.2, 166.4, 166.1],
            "high": [169.0, 168.8, 168.2, 167.3, 166.7, 166.2],
            "low": [167.7, 167.8, 166.8, 165.8, 165.6, 165.9],
            "close": [168.7, 168.0, 167.0, 166.2, 166.0, 166.1],
            "volume": [500, 700, 900, 850, 800, 600],
        }
    )
