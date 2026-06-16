from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.metrics import summarize_trade_log
from parabolic_exhaustion.backtest.vectorized import annotate_intraday_context, session_cutoff_timestamp
from parabolic_exhaustion.config import BacktestConfig, StrategyConfig
from parabolic_exhaustion.execution.state_machine import ReplayState
from parabolic_exhaustion.features.daily import engineer_daily_features
from parabolic_exhaustion.features.intraday import engineer_intraday_features
from parabolic_exhaustion.reporting.exports import export_dataframe
from parabolic_exhaustion.signals.candidates import scan_daily_candidates


@dataclass
class PositionLot:
    size: float
    entry_price: float
    entry_timestamp: pd.Timestamp
    label: str


@dataclass
class ReplayPosition:
    lots: list[PositionLot] = field(default_factory=list)
    initial_risk_points: float = 0.0
    stop_price: float = 0.0
    partial_target_price: float = 0.0
    final_target_price: float = 0.0
    signal_reference_high: float = 0.0
    partial_taken: bool = False
    break_even_protected: bool = False
    add_count: int = 0
    realized_pnl_points: float = 0.0
    realized_size: float = 0.0
    invalidated: bool = False

    @property
    def open_size(self) -> float:
        return sum(lot.size for lot in self.lots)

    @property
    def weighted_entry_price(self) -> float:
        total_size = self.open_size
        if total_size <= 0:
            return 0.0
        return sum(lot.entry_price * lot.size for lot in self.lots) / total_size


@dataclass
class ReplayResult:
    trade_log: pd.DataFrame
    transition_log: pd.DataFrame
    summary_metrics: pd.DataFrame
    instrument_diagnostics: pd.DataFrame


@dataclass
class PendingExecution:
    execute_index: int
    reference_high: float


def run_event_driven_replay(
    *,
    daily_bars: pd.DataFrame,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    output_dir: str | Path,
    strategy_type: str = "parabolic_exhaustion",
    strategy_context: dict[str, object] | None = None,
) -> ReplayResult:
    if strategy_type == "flow_strategy":
        from parabolic_exhaustion.strategies.flow_strategy.backtest import run_flow_replay

        if strategy_context is None or "parameter_set" not in strategy_context:
            raise ValueError("flow_strategy requires strategy_context['parameter_set'].")
        return run_flow_replay(
            daily_bars=daily_bars,
            intraday_bars_by_timeframe=intraday_bars_by_timeframe,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
            parameter_set=strategy_context["parameter_set"],
            output_dir=output_dir,
        )

    daily_features = engineer_daily_features(daily_bars)
    candidates = scan_daily_candidates(daily_features, strategy_config)
    candidates = candidates.loc[candidates["daily_candidate"]].copy()
    candidates = collapse_overlapping_candidates(
        candidates,
        signal_expiry_sessions=backtest_config.signal_expiry_sessions,
    )

    replay_bars = prepare_replay_bars_from_available(
        intraday_bars_by_timeframe=intraday_bars_by_timeframe,
        strategy_config=strategy_config,
    )
    trade_log, transition_log = replay_candidates(
        candidates=candidates,
        replay_bars=replay_bars,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
    )
    summary_metrics = build_replay_summary(
        trade_log=trade_log,
        transition_log=transition_log,
        candidate_count=len(candidates),
    )
    instrument_diagnostics = build_instrument_diagnostics(
        candidates=candidates,
        trade_log=trade_log,
        transition_log=transition_log,
    )

    result = ReplayResult(
        trade_log=trade_log,
        transition_log=transition_log,
        summary_metrics=summary_metrics,
        instrument_diagnostics=instrument_diagnostics,
    )
    export_replay_artifacts(result, output_dir=output_dir)
    return result


def collapse_overlapping_candidates(
    candidates: pd.DataFrame,
    *,
    signal_expiry_sessions: int,
) -> pd.DataFrame:
    if candidates.empty:
        return candidates

    collapsed_rows: list[pd.Series] = []
    for _, frame in candidates.sort_values(["symbol", "timestamp"]).groupby("symbol"):
        kept: list[pd.Series] = []
        for _, row in frame.iterrows():
            row_time = _candidate_timestamp(row["timestamp"])
            if not kept:
                kept.append(row)
                continue
            last_time = _candidate_timestamp(kept[-1]["timestamp"])
            overlap_end = last_time + pd.Timedelta(days=signal_expiry_sessions - 1)
            if row_time.floor("D") <= overlap_end.floor("D"):
                kept[-1] = row
            else:
                kept.append(row)
        collapsed_rows.extend(kept)
    return pd.DataFrame(collapsed_rows).reset_index(drop=True)


