from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.replay import run_event_driven_replay
from parabolic_exhaustion.backtest.vectorized import run_vectorized_research
from parabolic_exhaustion.config import BacktestConfig, StrategyConfig
from parabolic_exhaustion.strategies.flow_strategy.backtest import prepare_flow_bars
from parabolic_exhaustion.strategies.flow_strategy.config import FlowParameterSet


def test_flow_features_include_expected_columns() -> None:
    strategy = _base_strategy()
    parameter_set = _base_parameter_set()
    prepared = prepare_flow_bars(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={"M5": _build_intraday_bars()},
        strategy_config=strategy,
        parameter_set=parameter_set,
    )

    expected = {
        "ema_fast",
        "ema_slow",
        "intraday_atr",
        "distance_from_vwap_atr",
        "vwap_slope_atr",
        "prev_daily_atr_pct",
        "daily_context_eligible",
        "rolling_swing_low",
        "rolling_swing_high",
    }
    assert expected.issubset(set(prepared.bars.columns))
    assert set(prepared.bars["opening_window_variant"]) == {"open_0930_1030"}


def test_flow_opening_window_filter_excludes_late_bars() -> None:
    strategy = _base_strategy()
    parameter_set = _base_parameter_set()
    prepared = prepare_flow_bars(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={"M5": _build_intraday_bars_with_late_segment()},
        strategy_config=strategy,
        parameter_set=parameter_set,
    )

    latest_ny_time = prepared.bars["timestamp"].dt.tz_convert("America/New_York").dt.strftime("%H:%M").max()
    assert latest_ny_time <= "10:30"
    assert "10:35" not in set(prepared.bars["timestamp"].dt.tz_convert("America/New_York").dt.strftime("%H:%M"))


def test_flow_strategy_vectorized_and_replay_paths(tmp_path: Path) -> None:
    strategy = _base_strategy()
    backtest = BacktestConfig()
    backtest.entry_mode = "next_bar_open"
    backtest.target_r = 1.0
    backtest.force_exit_minutes_before_close = 1
    parameter_set = _base_parameter_set()
    strategy_context = {"parameter_set": parameter_set}

    vectorized = run_vectorized_research(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={"M5": _build_intraday_bars()},
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path / "vectorized",
        strategy_type="flow_strategy",
        strategy_context=strategy_context,
    )
    replay = run_event_driven_replay(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={"M5": _build_intraday_bars()},
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path / "replay",
        strategy_type="flow_strategy",
        strategy_context=strategy_context,
    )

    assert not vectorized["signals"].empty
    assert not vectorized["trades"].empty
    assert not replay.trade_log.empty
    assert len(vectorized["trades"]) == len(replay.trade_log)
    assert set(replay.trade_log["direction"]) == {"long"}
    assert (tmp_path / "vectorized" / "candidate_list.csv").exists()
    assert (tmp_path / "replay" / "replay_trade_log.csv").exists()


def _base_strategy() -> StrategyConfig:
    strategy = StrategyConfig()
    strategy.flow_strategy.signal_timeframe = "M5"
    strategy.flow_strategy.markets = ["NAS100_USD", "US30_USD"]
    strategy.flow_strategy.use_kill_zones = False
    strategy.kill_zones.london.enabled = False
    strategy.kill_zones.new_york.enabled = False
    strategy.kill_zones.overlap.enabled = False
    return strategy


def _base_parameter_set() -> FlowParameterSet:
    return FlowParameterSet(
        id="flow_test",
        symbols=("NAS100_USD",),
        opening_window_variant="open_0930_1030",
        min_daily_atr_pct=0.10,
        min_vwap_slope_atr=0.0,
        pullback_distance_atr=1.0,
        max_extension_atr=3.0,
        stop_atr_buffer=0.10,
        stop_lookback_bars=2,
        target_r=1.0,
        partial_take_r=0.5,
        killzone_only=False,
        max_trades_per_day=2,
        notes="test",
    )


def _build_daily_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-01", periods=30, freq="D", tz="UTC")
    base = 20000.0
    closes = [base + (idx * 25.0) for idx in range(len(timestamps))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["NAS100_USD"] * len(timestamps),
            "open": closes,
            "high": [price + 120.0 for price in closes],
            "low": [price - 90.0 for price in closes],
            "close": closes,
            "volume": [1000 + (idx * 20) for idx in range(len(timestamps))],
            "asset_class": ["index"] * len(timestamps),
        }
    )


def _build_intraday_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=8, freq="5min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["NAS100_USD"] * len(timestamps),
            "open": [20700.0, 20708.0, 20715.0, 20706.0, 20712.0, 20722.0, 20736.0, 20748.0],
            "high": [20710.0, 20718.0, 20716.0, 20714.0, 20724.0, 20740.0, 20756.0, 20758.0],
            "low": [20696.0, 20704.0, 20702.0, 20700.0, 20710.0, 20720.0, 20732.0, 20740.0],
            "close": [20708.0, 20715.0, 20706.0, 20712.0, 20722.0, 20736.0, 20748.0, 20752.0],
            "volume": [120.0, 130.0, 150.0, 140.0, 160.0, 180.0, 170.0, 150.0],
        }
    )


def _build_intraday_bars_with_late_segment() -> pd.DataFrame:
    early = _build_intraday_bars()
    late_times = pd.date_range("2026-01-30 15:10:00+00:00", periods=6, freq="5min")
    late = pd.DataFrame(
        {
            "timestamp": late_times,
            "symbol": ["NAS100_USD"] * len(late_times),
            "open": [20754.0, 20758.0, 20762.0, 20766.0, 20770.0, 20768.0],
            "high": [20760.0, 20764.0, 20768.0, 20772.0, 20774.0, 20772.0],
            "low": [20750.0, 20754.0, 20758.0, 20762.0, 20766.0, 20760.0],
            "close": [20758.0, 20762.0, 20766.0, 20770.0, 20768.0, 20762.0],
            "volume": [140.0, 145.0, 150.0, 135.0, 130.0, 125.0],
        }
    )
    return pd.concat([early, late], ignore_index=True)
