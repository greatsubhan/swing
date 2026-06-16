from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from parabolic_exhaustion.backtest.metrics import summarize_trade_log
from parabolic_exhaustion.backtest.vectorized import annotate_intraday_context, session_cutoff_timestamp
from parabolic_exhaustion.config import BacktestConfig, StrategyConfig
from parabolic_exhaustion.execution.state_machine import ReplayState
from parabolic_exhaustion.features.daily import engineer_daily_features
from parabolic_exhaustion.features.intraday import engineer_intraday_features
from parabolic_exhaustion.reporting.exports import export_dataframe
from parabolic_exhaustion.strategies.flow_strategy.config import (
    FlowParameterSet,
    apply_opening_window_filter,
)
from parabolic_exhaustion.strategies.flow_strategy.features import engineer_flow_features
from parabolic_exhaustion.strategies.flow_strategy.rules import (
    build_flow_candidate_table,
    build_flow_signal_table,
)


Direction = Literal["long", "short"]


@dataclass
class FlowReplayResult:
    trade_log: pd.DataFrame
    transition_log: pd.DataFrame
    summary_metrics: pd.DataFrame
    instrument_diagnostics: pd.DataFrame


@dataclass
class FlowPreparedBars:
    bars: pd.DataFrame
    daily_features: pd.DataFrame


@dataclass
class FlowPosition:
    direction: Direction
    entry_price: float
    entry_timestamp: pd.Timestamp
    stop_price: float
    partial_target_price: float
    final_target_price: float
    risk_points: float
    partial_taken: bool = False
    break_even_protected: bool = False
    realized_pnl_points: float = 0.0
    realized_size: float = 0.0
    remaining_size: float = 1.0