def prepare_replay_bars(
    *,
    intraday_1m: pd.DataFrame,
    intraday_5m: pd.DataFrame,
    strategy_config: StrategyConfig,
) -> pd.DataFrame:
    bars_1m = annotate_intraday_context(engineer_intraday_features(intraday_1m), strategy_config)
    bars_5m = annotate_intraday_context(engineer_intraday_features(intraday_5m), strategy_config)

    bars_1m = bars_1m.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    bars_5m = bars_5m.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    context_5m = bars_5m.loc[
        :,
        [
            "symbol",
            "timestamp",
            "close",
            "vwap_session",
            "trend_state",
            "vwap_reclaim_fail_flag",
            "distance_from_vwap_pct",
        ],
    ].rename(
        columns={
            "timestamp": "context_5m_timestamp",
            "close": "context_5m_close",
            "vwap_session": "context_5m_vwap_session",
            "trend_state": "context_5m_trend_state",
            "vwap_reclaim_fail_flag": "context_5m_vwap_reclaim_fail_flag",
            "distance_from_vwap_pct": "context_5m_distance_from_vwap_pct",
        }
    )
    merged = pd.merge_asof(
        bars_1m,
        context_5m,
        by="symbol",
        left_on="timestamp",
        right_on="context_5m_timestamp",
        direction="backward",
    )
    merged["context_5m_below_vwap"] = (
        merged["context_5m_close"] < merged["context_5m_vwap_session"]
    ).fillna(False)
    merged["trade_date"] = merged["timestamp"].dt.floor("D")
    merged["bar_timeframe"] = "1m"
    merged["context_timeframe"] = "5m"
    return merged


def prepare_replay_bars_from_available(
    *,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
) -> pd.DataFrame:
    if not intraday_bars_by_timeframe:
        raise ValueError("Replay requires at least one intraday timeframe.")

    normalized = {
        timeframe: frame.copy()
        for timeframe, frame in intraday_bars_by_timeframe.items()
        if frame is not None and not frame.empty
    }
    if not normalized:
        raise ValueError("Replay requires at least one non-empty intraday frame.")

    primary_timeframe = _select_primary_timeframe(list(normalized))
    context_timeframe = _select_context_timeframe(list(normalized), primary_timeframe)
    primary_bars = annotate_intraday_context(
        engineer_intraday_features(normalized[primary_timeframe]),
        strategy_config,
    )
    primary_bars = primary_bars.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    if context_timeframe == primary_timeframe:
        primary_bars["context_5m_timestamp"] = primary_bars["timestamp"]
        primary_bars["context_5m_close"] = primary_bars["close"]
        primary_bars["context_5m_vwap_session"] = primary_bars["vwap_session"]
        primary_bars["context_5m_trend_state"] = primary_bars["trend_state"]
        primary_bars["context_5m_vwap_reclaim_fail_flag"] = primary_bars["vwap_reclaim_fail_flag"]
        primary_bars["context_5m_distance_from_vwap_pct"] = primary_bars["distance_from_vwap_pct"]
        primary_bars["context_5m_below_vwap"] = primary_bars["close"] < primary_bars["vwap_session"]
        primary_bars["trade_date"] = primary_bars["timestamp"].dt.floor("D")
        primary_bars["bar_timeframe"] = primary_timeframe
        primary_bars["context_timeframe"] = context_timeframe
        return primary_bars

    context_bars = annotate_intraday_context(
        engineer_intraday_features(normalized[context_timeframe]),
        strategy_config,
    )
    context_bars = context_bars.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    context_frame = context_bars.loc[
        :,
        [
            "symbol",
            "timestamp",
            "close",
            "vwap_session",
            "trend_state",
            "vwap_reclaim_fail_flag",
            "distance_from_vwap_pct",
        ],
    ].rename(
        columns={
            "timestamp": "context_5m_timestamp",
            "close": "context_5m_close",
            "vwap_session": "context_5m_vwap_session",
            "trend_state": "context_5m_trend_state",
            "vwap_reclaim_fail_flag": "context_5m_vwap_reclaim_fail_flag",
            "distance_from_vwap_pct": "context_5m_distance_from_vwap_pct",
        }
    )
    merged = pd.merge_asof(
        primary_bars,
        context_frame,
        by="symbol",
        left_on="timestamp",
        right_on="context_5m_timestamp",
        direction="backward",
    )
    merged["context_5m_below_vwap"] = (
        merged["context_5m_close"] < merged["context_5m_vwap_session"]
    ).fillna(False)
    merged["trade_date"] = merged["timestamp"].dt.floor("D")
    merged["bar_timeframe"] = primary_timeframe
    merged["context_timeframe"] = context_timeframe
    return merged


