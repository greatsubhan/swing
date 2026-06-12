from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.vectorized import run_vectorized_research
from parabolic_exhaustion.config import BacktestConfig, ParameterGridConfig, StrategyConfig


def test_vectorized_research_creates_expected_exports(tmp_path: Path) -> None:
    daily_bars = _build_daily_bars()
    intraday_bars = {"1m": _build_intraday_bars()}

    strategy = StrategyConfig()
    strategy.intraday_timeframes = ["1m"]
    strategy.signal_timeframe = "1m"
    strategy.filters.extension.mode = "atr_multiple"
    strategy.filters.extension.min_value = 2.0
    strategy.filters.volume_rank_min = 0.6
    strategy.filters.min_parabolic_slope_score = 20.0

    backtest = BacktestConfig(
        parameter_grid=ParameterGridConfig(
            extension_modes=["atr_multiple"],
            extension_values=[2.0],
            volume_rank_values=[0.6],
            slope_score_values=[20.0],
            signal_timeframes=["1m"],
            target_r_values=[1.0],
            stop_buffer_points=[0.0],
        )
    )

    artifacts = run_vectorized_research(
        daily_bars=daily_bars,
        intraday_bars_by_timeframe=intraday_bars,
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path,
    )

    assert len(artifacts.parameter_results) == 1
    result = artifacts.parameter_results[0]
    assert not result.candidates.empty
    assert not result.signals.empty
    assert not result.trades.empty
    assert float(result.summary.iloc[0]["trade_count"]) == 1
    assert set(result.signals["kill_zone_name"]) == {"new_york_kill_zone+london_new_york_overlap"}
    assert set(result.signals["alert_priority"]) == {"high"}

    parameter_dir = tmp_path / result.parameter_set.name
    assert (tmp_path / "parameter_comparison.csv").exists()
    assert (parameter_dir / "candidate_list.csv").exists()
    assert (parameter_dir / "signal_table.csv").exists()
    assert (parameter_dir / "trade_log.csv").exists()
    assert (parameter_dir / "summary_metrics.csv").exists()


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


def _build_intraday_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=8, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 169.0, 168.5, 167.8, 167.2, 166.8, 166.4, 166.0],
            "high": [169.0, 169.4, 168.8, 168.2, 167.9, 167.0, 166.6, 166.2],
            "low": [167.8, 168.2, 167.5, 167.0, 166.9, 165.2, 165.8, 165.6],
            "close": [168.8, 168.4, 167.7, 167.2, 167.0, 165.4, 166.0, 165.8],
            "volume": [100, 110, 160, 200, 180, 220, 210, 150],
        }
    )