def run_flow_vectorized_research(
    *,
    daily_bars: pd.DataFrame,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
    output_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    prepared = prepare_flow_bars(
        daily_bars=daily_bars,
        intraday_bars_by_timeframe=intraday_bars_by_timeframe,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    candidates = build_flow_candidate_table(
        prepared.bars,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    signals = build_flow_signal_table(
        prepared.bars,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    trades = simulate_flow_trades(
        prepared.bars,
        signals=signals,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        parameter_set=parameter_set,
    )
    summary = summarize_trade_log(
        trades,
        candidate_count=len(candidates),
        signal_count=len(signals),
        parameter_set=parameter_set.id,
    )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    export_dataframe(candidates, root / "candidate_list.csv")
    export_dataframe(signals, root / "signal_table.csv")
    export_dataframe(trades, root / "trade_log.csv")
    export_dataframe(summary, root / "summary_metrics.csv")
    return {
        "candidates": candidates,
        "signals": signals,
        "trades": trades,
        "summary": summary,
    }


def run_flow_replay(
    *,
    daily_bars: pd.DataFrame,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
    output_dir: str | Path,
) -> FlowReplayResult:
    prepared = prepare_flow_bars(
        daily_bars=daily_bars,
        intraday_bars_by_timeframe=intraday_bars_by_timeframe,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    candidates = build_flow_candidate_table(
        prepared.bars,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    signals = build_flow_signal_table(
        prepared.bars,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    trade_log, transition_log = replay_flow_trades(
        prepared.bars,
        signals=signals,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        parameter_set=parameter_set,
    )
    summary_metrics = summarize_trade_log(
        trade_log,
        candidate_count=len(candidates),
        signal_count=len(signals),
        parameter_set=parameter_set.id,
    )
    instrument_diagnostics = build_flow_instrument_diagnostics(
        candidates=candidates,
        trades=trade_log,
        transitions=transition_log,
    )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    export_dataframe(trade_log, root / "replay_trade_log.csv")
    export_dataframe(transition_log, root / "state_transition_log.csv")
    export_dataframe(summary_metrics, root / "replay_summary_metrics.csv")
    export_dataframe(instrument_diagnostics, root / "per_instrument_diagnostics.csv")
    return FlowReplayResult(
        trade_log=trade_log,
        transition_log=transition_log,
        summary_metrics=summary_metrics,
        instrument_diagnostics=instrument_diagnostics,
    )


def prepare_flow_bars(
    *,
    daily_bars: pd.DataFrame,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
    parameter_set: FlowParameterSet,
) -> FlowPreparedBars:
    timeframe = strategy_config.flow_strategy.signal_timeframe
    intraday_bars = intraday_bars_by_timeframe.get(timeframe)
    if intraday_bars is None or intraday_bars.empty:
        available = ", ".join(sorted(intraday_bars_by_timeframe))
        raise ValueError(f"Flow strategy requires {timeframe} intraday bars. Available: {available}")

    daily_features = engineer_daily_features(daily_bars)
    intraday_features = annotate_intraday_context(engineer_intraday_features(intraday_bars), strategy_config)
    intraday_features["bar_timeframe"] = timeframe
    intraday_features["trade_date"] = intraday_features["timestamp"].dt.floor("D")
    flow_bars = engineer_flow_features(
        intraday_features,
        daily_features=daily_features,
        flow_config=strategy_config.flow_strategy,
    )
    if strategy_config.flow_strategy.require_session_alignment:
        flow_bars = flow_bars.loc[flow_bars["session_name"].notna()].copy()
    flow_bars = apply_opening_window_filter(
        flow_bars,
        strategy_config=strategy_config,
        parameter_set=parameter_set,
    )
    flow_bars["rolling_swing_low"] = flow_bars.groupby(["symbol", "trade_date"])["low"].transform(
        lambda series: series.rolling(parameter_set.stop_lookback_bars, min_periods=1).min()
    )
    flow_bars["rolling_swing_high"] = flow_bars.groupby(["symbol", "trade_date"])["high"].transform(
        lambda series: series.rolling(parameter_set.stop_lookback_bars, min_periods=1).max()
    )
    return FlowPreparedBars(bars=flow_bars, daily_features=daily_features)


def simulate_flow_trades(
    bars: pd.DataFrame,
    *,
    signals: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
) -> pd.DataFrame:
    trades, _ = replay_flow_trades(
        bars,
        signals=signals,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        parameter_set=parameter_set,
    )
    return trades


def replay_flow_trades(
    bars: pd.DataFrame,
    *,
    signals: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if signals.empty:
        return pd.DataFrame(), pd.DataFrame()

    trades: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    for (symbol, trade_date), day_bars in bars.groupby(["symbol", "trade_date"], sort=True):
        day_signals = signals.loc[
            (signals["symbol"] == symbol)
            & (signals["trade_date"] == trade_date)
        ].sort_values("timestamp")
        if day_signals.empty:
            continue
        day_trades, day_transitions = _replay_flow_day(
            day_bars=day_bars.reset_index(drop=True),
            signals=day_signals.reset_index(drop=True),
            strategy_config=strategy_config,
            backtest_config=backtest_config,
            parameter_set=parameter_set,
        )
        trades.extend(day_trades)
        transitions.extend(day_transitions)

    trade_log = pd.DataFrame(trades)
    if not trade_log.empty:
        trade_log = trade_log.sort_values(["symbol", "entry_timestamp"]).reset_index(drop=True)
    transition_log = pd.DataFrame(transitions)
    if not transition_log.empty:
        transition_log = transition_log.sort_values(["symbol", "timestamp", "sequence"]).reset_index(drop=True)
    return trade_log, transition_log


def build_flow_instrument_diagnostics(
    *,
    candidates: pd.DataFrame,
    trades: pd.DataFrame,
    transitions: pd.DataFrame,
) -> pd.DataFrame:
    diagnostics = candidates.groupby("symbol", as_index=False).agg(
        candidate_days=("candidate_date", "count")
    )
    if not trades.empty:
        trade_stats = trades.groupby("symbol", as_index=False).agg(
            trade_count=("trade_id", "count"),
            total_r=("r_multiple", "sum"),
            average_hold_minutes=("hold_minutes", "mean"),
        )
        diagnostics = diagnostics.merge(trade_stats, on="symbol", how="left")
    if not transitions.empty:
        transition_stats = transitions.groupby("symbol", as_index=False).agg(
            transition_count=("sequence", "count"),
            exit_count=("new_state", lambda series: int((series == ReplayState.EXITED).sum())),
        )
        diagnostics = diagnostics.merge(transition_stats, on="symbol", how="left")
    return diagnostics.fillna(0.0)


def _replay_flow_day(
    *,
    day_bars: pd.DataFrame,
    signals: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    trades: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    current_state = ReplayState.NO_SETUP
    sequence = 0
    trades_taken = 0
    pending_signal: pd.Series | None = None
    position: FlowPosition | None = None
    signal_lookup = {pd.Timestamp(row.timestamp): row for row in signals.itertuples(index=False)}
    trade_counter = 0

    for bar in day_bars.itertuples(index=False):
        bar_time = pd.Timestamp(bar.timestamp)
        if current_state == ReplayState.NO_SETUP and bool(getattr(bar, "daily_context_eligible", False)):
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.DAILY_CANDIDATE,
                "daily ATR regime eligible",
                bar,
                sequence,
            )
        if current_state == ReplayState.DAILY_CANDIDATE and bar.session_name is not None:
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.EXHAUSTION_WATCH,
                "active session window",
                bar,
                sequence,
            )

        if pending_signal is not None and position is None:
            position = _open_flow_position(
                pending_signal=pending_signal,
                bar=bar,
                strategy_config=strategy_config,
                backtest_config=backtest_config,
                parameter_set=parameter_set,
            )
            pending_signal = None
            if position is not None:
                trades_taken += 1
                trade_counter += 1
                current_state, sequence = _record_transition(
                    transitions,
                    current_state,
                    ReplayState.ENTRY_TRIGGERED,
                    "flow entry executed",
                    bar,
                    sequence,
                )

        signal_row = signal_lookup.get(bar_time)
        if signal_row is not None and position is None:
            if current_state != ReplayState.VWAP_LOST:
                current_state, sequence = _record_transition(
                    transitions,
                    current_state,
                    ReplayState.VWAP_LOST,
                    "trend and VWAP anchor aligned",
                    bar,
                    sequence,
                )
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.VWAP_RETEST_PENDING,
                "VWAP pullback trigger armed",
                bar,
                sequence,
            )
            if trades_taken < parameter_set.max_trades_per_day:
                pending_signal = pd.Series(signal_row._asdict())

        if position is None:
            continue

        current_state, sequence, trade = _manage_open_flow_position(
            position=position,
            bar=bar,
            current_state=current_state,
            sequence=sequence,
            transitions=transitions,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
            trade_id=f"{bar.symbol}-{pd.Timestamp(bar.timestamp).strftime('%Y%m%d')}-{trade_counter}",
            parameter_set_id=parameter_set.id,
        )
        if trade is not None:
            trades.append(trade)
            position = None

    return trades, transitions


def _open_flow_position(
    *,
    pending_signal: pd.Series,
    bar,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: FlowParameterSet,
) -> FlowPosition | None:
    entry_price = float(bar.close if backtest_config.entry_mode == "bar_close" else bar.open)
    stop_reference = float(pending_signal["stop_reference_price"])
    atr_buffer = float(pending_signal["intraday_atr"]) * parameter_set.stop_atr_buffer
    direction = str(pending_signal["direction"])

    if direction == "long":
        stop_price = stop_reference - atr_buffer
        risk_points = entry_price - stop_price
        partial_target = entry_price + (risk_points * strategy_config.risk.partial_take_r)
        final_target = entry_price + (risk_points * backtest_config.target_r)
    else:
        stop_price = stop_reference + atr_buffer
        risk_points = stop_price - entry_price
        partial_target = entry_price - (risk_points * strategy_config.risk.partial_take_r)
        final_target = entry_price - (risk_points * backtest_config.target_r)

    if risk_points <= 0:
        return None
    return FlowPosition(
        direction=direction,  # type: ignore[arg-type]
        entry_price=entry_price,
        entry_timestamp=pd.Timestamp(bar.timestamp),
        stop_price=stop_price,
        partial_target_price=partial_target,
        final_target_price=final_target,
        risk_points=risk_points,
    )


def _manage_open_flow_position(
    *,
    position: FlowPosition,
    bar,
    current_state: ReplayState,
    sequence: int,
    transitions: list[dict[str, object]],
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    trade_id: str,
    parameter_set_id: str,
) -> tuple[ReplayState, int, dict[str, object] | None]:
    if not position.partial_taken and _partial_hit(position, bar):
        _take_partial(position, strategy_config)
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.PARTIAL_TAKEN,
            "partial target reached",
            bar,
            sequence,
        )
        if strategy_config.risk.move_stop_to_break_even_after_partial:
            position.stop_price = position.entry_price
            position.break_even_protected = True
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.BREAK_EVEN_PROTECTED,
                "stop moved to break-even",
                bar,
                sequence,
            )

    if _stop_hit(position, bar):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "stop hit",
            bar,
            sequence,
        )
        return current_state, sequence, _close_flow_trade(
            position=position,
            bar=bar,
            exit_price=position.stop_price,
            exit_reason="STOP_HIT",
            backtest_config=backtest_config,
            trade_id=trade_id,
            parameter_set_id=parameter_set_id,
        )

    if _target_hit(position, bar):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "final target reached",
            bar,
            sequence,
        )
        return current_state, sequence, _close_flow_trade(
            position=position,
            bar=bar,
            exit_price=position.final_target_price,
            exit_reason="TARGET_HIT",
            backtest_config=backtest_config,
            trade_id=trade_id,
            parameter_set_id=parameter_set_id,
        )

    if _vwap_invalidation(position, bar):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.INVALIDATED,
            "VWAP invalidation",
            bar,
            sequence,
        )
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "invalidated position exited",
            bar,
            sequence,
        )
        return current_state, sequence, _close_flow_trade(
            position=position,
            bar=bar,
            exit_price=float(bar.close),
            exit_reason="INVALIDATED",
            backtest_config=backtest_config,
            trade_id=trade_id,
            parameter_set_id=parameter_set_id,
        )

    cutoff = session_cutoff_timestamp(pd.Timestamp(bar.timestamp), str(bar.session_name), strategy_config, backtest_config)
    if pd.Timestamp(bar.timestamp) >= cutoff:
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "forced session exit",
            bar,
            sequence,
        )
        return current_state, sequence, _close_flow_trade(
            position=position,
            bar=bar,
            exit_price=float(bar.close),
            exit_reason="SESSION_END",
            backtest_config=backtest_config,
            trade_id=trade_id,
            parameter_set_id=parameter_set_id,
        )

    return current_state, sequence, None