def replay_candidates(
    *,
    candidates: pd.DataFrame,
    replay_bars: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []

    for candidate in candidates.itertuples(index=False):
        candidate_time = _candidate_timestamp(candidate.timestamp)
        expiry = candidate_time + pd.Timedelta(days=backtest_config.signal_expiry_sessions - 1)
        bars = replay_bars.loc[
            (replay_bars["symbol"] == candidate.symbol)
            & (replay_bars["trade_date"] >= candidate_time.floor("D"))
            & (replay_bars["trade_date"] <= expiry.floor("D"))
            & (replay_bars["session_name"].notna())
        ].copy()
        if bars.empty:
            continue
        candidate_trades, candidate_transitions = replay_candidate_window(
            candidate=candidate,
            bars=bars,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        )
        trades.extend(candidate_trades)
        transitions.extend(candidate_transitions)

    trade_log = pd.DataFrame(trades)
    if not trade_log.empty:
        trade_log = trade_log.sort_values(["symbol", "entry_timestamp"]).reset_index(drop=True)

    transition_log = pd.DataFrame(transitions)
    if not transition_log.empty:
        transition_log = transition_log.sort_values(["symbol", "timestamp", "sequence"]).reset_index(drop=True)
    return trade_log, transition_log


def replay_candidate_window(
    *,
    candidate,
    bars: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    current_state = ReplayState.NO_SETUP
    attempt_count = 0
    pending_entry: PendingExecution | None = None
    pending_add_index: int | None = None
    position: ReplayPosition | None = None
    trades: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    sequence = 0
    entry_trade_id = 0

    for idx, bar in enumerate(bars.itertuples(index=False)):
        bar_time = pd.Timestamp(bar.timestamp)
        if current_state == ReplayState.NO_SETUP:
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.DAILY_CANDIDATE,
                "daily candidate active",
                candidate.symbol,
                candidate.timestamp,
                bar,
                attempt_count,
                sequence,
            )

        if pending_entry is not None and idx == pending_entry.execute_index:
            position = _open_position(
                bar=bar,
                candidate=candidate,
                strategy_config=strategy_config,
                backtest_config=backtest_config,
                label="initial",
                reference_high=pending_entry.reference_high,
            )
            if position is None:
                current_state, sequence = _record_transition(
                    transitions,
                    current_state,
                    ReplayState.INVALIDATED,
                    "entry skipped because stop reference was not above entry",
                    candidate.symbol,
                    candidate.timestamp,
                    bar,
                    attempt_count,
                    sequence,
                )
            else:
                attempt_count += 1
                entry_trade_id += 1
                current_state, sequence = _record_transition(
                    transitions,
                    current_state,
                    ReplayState.ENTRY_TRIGGERED,
                    "entry executed",
                    candidate.symbol,
                    candidate.timestamp,
                    bar,
                    attempt_count,
                    sequence,
                )
            pending_entry = None

        if pending_add_index is not None and idx == pending_add_index and position is not None:
            _add_position_lot(
                position,
                bar=bar,
                size_pct=backtest_config.replay.add_size_pct_of_initial / 100.0,
            )
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.ADD_TRIGGERED,
                "risk-free add executed",
                candidate.symbol,
                candidate.timestamp,
                bar,
                attempt_count,
                sequence,
            )
            pending_add_index = None

        if position is None:
            current_state, sequence, pending_entry = _process_pre_entry_bar(
                candidate=candidate,
                bar=bar,
                bar_index=idx,
                current_state=current_state,
                pending_entry=pending_entry,
                strategy_config=strategy_config,
                backtest_config=backtest_config,
                transitions=transitions,
                attempt_count=attempt_count,
                sequence=sequence,
            )
            continue

        current_state, sequence, pending_add_index, trade = _process_open_position_bar(
            candidate=candidate,
            bar=bar,
            bar_index=idx,
            current_state=current_state,
            position=position,
            pending_add_index=pending_add_index,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
            transitions=transitions,
            attempt_count=attempt_count,
            sequence=sequence,
            trade_id=f"{candidate.symbol}-{pd.Timestamp(candidate.timestamp).strftime('%Y%m%d')}-{entry_trade_id}",
        )
        if trade is not None:
            trades.append(trade)
            position = None
            pending_add_index = None

    return trades, transitions


