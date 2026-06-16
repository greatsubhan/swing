from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from itertools import product
from pathlib import Path

import pandas as pd

from parabolic_exhaustion.backtest.metrics import summarize_trade_log
from parabolic_exhaustion.config import BacktestConfig, SessionScope, StrategyConfig
from parabolic_exhaustion.features.daily import engineer_daily_features
from parabolic_exhaustion.features.intraday import engineer_intraday_features
from parabolic_exhaustion.reporting.exports import export_dataframe
from parabolic_exhaustion.signals.candidates import scan_daily_candidates


@dataclass(frozen=True)
class ParameterSet:
    name: str
    extension_mode: str
    extension_value: float
    volume_rank_min: float
    slope_score_min: float
    signal_timeframe: str
    target_r: float
    stop_buffer_points: float


@dataclass
class ParameterSetResult:
    parameter_set: ParameterSet
    candidates: pd.DataFrame
    signals: pd.DataFrame
    trades: pd.DataFrame
    summary: pd.DataFrame


@dataclass
class ResearchRunArtifacts:
    parameter_results: list[ParameterSetResult]
    parameter_comparison: pd.DataFrame


def run_vectorized_research(
    *,
    daily_bars: pd.DataFrame,
    intraday_bars_by_timeframe: dict[str, pd.DataFrame],
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    output_dir: str | Path,
    strategy_type: str = "parabolic_exhaustion",
    strategy_context: dict[str, object] | None = None,
) -> ResearchRunArtifacts:
    if strategy_type == "flow_strategy":
        from parabolic_exhaustion.strategies.flow_strategy.backtest import run_flow_vectorized_research

        if strategy_context is None or "parameter_set" not in strategy_context:
            raise ValueError("flow_strategy requires strategy_context['parameter_set'].")
        return run_flow_vectorized_research(
            daily_bars=daily_bars,
            intraday_bars_by_timeframe=intraday_bars_by_timeframe,
            strategy_config=strategy_config,
            backtest_config=backtest_config,
            parameter_set=strategy_context["parameter_set"],
            output_dir=output_dir,
        )

    daily_features = engineer_daily_features(daily_bars)
    intraday_features = {
        timeframe: engineer_intraday_features(frame)
        for timeframe, frame in intraday_bars_by_timeframe.items()
    }

    parameter_results: list[ParameterSetResult] = []
    for parameter_set in build_parameter_sets(backtest_config):
        strategy_variant = _build_strategy_variant(strategy_config, parameter_set)
        candidates = scan_daily_candidates(daily_features, strategy_variant)
        candidates = candidates.loc[candidates["daily_candidate"]].copy()

        timeframe_data = intraday_features[parameter_set.signal_timeframe]
        signals = build_signal_table(
            candidates=candidates,
            intraday_features=timeframe_data,
            strategy_config=strategy_variant,
            backtest_config=backtest_config,
            parameter_set=parameter_set,
        )
        trades = build_trade_log(
            signals=signals,
            intraday_features=timeframe_data,
            strategy_config=strategy_variant,
            backtest_config=backtest_config,
        )
        summary = summarize_trade_log(
            trades,
            candidate_count=len(candidates),
            signal_count=len(signals),
            parameter_set=parameter_set.name,
        )
        result = ParameterSetResult(
            parameter_set=parameter_set,
            candidates=candidates,
            signals=signals,
            trades=trades,
            summary=summary,
        )
        parameter_results.append(result)

    comparison = pd.concat([result.summary for result in parameter_results], ignore_index=True)
    comparison = comparison.sort_values(
        ["total_r", "expectancy_r", "trade_count"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    artifacts = ResearchRunArtifacts(
        parameter_results=parameter_results,
        parameter_comparison=comparison,
    )
    export_research_artifacts(artifacts, output_dir=output_dir)
    return artifacts


def build_parameter_sets(backtest_config: BacktestConfig) -> list[ParameterSet]:
    grid = backtest_config.parameter_grid
    parameter_sets: list[ParameterSet] = []
    for index, values in enumerate(
        product(
            grid.extension_modes,
            grid.extension_values,
            grid.volume_rank_values,
            grid.slope_score_values,
            grid.signal_timeframes,
            grid.target_r_values,
            grid.stop_buffer_points,
        ),
        start=1,
    ):
        extension_mode, extension_value, volume_rank_min, slope_score_min, signal_timeframe, target_r, stop_buffer = values
        name = (
            f"ps{index:03d}_{extension_mode}_{extension_value:g}_"
            f"vr{volume_rank_min:g}_ss{slope_score_min:g}_{signal_timeframe}_tr{target_r:g}_sb{stop_buffer:g}"
        )
        parameter_sets.append(
            ParameterSet(
                name=name,
                extension_mode=extension_mode,
                extension_value=float(extension_value),
                volume_rank_min=float(volume_rank_min),
                slope_score_min=float(slope_score_min),
                signal_timeframe=signal_timeframe,
                target_r=float(target_r),
                stop_buffer_points=float(stop_buffer),
            )
        )
    return parameter_sets


def build_signal_table(
    *,
    candidates: pd.DataFrame,
    intraday_features: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    parameter_set: ParameterSet,
) -> pd.DataFrame:
    if candidates.empty or intraday_features.empty:
        return pd.DataFrame()

    intraday = annotate_intraday_context(intraday_features, strategy_config)
    intraday = intraday.loc[intraday["session_name"].notna()].copy()
    if _kill_zone_filter_enabled(strategy_config):
        intraday = intraday.loc[intraday["kill_zone_active"]].copy()
    intraday["trade_date"] = intraday["timestamp"].dt.floor("D")

    signals: list[dict[str, object]] = []
    for candidate in candidates.itertuples(index=False):
        candidate_date = pd.Timestamp(candidate.timestamp).tz_localize("UTC") if pd.Timestamp(candidate.timestamp).tzinfo is None else pd.Timestamp(candidate.timestamp).tz_convert("UTC")
        expiry_date = candidate_date + pd.Timedelta(days=backtest_config.signal_expiry_sessions - 1)
        window = intraday.loc[
            (intraday["symbol"] == candidate.symbol)
            & (intraday["trade_date"] >= candidate_date.floor("D"))
            & (intraday["trade_date"] <= expiry_date.floor("D"))
        ].copy()
        if window.empty:
            continue

        signal_mask = pd.Series(True, index=window.index)
        if strategy_config.intraday.require_lower_high:
            signal_mask &= window["lower_high_flag"].fillna(False)
        if strategy_config.intraday.require_lower_low:
            signal_mask &= window["lower_low_flag"].fillna(False)
        if strategy_config.intraday.require_vwap_loss:
            signal_mask &= (window["vwap_cross_down_flag"].fillna(False) | (window["close"] < window["vwap_session"]))
        if strategy_config.intraday.require_vwap_reclaim_failure:
            signal_mask &= window["vwap_reclaim_fail_flag"].fillna(False)
        signal_mask &= window["retest_count_vwap"].fillna(0) <= strategy_config.intraday.vwap_retest_max_count

        qualified = window.loc[signal_mask].copy()
        if qualified.empty:
            continue

        qualified["parameter_set"] = parameter_set.name
        qualified["candidate_timestamp"] = candidate.timestamp
        qualified["candidate_score"] = candidate.parabolic_exhaustion_score
        qualified["candidate_reason"] = candidate.candidate_reason
        qualified["signal_stage"] = qualified["vwap_reclaim_fail_flag"].map(
            lambda flag: "VWAP_REJECTION_CONFIRMED" if flag else "VWAP_LOST"
        )
        qualified["signal_timeframe"] = parameter_set.signal_timeframe
        qualified["bar_timeframe"] = parameter_set.signal_timeframe
        signals.extend(qualified.to_dict("records"))

    signal_table = pd.DataFrame(signals)
    if signal_table.empty:
        return signal_table
    signal_table = signal_table.sort_values(
        ["symbol", "timestamp", "candidate_timestamp", "candidate_score"],
        ascending=[True, True, False, False],
    )
    signal_table = signal_table.drop_duplicates(
        subset=["parameter_set", "symbol", "timestamp"],
        keep="first",
    )
    signal_table["signal_rank"] = signal_table.groupby(
        ["parameter_set", "symbol", "candidate_timestamp"]
    )["timestamp"].rank(method="first")
    return signal_table.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def build_trade_log(
    *,
    signals: pd.DataFrame,
    intraday_features: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()

    intraday = annotate_intraday_context(intraday_features, strategy_config)
    intraday = intraday.loc[intraday["session_name"].notna()].copy()

    trades: list[dict[str, object]] = []
    first_signals = signals.loc[signals["signal_rank"] == 1].copy()
    for signal in first_signals.itertuples(index=False):
        symbol_bars = intraday.loc[
            (intraday["symbol"] == signal.symbol)
            & (intraday["session_name"] == signal.session_name)
        ].copy()
        signal_time = pd.Timestamp(signal.timestamp)
        symbol_bars = symbol_bars.loc[symbol_bars["timestamp"] >= signal_time].copy()
        if symbol_bars.empty:
            continue

        signal_position = symbol_bars.index[symbol_bars["timestamp"] == signal_time]
        if len(signal_position) == 0:
            continue
        position = symbol_bars.index.get_loc(signal_position[0])
        entry_position = position + 1 if backtest_config.entry_mode == "next_bar_open" else position
        if entry_position >= len(symbol_bars):
            continue

        entry_bar = symbol_bars.iloc[entry_position]
        entry_time = pd.Timestamp(entry_bar["timestamp"])
        entry_price = float(entry_bar["open"] if backtest_config.entry_mode == "next_bar_open" else signal.close)
        stop_reference = float(signal.high if backtest_config.stop_reference == "signal_bar_high" else signal.high_of_day)
        stop_price = stop_reference + backtest_config.stop_buffer_points
        risk_points = stop_price - entry_price
        if risk_points <= 0:
            continue
        target_price = entry_price - (risk_points * backtest_config.target_r)

        managed = symbol_bars.iloc[entry_position:].copy()
        cutoff = session_cutoff_timestamp(entry_time, str(signal.session_name), strategy_config, backtest_config)
        managed = managed.loc[managed["timestamp"] <= cutoff].copy()
        if managed.empty:
            continue

        exit_time = pd.Timestamp(managed.iloc[-1]["timestamp"])
        exit_price = float(managed.iloc[-1]["close"])
        exit_reason = "SESSION_END"

        for bar in managed.itertuples(index=False):
            stop_hit = float(bar.high) >= stop_price
            target_hit = float(bar.low) <= target_price
            if stop_hit and target_hit:
                exit_reason = "STOP_HIT" if backtest_config.intrabar_priority == "stop_first" else "TARGET_HIT"
                exit_price = stop_price if exit_reason == "STOP_HIT" else target_price
                exit_time = pd.Timestamp(bar.timestamp)
                break
            if stop_hit:
                exit_reason = "STOP_HIT"
                exit_price = stop_price
                exit_time = pd.Timestamp(bar.timestamp)
                break
            if target_hit:
                exit_reason = "TARGET_HIT"
                exit_price = target_price
                exit_time = pd.Timestamp(bar.timestamp)
                break

        hold_minutes = (exit_time - entry_time).total_seconds() / 60.0
        cost_points = (
            backtest_config.spread_points
            + backtest_config.slippage_points
            + backtest_config.commission_points
            + (backtest_config.borrow_cost_points_per_day * max(hold_minutes, 0.0) / (24.0 * 60.0))
        )
        pnl_points = (entry_price - exit_price) - cost_points
        trades.append(
            {
                "parameter_set": signal.parameter_set,
                "symbol": signal.symbol,
                "signal_timestamp": signal.timestamp,
                "entry_timestamp": entry_time,
                "exit_timestamp": exit_time,
                "session_name": signal.session_name,
                "kill_zone_name": signal.kill_zone_name,
                "alert_priority": signal.alert_priority,
                "signal_stage": signal.signal_stage,
                "bar_timeframe": signal.bar_timeframe,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "risk_points": risk_points,
                "pnl_points": pnl_points,
                "r_multiple": pnl_points / risk_points,
                "hold_minutes": hold_minutes,
            }
        )

    return pd.DataFrame(trades).sort_values(["symbol", "entry_timestamp"]).reset_index(drop=True)


def annotate_intraday_context(
    intraday_features: pd.DataFrame,
    strategy_config: StrategyConfig,
) -> pd.DataFrame:
    intraday = intraday_features.copy()
    intraday["timestamp"] = pd.to_datetime(intraday["timestamp"], utc=True)
    intraday["london_session_active"] = _window_active(
        intraday["timestamp"],
        strategy_config.sessions.get("london"),
    )
    intraday["new_york_session_active"] = _window_active(
        intraday["timestamp"],
        strategy_config.sessions.get("new_york"),
    )
    intraday["session_overlap"] = (
        intraday["london_session_active"] & intraday["new_york_session_active"]
    )
    intraday["session_name"] = determine_session_name(intraday, strategy_config)
    intraday["london_kill_zone_active"] = _kill_zone_active(
        intraday["timestamp"],
        strategy_config,
        zone_name="london",
    )
    intraday["new_york_kill_zone_active"] = _kill_zone_active(
        intraday["timestamp"],
        strategy_config,
        zone_name="new_york",
    )
    intraday["kill_zone_active"] = (
        intraday["london_kill_zone_active"] | intraday["new_york_kill_zone_active"]
    )
    intraday["kill_zone_overlap"] = _kill_zone_active(
        intraday["timestamp"],
        strategy_config,
        zone_name="overlap",
    )
    intraday["kill_zone_name"] = intraday.apply(_resolve_kill_zone_name, axis=1)
    intraday["alert_priority"] = intraday["kill_zone_overlap"].map(
        lambda overlap: (
            strategy_config.kill_zones.overlap_alert_priority
            if overlap and strategy_config.kill_zones.prioritize_overlap
            else strategy_config.kill_zones.default_alert_priority
        )
    )
    return intraday


def determine_session_name(intraday: pd.DataFrame | pd.Series, strategy_config: StrategyConfig) -> pd.Series:
    if strategy_config.session_scope == "full_24h":
        series = intraday["timestamp"] if isinstance(intraday, pd.DataFrame) else intraday
        return pd.Series(["full_24h"] * len(series), index=series.index, dtype="object")

    if isinstance(intraday, pd.Series):
        series = pd.to_datetime(intraday, utc=True)
        london_active = _window_active(series, strategy_config.sessions.get("london"))
        new_york_active = _window_active(series, strategy_config.sessions.get("new_york"))
    else:
        series = intraday["timestamp"]
        london_active = intraday["london_session_active"]
        new_york_active = intraday["new_york_session_active"]

    names = pd.Series([None] * len(series), index=series.index, dtype="object")
    if strategy_config.session_scope in {"london", "london_new_york"}:
        names.loc[london_active] = "london"
    if strategy_config.session_scope in {"new_york", "london_new_york"}:
        names.loc[new_york_active & names.isna()] = "new_york"
    return names


def session_cutoff_timestamp(
    entry_time: pd.Timestamp,
    session_name: str,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
) -> pd.Timestamp:
    if session_name == "full_24h":
        return entry_time.floor("D") + pd.Timedelta(days=1) - pd.Timedelta(minutes=backtest_config.force_exit_minutes_before_close)

    session = strategy_config.sessions[session_name]
    localized = entry_time.tz_convert(session.timezone)
    end = _parse_time(session.end_time)
    cutoff_local = localized.normalize() + pd.Timedelta(hours=end.hour, minutes=end.minute)
    cutoff_local = cutoff_local - pd.Timedelta(minutes=backtest_config.force_exit_minutes_before_close)
    return cutoff_local.tz_convert("UTC")


def export_research_artifacts(artifacts: ResearchRunArtifacts, output_dir: str | Path) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    export_dataframe(artifacts.parameter_comparison, root / "parameter_comparison.csv")

    for result in artifacts.parameter_results:
        parameter_dir = root / result.parameter_set.name
        export_dataframe(result.candidates, parameter_dir / "candidate_list.csv")
        export_dataframe(result.signals, parameter_dir / "signal_table.csv")
        export_dataframe(result.trades, parameter_dir / "trade_log.csv")
        export_dataframe(result.summary, parameter_dir / "summary_metrics.csv")


def _build_strategy_variant(strategy_config: StrategyConfig, parameter_set: ParameterSet) -> StrategyConfig:
    variant = strategy_config.model_copy(deep=True)
    variant.signal_timeframe = parameter_set.signal_timeframe
    variant.filters.extension.mode = parameter_set.extension_mode
    variant.filters.extension.min_value = parameter_set.extension_value
    variant.filters.volume_rank_min = parameter_set.volume_rank_min
    variant.filters.min_parabolic_slope_score = parameter_set.slope_score_min
    return variant


def _active_session_names(session_scope: SessionScope) -> list[str]:
    if session_scope == "london":
        return ["london"]
    if session_scope == "new_york":
        return ["new_york"]
    return ["london", "new_york"]


def _parse_time(value: str) -> time:
    hour_text, minute_text = value.split(":")
    return time(hour=int(hour_text), minute=int(minute_text))


def _window_active(
    timestamps: pd.Series,
    session,
) -> pd.Series:
    if session is None:
        return pd.Series(False, index=timestamps.index)
    localized = pd.to_datetime(timestamps, utc=True).dt.tz_convert(session.timezone)
    local_time = localized.dt.time
    start = _parse_time(session.start_time)
    end = _parse_time(session.end_time)
    return local_time.map(lambda value: start <= value <= end)


def _kill_zone_active(
    timestamps: pd.Series,
    strategy_config: StrategyConfig,
    *,
    zone_name: str,
) -> pd.Series:
    zone = getattr(strategy_config.kill_zones, zone_name)
    if not zone.enabled:
        return pd.Series(False, index=timestamps.index)
    localized = pd.to_datetime(timestamps, utc=True).dt.tz_convert(strategy_config.kill_zones.timezone)
    local_time = localized.dt.time
    start = _parse_time(zone.start_time)
    end = _parse_time(zone.end_time)
    return local_time.map(lambda value: start <= value <= end)


def _kill_zone_filter_enabled(strategy_config: StrategyConfig) -> bool:
    return strategy_config.kill_zones.london.enabled or strategy_config.kill_zones.new_york.enabled


def _resolve_kill_zone_name(row: pd.Series) -> str | None:
    active_names: list[str] = []
    if bool(row.get("london_kill_zone_active", False)):
        active_names.append("london_kill_zone")
    if bool(row.get("new_york_kill_zone_active", False)):
        active_names.append("new_york_kill_zone")
    if bool(row.get("kill_zone_overlap", False)):
        active_names.append("london_new_york_overlap")
    if not active_names:
        return None
    return "+".join(active_names)
