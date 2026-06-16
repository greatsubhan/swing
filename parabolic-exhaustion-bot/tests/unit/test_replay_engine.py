from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.replay import run_event_driven_replay
from parabolic_exhaustion.config import BacktestConfig, StrategyConfig
from parabolic_exhaustion.execution.state_machine import ReplayState


def test_replay_happy_path_partial_add_and_forced_exit(tmp_path: Path) -> None:
    strategy, backtest = _base_configs()
    strategy.sessions["new_york"].end_time = "09:38"
    strategy.risk.partial_take_r = 1.0
    backtest.target_r = 2.0

    result = run_event_driven_replay(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={
            "1m": _build_happy_path_1m(),
            "5m": _build_5m_context(),
        },
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path,
    )

    assert len(result.trade_log) == 1
    trade = result.trade_log.iloc[0]
    assert bool(trade["partial_taken"]) is True
    assert trade["add_count"] == 1
    assert trade["exit_reason"] == "SESSION_END"
    assert trade["alert_priority"] == "high"
    assert (result.transition_log["new_state"] == ReplayState.ADD_TRIGGERED).any()
    assert (tmp_path / "replay_trade_log.csv").exists()
    assert (tmp_path / "state_transition_log.csv").exists()
    assert (tmp_path / "replay_summary_metrics.csv").exists()
    assert (tmp_path / "per_instrument_diagnostics.csv").exists()


def test_replay_pre_entry_invalidation_has_no_trade(tmp_path: Path) -> None:
    strategy, backtest = _base_configs()

    result = run_event_driven_replay(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={
            "1m": _build_invalidation_1m(),
            "5m": _build_5m_context(),
        },
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path,
    )

    assert result.trade_log.empty
    assert (result.transition_log["new_state"] == ReplayState.INVALIDATED).any()


def test_replay_break_even_stop_after_partial(tmp_path: Path) -> None:
    strategy, backtest = _base_configs()
    strategy.risk.partial_take_r = 1.0
    strategy.risk.enable_risk_free_add = False
    backtest.target_r = 2.0

    result = run_event_driven_replay(
        daily_bars=_build_daily_bars(),
        intraday_bars_by_timeframe={
            "1m": _build_break_even_stop_1m(),
            "5m": _build_5m_context(),
        },
        strategy_config=strategy,
        backtest_config=backtest,
        output_dir=tmp_path,
    )

    assert len(result.trade_log) == 1
    trade = result.trade_log.iloc[0]
    assert bool(trade["partial_taken"]) is True
    assert trade["exit_reason"] == "STOP_HIT"
    assert (result.transition_log["new_state"] == ReplayState.BREAK_EVEN_PROTECTED).any()


def _base_configs() -> tuple[StrategyConfig, BacktestConfig]:
    strategy = StrategyConfig()
    strategy.filters.extension.mode = "atr_multiple"
    strategy.filters.extension.min_value = 2.0
    strategy.filters.volume_rank_min = 0.6
    strategy.filters.min_parabolic_slope_score = 20.0
    strategy.max_attempts_per_symbol_per_day = 2

    backtest = BacktestConfig()
    backtest.force_exit_minutes_before_close = 1
    backtest.stop_buffer_points = 0.0
    return strategy, backtest


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


def _build_happy_path_1m() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=8, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 168.8, 168.4, 167.6, 167.3, 166.8, 166.4, 166.5],
            "high": [169.0, 169.4, 168.8, 168.1, 167.4, 167.5, 166.8, 166.7],
            "low": [167.8, 168.2, 167.5, 167.0, 166.1, 166.2, 166.0, 166.2],
            "close": [168.8, 168.4, 167.7, 167.4, 166.4, 166.5, 166.3, 166.4],
            "volume": [100, 110, 160, 200, 180, 220, 210, 150],
        }
    )


def _build_invalidation_1m() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=4, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 168.8, 168.4, 168.8],
            "high": [169.0, 169.4, 169.1, 169.0],
            "low": [167.8, 168.2, 167.8, 168.5],
            "close": [168.8, 168.4, 168.9, 168.8],
            "volume": [100, 120, 160, 150],
        }
    )


def _build_break_even_stop_1m() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-30 14:30:00+00:00", periods=6, freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD"] * len(timestamps),
            "open": [168.0, 168.8, 168.4, 167.2, 167.0, 166.9],
            "high": [169.0, 169.4, 168.8, 167.9, 167.4, 167.3],
            "low": [167.8, 168.2, 167.5, 166.7, 165.4, 166.8],
            "close": [168.8, 168.4, 167.7, 167.0, 165.8, 167.1],
            "volume": [100, 110, 160, 200, 180, 220],
        }
    )


def _build_5m_context() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2026-01-30 14:30:00+00:00",
            "2026-01-30 14:35:00+00:00",
        ]
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["XAU_USD", "XAU_USD"],
            "open": [168.0, 166.8],
            "high": [169.4, 167.1],
            "low": [167.5, 165.8],
            "close": [167.7, 165.9],
            "volume": [750, 760],
        }
    )