def build_replay_summary(
    *,
    trade_log: pd.DataFrame,
    transition_log: pd.DataFrame,
    candidate_count: int,
) -> pd.DataFrame:
    summary = summarize_trade_log(
        trade_log,
        candidate_count=candidate_count,
        signal_count=int((transition_log["new_state"] == ReplayState.ENTRY_TRIGGERED).sum()) if not transition_log.empty else 0,
        parameter_set="replay",
    )
    if transition_log.empty:
        summary["transition_count"] = 0
        summary["invalidation_count"] = 0
        summary["partial_count"] = 0
        summary["add_count"] = 0
        summary["forced_exit_count"] = 0
        return summary

    summary["transition_count"] = len(transition_log)
    summary["invalidation_count"] = int((transition_log["new_state"] == ReplayState.INVALIDATED).sum())
    summary["partial_count"] = int((transition_log["new_state"] == ReplayState.PARTIAL_TAKEN).sum())
    summary["add_count"] = int((transition_log["new_state"] == ReplayState.ADD_TRIGGERED).sum())
    summary["forced_exit_count"] = int((trade_log["exit_reason"] == "SESSION_END").sum()) if not trade_log.empty else 0
    return summary


def build_instrument_diagnostics(
    *,
    candidates: pd.DataFrame,
    trade_log: pd.DataFrame,
    transition_log: pd.DataFrame,
) -> pd.DataFrame:
    candidate_counts = candidates.groupby("symbol").size().rename("candidate_count")
    diagnostics = candidate_counts.to_frame()
    if not trade_log.empty:
        trade_stats = trade_log.groupby("symbol").agg(
            replay_trade_count=("trade_id", "count"),
            total_r=("r_multiple", "sum"),
            total_pnl_points=("pnl_points", "sum"),
            average_hold_minutes=("hold_minutes", "mean"),
        )
        diagnostics = diagnostics.join(trade_stats, how="left")
    if not transition_log.empty:
        transition_stats = transition_log.groupby("symbol").agg(
            transition_count=("sequence", "count"),
            invalidation_count=("new_state", lambda s: int((s == ReplayState.INVALIDATED).sum())),
            add_count=("new_state", lambda s: int((s == ReplayState.ADD_TRIGGERED).sum())),
            partial_count=("new_state", lambda s: int((s == ReplayState.PARTIAL_TAKEN).sum())),
        )
        diagnostics = diagnostics.join(transition_stats, how="left")
    diagnostics = diagnostics.fillna(0.0).reset_index()
    return diagnostics


def export_replay_artifacts(result: ReplayResult, *, output_dir: str | Path) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    export_dataframe(result.trade_log, root / "replay_trade_log.csv")
    export_dataframe(result.transition_log, root / "state_transition_log.csv")
    export_dataframe(result.summary_metrics, root / "replay_summary_metrics.csv")
    export_dataframe(result.instrument_diagnostics, root / "per_instrument_diagnostics.csv")