def _take_partial(position: FlowPosition, strategy_config: StrategyConfig) -> None:
    partial_fraction = strategy_config.risk.partial_take_size_pct / 100.0
    closed_size = min(position.remaining_size, partial_fraction)
    realized = _pnl_points(position.direction, position.entry_price, position.partial_target_price) * closed_size
    position.realized_pnl_points += realized
    position.realized_size += closed_size
    position.remaining_size -= closed_size
    position.partial_taken = True


def _partial_hit(position: FlowPosition, bar) -> bool:
    if position.direction == "long":
        return float(bar.high) >= position.partial_target_price
    return float(bar.low) <= position.partial_target_price


def _target_hit(position: FlowPosition, bar) -> bool:
    if position.direction == "long":
        return float(bar.high) >= position.final_target_price
    return float(bar.low) <= position.final_target_price


def _stop_hit(position: FlowPosition, bar) -> bool:
    if position.direction == "long":
        return float(bar.low) <= position.stop_price
    return float(bar.high) >= position.stop_price


def _vwap_invalidation(position: FlowPosition, bar) -> bool:
    if position.partial_taken:
        return False
    if position.direction == "long":
        return float(bar.close) < float(bar.vwap_session)
    return float(bar.close) > float(bar.vwap_session)


def _close_flow_trade(
    *,
    position: FlowPosition,
    bar,
    exit_price: float,
    exit_reason: str,
    backtest_config: BacktestConfig,
    trade_id: str,
    parameter_set_id: str,
) -> dict[str, object]:
    realized_remaining = _pnl_points(position.direction, position.entry_price, exit_price) * position.remaining_size
    gross_pnl_points = position.realized_pnl_points + realized_remaining
    hold_minutes = (pd.Timestamp(bar.timestamp) - position.entry_timestamp).total_seconds() / 60.0
    cost_points = (
        backtest_config.spread_points
        + backtest_config.slippage_points
        + backtest_config.commission_points
    )
    pnl_points = gross_pnl_points - cost_points
    return {
        "trade_id": trade_id,
        "parameter_set": parameter_set_id,
        "symbol": bar.symbol,
        "entry_timestamp": position.entry_timestamp,
        "exit_timestamp": pd.Timestamp(bar.timestamp),
        "session_name": getattr(bar, "session_name", None),
        "kill_zone_name": getattr(bar, "kill_zone_name", None),
        "alert_priority": getattr(bar, "alert_priority", None),
        "bar_timeframe": getattr(bar, "bar_timeframe", None),
        "opening_window_variant": getattr(bar, "opening_window_variant", None),
        "direction": position.direction,
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "stop_price": position.stop_price,
        "partial_target_price": position.partial_target_price,
        "final_target_price": position.final_target_price,
        "exit_reason": exit_reason,
        "risk_points": position.risk_points,
        "partial_taken": position.partial_taken,
        "break_even_protected": position.break_even_protected,
        "hold_minutes": hold_minutes,
        "pnl_points": pnl_points,
        "r_multiple": pnl_points / position.risk_points if position.risk_points > 0 else 0.0,
    }


def _pnl_points(direction: Direction, entry_price: float, exit_price: float) -> float:
    if direction == "long":
        return exit_price - entry_price
    return entry_price - exit_price


def _record_transition(
    transitions: list[dict[str, object]],
    previous_state: ReplayState,
    new_state: ReplayState,
    reason: str,
    bar,
    sequence: int,
) -> tuple[ReplayState, int]:
    sequence += 1
    transitions.append(
        {
            "sequence": sequence,
            "symbol": bar.symbol,
            "timestamp": pd.Timestamp(bar.timestamp),
            "previous_state": previous_state,
            "new_state": new_state,
            "reason": reason,
            "close": float(bar.close),
            "vwap_session": float(bar.vwap_session),
            "kill_zone_name": getattr(bar, "kill_zone_name", None),
            "alert_priority": getattr(bar, "alert_priority", None),
            "bar_timeframe": getattr(bar, "bar_timeframe", None),
            "opening_window_variant": getattr(bar, "opening_window_variant", None),
        }
    )
    return new_state, sequence