def _process_pre_entry_bar(
    *,
    candidate,
    bar,
    bar_index: int,
    current_state: ReplayState,
    pending_entry: PendingExecution | None,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    transitions: list[dict[str, object]],
    attempt_count: int,
    sequence: int,
) -> tuple[ReplayState, int, PendingExecution | None]:
    if current_state in {ReplayState.DAILY_CANDIDATE, ReplayState.EXITED, ReplayState.INVALIDATED} and _bar_eligible_for_watch(bar, backtest_config):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXHAUSTION_WATCH,
            "eligible intraday watch window",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )

    if current_state == ReplayState.EXHAUSTION_WATCH and _bar_lost_vwap(bar):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.VWAP_LOST,
            "lost VWAP",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )

    if current_state == ReplayState.VWAP_LOST and float(bar.high) >= float(bar.vwap_session):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.VWAP_RETEST_PENDING,
            "VWAP retest in progress",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )

    if current_state in {ReplayState.VWAP_LOST, ReplayState.VWAP_RETEST_PENDING} and _pre_entry_invalidation(bar, backtest_config):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.INVALIDATED,
            "pre-entry invalidation on VWAP reclaim",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        return current_state, sequence, None

    if (
        current_state in {ReplayState.VWAP_LOST, ReplayState.VWAP_RETEST_PENDING}
        and pending_entry is None
        and attempt_count < strategy_config.max_attempts_per_symbol_per_day
        and _entry_trigger(bar, backtest_config)
    ):
        execute_index = bar_index if backtest_config.entry_mode == "bar_close" else bar_index + 1
        pending_entry = PendingExecution(
            execute_index=execute_index,
            reference_high=float(bar.high),
        )
    return current_state, sequence, pending_entry


def _process_open_position_bar(
    *,
    candidate,
    bar,
    bar_index: int,
    current_state: ReplayState,
    position: ReplayPosition,
    pending_add_index: int | None,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    transitions: list[dict[str, object]],
    attempt_count: int,
    sequence: int,
    trade_id: str,
) -> tuple[ReplayState, int, int | None, dict[str, object] | None]:
    if not position.partial_taken and float(bar.low) <= position.partial_target_price:
        _take_partial(position, strategy_config)
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.PARTIAL_TAKEN,
            "partial target reached",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        if strategy_config.risk.move_stop_to_break_even_after_partial:
            position.stop_price = position.lots[0].entry_price
            position.break_even_protected = True
            current_state, sequence = _record_transition(
                transitions,
                current_state,
                ReplayState.BREAK_EVEN_PROTECTED,
                "stop moved to break-even",
                candidate.symbol,
                candidate.timestamp,
                bar,
                attempt_count,
                sequence,
            )

    if _should_queue_add(position, bar, pending_add_index, strategy_config, backtest_config):
        pending_add_index = bar_index if backtest_config.entry_mode == "bar_close" else bar_index + 1

    if _stop_hit(bar, position.stop_price):
        trade = _close_trade(
            trade_id=trade_id,
            candidate=candidate,
            bar=bar,
            position=position,
            exit_price=position.stop_price,
            exit_reason="STOP_HIT",
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        )
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "stop hit",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        return current_state, sequence, None, trade

    if float(bar.low) <= position.final_target_price:
        trade = _close_trade(
            trade_id=trade_id,
            candidate=candidate,
            bar=bar,
            position=position,
            exit_price=position.final_target_price,
            exit_reason="TARGET_HIT",
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        )
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "final target reached",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        return current_state, sequence, None, trade

    if _post_entry_invalidation(bar, backtest_config):
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.INVALIDATED,
            "post-entry invalidation on VWAP reclaim",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        trade = _close_trade(
            trade_id=trade_id,
            candidate=candidate,
            bar=bar,
            position=position,
            exit_price=float(bar.close),
            exit_reason="INVALIDATED",
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        )
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "invalidated position exited",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        return current_state, sequence, None, trade

    cutoff = session_cutoff_timestamp(pd.Timestamp(bar.timestamp), str(bar.session_name), strategy_config, backtest_config)
    if pd.Timestamp(bar.timestamp) >= cutoff:
        trade = _close_trade(
            trade_id=trade_id,
            candidate=candidate,
            bar=bar,
            position=position,
            exit_price=float(bar.close),
            exit_reason="SESSION_END",
            strategy_config=strategy_config,
            backtest_config=backtest_config,
        )
        current_state, sequence = _record_transition(
            transitions,
            current_state,
            ReplayState.EXITED,
            "forced session exit",
            candidate.symbol,
            candidate.timestamp,
            bar,
            attempt_count,
            sequence,
        )
        return current_state, sequence, None, trade

    return current_state, sequence, pending_add_index, None


def _open_position(
    *,
    bar,
    candidate,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    label: str,
    reference_high: float,
) -> ReplayPosition | None:
    entry_price = float(bar.close if backtest_config.entry_mode == "bar_close" else bar.open)
    stop_price = float(reference_high) + backtest_config.stop_buffer_points
    risk_points = stop_price - entry_price
    if risk_points <= 0:
        return None
    partial_target = entry_price - (risk_points * strategy_config.risk.partial_take_r)
    final_target = entry_price - (risk_points * backtest_config.target_r)
    return ReplayPosition(
        lots=[PositionLot(size=1.0, entry_price=entry_price, entry_timestamp=pd.Timestamp(bar.timestamp), label=label)],
        initial_risk_points=risk_points,
        stop_price=stop_price,
        partial_target_price=partial_target,
        final_target_price=final_target,
        signal_reference_high=float(bar.high),
    )


def _add_position_lot(position: ReplayPosition, *, bar, size_pct: float) -> None:
    position.add_count += 1
    position.lots.append(
        PositionLot(
            size=size_pct,
            entry_price=float(bar.close),
            entry_timestamp=pd.Timestamp(bar.timestamp),
            label=f"add_{position.add_count}",
        )
    )


def _take_partial(position: ReplayPosition, strategy_config: StrategyConfig) -> None:
    if position.partial_taken:
        return
    partial_size = strategy_config.risk.partial_take_size_pct / 100.0
    target_reduction = min(partial_size, position.open_size)
    remaining = target_reduction
    updated_lots: list[PositionLot] = []
    for lot in position.lots:
        if remaining <= 0:
            updated_lots.append(lot)
            continue
        reducible = min(lot.size, remaining)
        realized = (lot.entry_price - position.partial_target_price) * reducible
        position.realized_pnl_points += realized
        position.realized_size += reducible
        leftover = lot.size - reducible
        if leftover > 0:
            updated_lots.append(
                PositionLot(
                    size=leftover,
                    entry_price=lot.entry_price,
                    entry_timestamp=lot.entry_timestamp,
                    label=lot.label,
                )
            )
        remaining -= reducible
    position.lots = updated_lots
    position.partial_taken = True


def _close_trade(
    *,
    trade_id: str,
    candidate,
    bar,
    position: ReplayPosition,
    exit_price: float,
    exit_reason: str,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> dict[str, object]:
    realized_remaining = sum((lot.entry_price - exit_price) * lot.size for lot in position.lots)
    gross_pnl_points = position.realized_pnl_points + realized_remaining
    total_size = position.realized_size + position.open_size
    entry_timestamp = min(lot.entry_timestamp for lot in position.lots) if position.lots else pd.Timestamp(bar.timestamp)
    hold_minutes = (pd.Timestamp(bar.timestamp) - entry_timestamp).total_seconds() / 60.0
    cost_points = (
        backtest_config.spread_points
        + backtest_config.slippage_points
        + backtest_config.commission_points
        + (backtest_config.borrow_cost_points_per_day * max(hold_minutes, 0.0) / (24.0 * 60.0))
    )
    pnl_points = gross_pnl_points - cost_points
    return {
        "trade_id": trade_id,
        "symbol": candidate.symbol,
        "candidate_timestamp": candidate.timestamp,
        "entry_timestamp": entry_timestamp,
        "exit_timestamp": pd.Timestamp(bar.timestamp),
        "session_name": getattr(bar, "session_name", None),
        "kill_zone_name": getattr(bar, "kill_zone_name", None),
        "alert_priority": getattr(bar, "alert_priority", None),
        "bar_timeframe": getattr(bar, "bar_timeframe", None),
        "entry_price": position.weighted_entry_price,
        "exit_price": exit_price,
        "stop_price": position.stop_price,
        "partial_target_price": position.partial_target_price,
        "final_target_price": position.final_target_price,
        "exit_reason": exit_reason,
        "risk_points": position.initial_risk_points,
        "size_closed": total_size,
        "add_count": position.add_count,
        "partial_taken": position.partial_taken,
        "break_even_protected": position.break_even_protected,
        "hold_minutes": hold_minutes,
        "pnl_points": pnl_points,
        "r_multiple": pnl_points / position.initial_risk_points if position.initial_risk_points > 0 else 0.0,
    }


def _bar_eligible_for_watch(bar, backtest_config: BacktestConfig) -> bool:
    if backtest_config.replay.use_kill_zones_for_entry:
        return bool(getattr(bar, "kill_zone_active", False))
    return True


def _bar_lost_vwap(bar) -> bool:
    return bool(getattr(bar, "vwap_cross_down_flag", False) or float(bar.close) < float(bar.vwap_session))


def _entry_trigger(bar, backtest_config: BacktestConfig) -> bool:
    if not bool(getattr(bar, "vwap_reclaim_fail_flag", False)):
        return False
    if not bool(getattr(bar, "lower_high_flag", False)):
        return False
    if not bool(getattr(bar, "lower_low_flag", False)):
        return False
    if backtest_config.replay.use_5m_context_filter:
        if getattr(bar, "context_5m_trend_state", None) not in backtest_config.replay.allowed_5m_trend_states:
            return False
        if backtest_config.replay.require_5m_below_vwap_for_entry and not bool(getattr(bar, "context_5m_below_vwap", False)):
            return False
    return True


def _pre_entry_invalidation(bar, backtest_config: BacktestConfig) -> bool:
    return backtest_config.replay.pre_entry_invalidation_on_close_above_vwap and float(bar.close) > float(bar.vwap_session)


def _post_entry_invalidation(bar, backtest_config: BacktestConfig) -> bool:
    return backtest_config.replay.post_entry_invalidation_on_close_above_vwap and float(bar.close) > float(bar.vwap_session)


def _should_queue_add(
    position: ReplayPosition,
    bar,
    pending_add_index: int | None,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> bool:
    if pending_add_index is not None:
        return False
    if not strategy_config.risk.enable_risk_free_add:
        return False
    if not position.break_even_protected:
        return False
    if position.add_count >= backtest_config.replay.max_adds_per_trade:
        return False
    if strategy_config.risk.add_only_after_second_vwap_failure and int(getattr(bar, "retest_count_vwap", 0)) < 2:
        return False
    return bool(getattr(bar, "vwap_reclaim_fail_flag", False))


def _stop_hit(bar, stop_price: float) -> bool:
    return float(bar.high) >= float(stop_price)


def _record_transition(
    transitions: list[dict[str, object]],
    previous_state: ReplayState,
    new_state: ReplayState,
    reason: str,
    symbol: str,
    candidate_timestamp,
    bar,
    attempt_count: int,
    sequence: int,
) -> tuple[ReplayState, int]:
    sequence += 1
    transitions.append(
        {
            "sequence": sequence,
            "symbol": symbol,
            "candidate_timestamp": candidate_timestamp,
            "timestamp": pd.Timestamp(bar.timestamp),
            "attempt": attempt_count,
            "previous_state": previous_state,
            "new_state": new_state,
            "reason": reason,
            "close": float(bar.close),
            "vwap_session": float(bar.vwap_session),
            "session_name": getattr(bar, "session_name", None),
            "kill_zone_name": getattr(bar, "kill_zone_name", None),
            "alert_priority": getattr(bar, "alert_priority", None),
            "bar_timeframe": getattr(bar, "bar_timeframe", None),
            "context_5m_trend_state": getattr(bar, "context_5m_trend_state", None),
        }
    )
    return new_state, sequence


def _candidate_timestamp(value) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _select_primary_timeframe(timeframes: list[str]) -> str:
    return min(timeframes, key=_timeframe_sort_key)


def _select_context_timeframe(timeframes: list[str], primary_timeframe: str) -> str:
    preferred_5m = next(
        (
            timeframe
            for timeframe in timeframes
            if _timeframe_sort_key(timeframe) == 5 and timeframe != primary_timeframe
        ),
        None,
    )
    if preferred_5m is not None:
        return preferred_5m
    return primary_timeframe


def _timeframe_sort_key(label: str) -> int:
    normalized = label.strip().lower()
    if normalized.endswith("m"):
        return int(normalized[:-1])
    if normalized.startswith("m"):
        return int(normalized[1:])
    raise ValueError(f"Unsupported timeframe label: {label}")
