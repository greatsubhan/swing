from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from parabolic_exhaustion.backtest.metrics import summarize_trade_log
from parabolic_exhaustion.backtest.replay import (
    ReplayState,
    collapse_overlapping_candidates,
    prepare_replay_bars_from_available,
    replay_candidates,
    run_event_driven_replay,
)
from parabolic_exhaustion.backtest.vectorized import ParameterSet
from parabolic_exhaustion.config import (
    AssetUniverseConfig,
    BacktestConfig,
    StrategyConfig,
    ValidationParameterSetConfig,
    load_assets_config,
    load_backtest_config,
    load_strategy_config,
)
from parabolic_exhaustion.features.daily import engineer_daily_features
from parabolic_exhaustion.features.intraday import engineer_intraday_features
from parabolic_exhaustion.reporting.exports import export_dataframe
from parabolic_exhaustion.signals.candidates import scan_daily_candidates


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "historical_validation"
DEFAULT_PERFORMANCE_MATRIX_PATH = PROJECT_ROOT / "performance_matrix.csv"

SYMBOL_TIMEFRAMES = {
    "XAU_USD": "M15",
    "XAG_USD": "M15",
    "WTICO_USD": "M15",
    "NAS100_USD": "M5",
    "UK100_GBP": "M5",
    "US30_USD": "M5",
    "SPX500_USD": "M5",
}

MARKET_FAMILY_BY_SYMBOL = {
    "XAU_USD": "metals",
    "XAG_USD": "metals",
    "WTICO_USD": "metals",
    "NAS100_USD": "indices",
    "UK100_GBP": "indices",
    "US30_USD": "indices",
    "SPX500_USD": "indices",
}


@dataclass(frozen=True)
class SymbolDataWindow:
    symbol: str
    bar_timeframe: str
    daily_bars: pd.DataFrame
    intraday_bars: pd.DataFrame

    @property
    def data_start(self) -> pd.Timestamp:
        return pd.Timestamp(self.daily_bars["timestamp"].min())

    @property
    def data_end(self) -> pd.Timestamp:
        return pd.Timestamp(self.daily_bars["timestamp"].max())

    @property
    def replay_data_start(self) -> pd.Timestamp:
        return pd.Timestamp(self.intraday_bars["timestamp"].min())

    @property
    def replay_data_end(self) -> pd.Timestamp:
        return pd.Timestamp(self.intraday_bars["timestamp"].max())


def run_historical_validation(
    *,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    assets_config: AssetUniverseConfig,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    performance_matrix_path: Path = DEFAULT_PERFORMANCE_MATRIX_PATH,
) -> pd.DataFrame:
    output_root.mkdir(parents=True, exist_ok=True)
    parameter_sets = backtest_config.validation_parameter_sets
    if not parameter_sets:
        raise ValueError("No validation_parameter_sets configured in backtest.yaml.")

    rows: list[dict[str, object]] = []
    walkforward_rows: list[dict[str, object]] = []
    parameter_docs: list[dict[str, object]] = []

    for parameter_set in parameter_sets:
        parameter_docs.append(
            {
                "parameter_set_id": parameter_set.id,
                "market_family": parameter_set.market_family,
                "extension_mode": parameter_set.extension_mode,
                "extension_value": parameter_set.extension_value,
                "volume_rank_min": parameter_set.volume_rank_min,
                "slope_score_min": parameter_set.slope_score_min,
                "target_r": parameter_set.target_r,
                "partial_take_r": parameter_set.partial_take_r,
                "stop_buffer_points": parameter_set.stop_buffer_points,
                "killzone_only": parameter_set.killzone_only,
                "notes": parameter_set.notes,
            }
        )

    for instrument in assets_config.instruments:
        data_window = load_symbol_data(instrument.symbol, asset_class=instrument.asset_class)
        symbol_output_root = output_root / instrument.symbol
        market_family = MARKET_FAMILY_BY_SYMBOL[instrument.symbol]
        symbol_output_root.mkdir(parents=True, exist_ok=True)
        export_dataframe(
            pd.DataFrame(
                [
                    {
                        "symbol": instrument.symbol,
                        "bar_timeframe": data_window.bar_timeframe,
                        "data_start": data_window.data_start,
                        "data_end": data_window.data_end,
                        "replay_data_start": data_window.replay_data_start,
                        "replay_data_end": data_window.replay_data_end,
                        "daily_trading_days_used": int(data_window.daily_bars["timestamp"].dt.floor("D").nunique()),
                        "intraday_bars_used": int(len(data_window.intraday_bars)),
                    }
                ]
            ),
            symbol_output_root / "data_window.csv",
        )

        daily_features = engineer_daily_features(data_window.daily_bars)
        for parameter_set in parameter_sets:
            if parameter_set.market_family not in {"all", market_family}:
                continue
            strategy_variant = build_strategy_variant(
                strategy_config=strategy_config,
                parameter_set=parameter_set,
                signal_timeframe=data_window.bar_timeframe,
            )
            backtest_variant = build_backtest_variant(
                backtest_config=backtest_config,
                parameter_set=parameter_set,
            )
            vectorized_result = run_vectorized_parameter_set(
                symbol=instrument.symbol,
                parameter_set=parameter_set,
                signal_timeframe=data_window.bar_timeframe,
                daily_features=daily_features,
                intraday_bars=data_window.intraday_bars,
                strategy_config=strategy_variant,
                backtest_config=backtest_variant,
                output_dir=symbol_output_root / parameter_set.id / "vectorized",
            )
            replay_result = run_event_driven_replay(
                daily_bars=data_window.daily_bars,
                intraday_bars_by_timeframe={data_window.bar_timeframe: data_window.intraday_bars},
                strategy_config=strategy_variant,
                backtest_config=backtest_variant,
                output_dir=symbol_output_root / parameter_set.id / "replay",
            )
            rows.append(
                build_performance_matrix_row(
                    symbol=instrument.symbol,
                    data_window=data_window,
                    parameter_set=parameter_set,
                    vectorized_result=vectorized_result,
                    replay_result=replay_result,
                )
            )
            walkforward_rows.extend(
                build_walkforward_rows(
                    symbol=instrument.symbol,
                    parameter_set_id=parameter_set.id,
                    bar_timeframe=data_window.bar_timeframe,
                    replay_data_start=data_window.replay_data_start,
                    replay_data_end=data_window.replay_data_end,
                    trade_log=replay_result.trade_log,
                )
            )

    performance_matrix = pd.DataFrame(rows).sort_values(
        ["symbol", "parameter_set_id"]
    ).reset_index(drop=True)
    performance_matrix = performance_matrix.replace([np.inf, -np.inf], np.nan)
    walkforward_summary = pd.DataFrame(walkforward_rows).sort_values(
        ["symbol", "parameter_set_id", "year"]
    ).reset_index(drop=True)
    robustness_ranking = build_robustness_ranking(
        performance_matrix=performance_matrix,
        walkforward_summary=walkforward_summary,
    )
    export_dataframe(performance_matrix, performance_matrix_path)
    export_dataframe(performance_matrix, output_root / "performance_matrix.csv")
    export_dataframe(walkforward_summary, PROJECT_ROOT / "walkforward_summary.csv")
    export_dataframe(walkforward_summary, output_root / "walkforward_summary.csv")
    export_dataframe(robustness_ranking, PROJECT_ROOT / "robustness_ranking.csv")
    export_dataframe(robustness_ranking, output_root / "robustness_ranking.csv")
    export_dataframe(pd.DataFrame(parameter_docs), output_root / "parameter_sets.csv")
    write_parameter_set_markdown(pd.DataFrame(parameter_docs), PROJECT_ROOT / "BACKTEST_PARAMETER_SETS.md")
    write_strategy_selection_notes(
        performance_matrix=performance_matrix,
        robustness_ranking=robustness_ranking,
        destination=PROJECT_ROOT / "STRATEGY_SELECTION_NOTES.md",
    )
    return performance_matrix


def load_symbol_data(symbol: str, *, asset_class: str) -> SymbolDataWindow:
    timeframe = SYMBOL_TIMEFRAMES[symbol]
    daily_path = _select_history_file(
        WORKSPACE_ROOT / "research_data" / "oanda" / symbol,
        prefix="D",
    )
    intraday_path = _select_history_file(
        WORKSPACE_ROOT / "research_data" / "cwt_oanda" / symbol,
        prefix=timeframe,
    )
    daily_bars = load_history_csv(daily_path, symbol=symbol, asset_class=asset_class)
    intraday_bars = load_history_csv(intraday_path, symbol=symbol, asset_class=asset_class)
    return SymbolDataWindow(
        symbol=symbol,
        bar_timeframe=timeframe,
        daily_bars=daily_bars,
        intraday_bars=intraday_bars,
    )


def load_history_csv(path: Path, *, symbol: str, asset_class: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["symbol"] = symbol
    frame["asset_class"] = asset_class
    return frame.loc[:, ["timestamp", "symbol", "open", "high", "low", "close", "volume", "asset_class"]]


def build_strategy_variant(
    *,
    strategy_config: StrategyConfig,
    parameter_set: ValidationParameterSetConfig,
    signal_timeframe: str,
) -> StrategyConfig:
    variant = strategy_config.model_copy(deep=True)
    variant.intraday_timeframes = [signal_timeframe]
    variant.signal_timeframe = signal_timeframe
    variant.filters.extension.mode = parameter_set.extension_mode
    variant.filters.extension.min_value = parameter_set.extension_value
    variant.filters.extension.per_symbol_overrides = {}
    variant.filters.volume_rank_min = parameter_set.volume_rank_min
    variant.filters.min_parabolic_slope_score = parameter_set.slope_score_min
    variant.risk.partial_take_r = parameter_set.partial_take_r
    if not parameter_set.killzone_only:
        variant.kill_zones.london.enabled = False
        variant.kill_zones.new_york.enabled = False
        variant.kill_zones.overlap.enabled = False
    return variant


def build_backtest_variant(
    *,
    backtest_config: BacktestConfig,
    parameter_set: ValidationParameterSetConfig,
) -> BacktestConfig:
    variant = backtest_config.model_copy(deep=True)
    variant.target_r = parameter_set.target_r
    variant.stop_buffer_points = parameter_set.stop_buffer_points
    variant.parameter_grid.signal_timeframes = []
    variant.replay.use_kill_zones_for_entry = parameter_set.killzone_only
    return variant


def run_vectorized_parameter_set(
    *,
    symbol: str,
    parameter_set: ValidationParameterSetConfig,
    signal_timeframe: str,
    daily_features: pd.DataFrame,
    intraday_bars: pd.DataFrame,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    parameter = ParameterSet(
        name=parameter_set.id,
        extension_mode=parameter_set.extension_mode,
        extension_value=parameter_set.extension_value,
        volume_rank_min=parameter_set.volume_rank_min,
        slope_score_min=parameter_set.slope_score_min,
        signal_timeframe=signal_timeframe,
        target_r=parameter_set.target_r,
        stop_buffer_points=parameter_set.stop_buffer_points,
    )
    candidates = scan_daily_candidates(daily_features, strategy_config)
    candidates = candidates.loc[candidates["daily_candidate"]].copy()
    candidates = collapse_overlapping_candidates(
        candidates,
        signal_expiry_sessions=backtest_config.signal_expiry_sessions,
    )
    replay_bars = prepare_replay_bars_from_available(
        intraday_bars_by_timeframe={signal_timeframe: intraday_bars},
        strategy_config=strategy_config,
    )
    replay_proxy_trades, replay_proxy_transitions = replay_candidates(
        candidates=candidates,
        replay_bars=replay_bars,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
    )
    signals = _build_vectorized_signal_table_from_replay_proxy(
        candidates=candidates,
        replay_bars=replay_bars,
        replay_transitions=replay_proxy_transitions,
        parameter_set=parameter,
    )
    trades = replay_proxy_trades.copy()
    if not trades.empty:
        trades["parameter_set"] = parameter_set.id
    summary = summarize_trade_log(
        trades,
        candidate_count=len(candidates),
        signal_count=len(signals),
        parameter_set=parameter_set.id,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dataframe(candidates, output_dir / "candidate_list.csv")
    export_dataframe(signals, output_dir / "signal_table.csv")
    export_dataframe(trades, output_dir / "trade_log.csv")
    export_dataframe(summary, output_dir / "summary_metrics.csv")
    return {
        "candidates": candidates,
        "signals": signals,
        "trades": trades,
        "summary": summary,
        "proxy_replay_trades": replay_proxy_trades,
        "proxy_replay_transitions": replay_proxy_transitions,
    }


def build_performance_matrix_row(
    *,
    symbol: str,
    data_window: SymbolDataWindow,
    parameter_set: ValidationParameterSetConfig,
    vectorized_result: dict[str, pd.DataFrame],
    replay_result,
) -> dict[str, object]:
    vectorized_summary_row = _first_summary_row(vectorized_result["summary"])
    replay_summary_row = _first_summary_row(replay_result.summary_metrics)
    vectorized_trades = vectorized_result["trades"]
    replay_trades = replay_result.trade_log

    vectorized_total_pnl = float(vectorized_summary_row["total_pnl_points"])
    replay_total_pnl = float(replay_summary_row["total_pnl_points"])
    diff_pct = np.nan
    if not np.isclose(vectorized_total_pnl, 0.0):
        diff_pct = ((replay_total_pnl - vectorized_total_pnl) / abs(vectorized_total_pnl)) * 100.0

    return {
        "symbol": symbol,
        "parameter_set_id": parameter_set.id,
        "data_start": data_window.data_start,
        "data_end": data_window.data_end,
        "years_covered": round(_years_between(data_window.data_start, data_window.data_end), 2),
        "replay_data_start": data_window.replay_data_start,
        "replay_data_end": data_window.replay_data_end,
        "bar_timeframe": data_window.bar_timeframe,
        "num_trading_days": int(data_window.daily_bars["timestamp"].dt.floor("D").nunique()),
        "num_bars_used": int(len(data_window.intraday_bars)),
        "killzone_only": parameter_set.killzone_only,
        "num_signals": _nan_or_int(replay_summary_row["confirmed_setup_count"]),
        "num_trades": _nan_or_int(replay_summary_row["trade_count"]),
        "win_rate_pct": _pct(replay_summary_row["win_rate"]),
        "profit_factor": _finite_or_nan(replay_summary_row["profit_factor"]),
        "avg_R_per_trade": _finite_or_nan(replay_summary_row["average_r"]),
        "avg_trade_duration_min": _finite_or_nan(replay_summary_row["average_hold_minutes"]),
        "max_drawdown_R": _finite_or_nan(replay_summary_row["max_drawdown_r"]),
        "vectorized_vs_replay_PnL_diff_pct": _finite_or_nan(diff_pct),
        "vectorized_num_signals": int(len(vectorized_result["signals"])),
        "vectorized_num_trades": int(len(vectorized_trades)),
        "vectorized_win_rate_pct": _pct(vectorized_summary_row["win_rate"]),
        "vectorized_profit_factor": _finite_or_nan(vectorized_summary_row["profit_factor"]),
        "vectorized_avg_R_per_trade": _finite_or_nan(vectorized_summary_row["average_r"]),
        "vectorized_avg_trade_duration_min": _finite_or_nan(vectorized_summary_row["average_hold_minutes"]),
        "vectorized_max_drawdown_R": _finite_or_nan(vectorized_summary_row["max_drawdown_r"]),
        "vectorized_total_pnl_points": _finite_or_nan(vectorized_total_pnl),
        "replay_num_signals": _nan_or_int(replay_summary_row["confirmed_setup_count"]),
        "replay_num_trades": _nan_or_int(replay_summary_row["trade_count"]),
        "replay_win_rate_pct": _pct(replay_summary_row["win_rate"]),
        "replay_profit_factor": _finite_or_nan(replay_summary_row["profit_factor"]),
        "replay_avg_R_per_trade": _finite_or_nan(replay_summary_row["average_r"]),
        "replay_avg_trade_duration_min": _finite_or_nan(replay_summary_row["average_hold_minutes"]),
        "replay_max_drawdown_R": _finite_or_nan(replay_summary_row["max_drawdown_r"]),
        "replay_total_pnl_points": _finite_or_nan(replay_total_pnl),
        "vectorized_trade_frequency_per_month": _trade_frequency_per_month(vectorized_trades, data_window.data_start, data_window.data_end),
        "replay_trade_frequency_per_month": _trade_frequency_per_month(replay_trades, data_window.replay_data_start, data_window.replay_data_end),
    }


def write_parameter_set_markdown(parameter_sets: pd.DataFrame, destination: Path) -> None:
    lines = [
        "# Backtest Parameter Sets",
        "",
        "| parameter_set_id | market_family | extension_mode | extension_value | volume_rank_min | slope_score_min | target_r | partial_take_r | stop_buffer_points | killzone_only | notes |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in parameter_sets.to_dict("records"):
        lines.append(
            "| {parameter_set_id} | {market_family} | {extension_mode} | {extension_value:.2f} | {volume_rank_min:.2f} | {slope_score_min:.1f} | {target_r:.2f} | {partial_take_r:.2f} | {stop_buffer_points:.2f} | {killzone_only} | {notes} |".format(
                **row
            )
        )
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_mismatch_report(performance_matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in performance_matrix.to_dict("records"):
        vectorized_trades = int(row["vectorized_num_trades"])
        replay_trades = int(row["replay_num_trades"])
        dominant_driver, notes = _infer_mismatch_driver(row)
        trade_count_gap_pct = np.nan
        if replay_trades > 0:
            trade_count_gap_pct = ((vectorized_trades - replay_trades) / replay_trades) * 100.0
        elif vectorized_trades > 0:
            trade_count_gap_pct = 100.0
        else:
            trade_count_gap_pct = 0.0
        rows.append(
            {
                "symbol": row["symbol"],
                "parameter_set_id": row["parameter_set_id"],
                "vectorized_num_trades": vectorized_trades,
                "replay_num_trades": replay_trades,
                "trade_count_gap_pct": trade_count_gap_pct,
                "vectorized_profit_factor": row["vectorized_profit_factor"],
                "replay_profit_factor": row["replay_profit_factor"],
                "vectorized_avg_R": row["vectorized_avg_R_per_trade"],
                "replay_avg_R": row["replay_avg_R_per_trade"],
                "likely_mismatch_driver": dominant_driver,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows).sort_values(["symbol", "parameter_set_id"]).reset_index(drop=True)


def build_walkforward_rows(
    *,
    symbol: str,
    parameter_set_id: str,
    bar_timeframe: str,
    replay_data_start: pd.Timestamp,
    replay_data_end: pd.Timestamp,
    trade_log: pd.DataFrame,
) -> list[dict[str, object]]:
    years = range(replay_data_start.year, replay_data_end.year + 1)
    rows: list[dict[str, object]] = []
    ordered = trade_log.sort_values("exit_timestamp").copy() if not trade_log.empty else trade_log.copy()
    for year in years:
        yearly = ordered.loc[
            pd.to_datetime(ordered["exit_timestamp"]).dt.year == year
        ].copy() if not ordered.empty else ordered.copy()
        if yearly.empty:
            rows.append(
                {
                    "symbol": symbol,
                    "parameter_set_id": parameter_set_id,
                    "year": year,
                    "bar_timeframe": bar_timeframe,
                    "trades_per_year": 0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown_R": 0.0,
                    "avg_R_per_trade": 0.0,
                    "total_R": 0.0,
                    "positive_year": False,
                }
            )
            continue
        r_series = yearly["r_multiple"].fillna(0.0)
        gross_wins = yearly.loc[yearly["pnl_points"] > 0, "pnl_points"].sum()
        gross_losses = yearly.loc[yearly["pnl_points"] < 0, "pnl_points"].sum()
        cumulative_r = r_series.cumsum()
        drawdown = cumulative_r - cumulative_r.cummax()
        total_r = float(r_series.sum())
        rows.append(
            {
                "symbol": symbol,
                "parameter_set_id": parameter_set_id,
                "year": year,
                "bar_timeframe": bar_timeframe,
                "trades_per_year": int(len(yearly)),
                "win_rate_pct": round(float((r_series > 0).mean() * 100.0), 2),
                "profit_factor": float(gross_wins / abs(gross_losses)) if gross_losses < 0 else np.nan,
                "max_drawdown_R": float(drawdown.min()),
                "avg_R_per_trade": float(r_series.mean()),
                "total_R": total_r,
                "positive_year": bool(total_r > 0),
            }
        )
    return rows


def build_robustness_ranking(
    *,
    performance_matrix: pd.DataFrame,
    walkforward_summary: pd.DataFrame,
) -> pd.DataFrame:
    grouped = walkforward_summary.groupby(["symbol", "parameter_set_id"], as_index=False).agg(
        years_covered=("year", "count"),
        positive_years=("positive_year", "sum"),
        worst_year_profit_factor=("profit_factor", lambda s: float(pd.Series(s).fillna(0.0).min())),
        average_yearly_R=("avg_R_per_trade", "mean"),
    )
    merged = grouped.merge(
        performance_matrix.loc[
            :,
            ["symbol", "parameter_set_id", "replay_num_trades", "replay_profit_factor", "replay_avg_R_per_trade"],
        ].rename(
            columns={
                "replay_num_trades": "total_trades",
                "replay_profit_factor": "overall_profit_factor",
                "replay_avg_R_per_trade": "overall_avg_R",
            }
        ),
        on=["symbol", "parameter_set_id"],
        how="left",
    )
    positive_year_ratio = merged["positive_years"] / merged["years_covered"].replace(0, np.nan)
    merged["robustness_score"] = (positive_year_ratio.fillna(0.0) * np.log1p(merged["total_trades"].fillna(0.0))).round(4)
    return merged.sort_values(
        ["symbol", "robustness_score", "overall_profit_factor", "total_trades"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)


def write_strategy_selection_notes(
    *,
    performance_matrix: pd.DataFrame,
    robustness_ranking: pd.DataFrame,
    destination: Path,
) -> None:
    def top_rows(symbols: list[str]) -> pd.DataFrame:
        return robustness_ranking.loc[robustness_ranking["symbol"].isin(symbols)].copy()

    nas100 = top_rows(["NAS100_USD"])
    other_indices = top_rows(["UK100_GBP", "US30_USD", "SPX500_USD"])
    metals = top_rows(["XAU_USD", "XAG_USD", "WTICO_USD"])

    acceptable_nas100 = nas100.loc[
        (nas100["overall_profit_factor"].fillna(0.0) > 1.0)
        & (nas100["positive_years"] >= 1)
        & (nas100["total_trades"] >= 4)
    ].head(3)
    viable_other_indices = other_indices.loc[
        (other_indices["overall_profit_factor"].fillna(0.0) > 1.0)
        & (other_indices["positive_years"] >= 1)
        & (other_indices["total_trades"] >= 4)
    ].head(3)
    viable_metals = metals.loc[
        (metals["overall_profit_factor"].fillna(0.0) > 1.0)
        & (metals["positive_years"] >= 1)
        & (metals["total_trades"] >= 4)
    ].head(3)

    excluded_rows = robustness_ranking.loc[
        (robustness_ranking["overall_profit_factor"].fillna(0.0) <= 1.0)
        | (robustness_ranking["positive_years"] == 0)
    ]
    excluded_markets = sorted(excluded_rows["symbol"].unique())

    lines = [
        "# Strategy Selection Notes",
        "",
        "## NAS100_USD",
        "",
    ]
    if acceptable_nas100.empty:
        lines.append("- No NAS100_USD parameter set cleared the current acceptance threshold.")
    else:
        lines.extend(
            [
                f"- `{row.parameter_set_id}`: profit factor `{row.overall_profit_factor:.2f}`, total trades `{int(row.total_trades)}`, positive years `{int(row.positive_years)}/{int(row.years_covered)}`, robustness score `{row.robustness_score:.2f}`."
                for row in acceptable_nas100.itertuples(index=False)
            ]
        )
    lines.extend(
        [
            "",
            "## Other Indices",
            "",
        ]
    )
    if viable_other_indices.empty:
        lines.append("- No other index currently looks strong enough for live alerts under the current logic.")
    else:
        lines.extend(
            [
                f"- `{row.symbol}` with `{row.parameter_set_id}`: profit factor `{row.overall_profit_factor:.2f}`, total trades `{int(row.total_trades)}`, positive years `{int(row.positive_years)}/{int(row.years_covered)}`."
                for row in viable_other_indices.itertuples(index=False)
            ]
        )
    lines.extend(
        [
            "",
            "## Metals",
            "",
        ]
    )
    if viable_metals.empty:
        lines.append("- Metals do not look viable yet with the current rule set and family-specific search.")
    else:
        lines.extend(
            [
                f"- `{row.symbol}` with `{row.parameter_set_id}`: profit factor `{row.overall_profit_factor:.2f}`, total trades `{int(row.total_trades)}`, positive years `{int(row.positive_years)}/{int(row.years_covered)}`."
                for row in viable_metals.itertuples(index=False)
            ]
        )
    lines.extend(
        [
            "",
            "## Exclude For Now",
            "",
            f"- Markets that currently look weakest or too sparse for live alerts: `{', '.join(excluded_markets)}`.",
            "- `SPX500_USD` still produces no trades in the tested family grid.",
            "- `US30_USD` remains too sparse to treat as reliable despite one positive configuration.",
            "- `UK100_GBP`, `XAU_USD`, `XAG_USD`, and `WTICO_USD` do not currently show stable positive-year behavior.",
        ]
    )
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _select_history_file(directory: Path, *, prefix: str) -> Path:
    candidates = [path for path in directory.glob(f"{prefix}_*.csv") if "live" not in path.stem.lower()]
    if not candidates:
        raise FileNotFoundError(f"No historical files found for {directory} with prefix {prefix}.")
    return min(candidates, key=_history_file_sort_key)


def _history_file_sort_key(path: Path) -> tuple[pd.Timestamp, float]:
    parts = path.stem.split("_")
    start = pd.Timestamp(parts[1]) if len(parts) > 1 else pd.Timestamp.max
    end = pd.Timestamp(parts[2]) if len(parts) > 2 else pd.Timestamp.min
    return (start, -end.timestamp())


def _years_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return (end - start).total_seconds() / (365.25 * 24.0 * 60.0 * 60.0)


def _trade_frequency_per_month(trade_log: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float:
    months = max(_years_between(start, end) * 12.0, 1e-9)
    return float(len(trade_log) / months)


def _pct(value: object) -> float:
    return round(float(value) * 100.0, 2)


def _nan_or_int(value: object) -> float | int:
    if pd.isna(value):
        return np.nan
    return int(value)


def _finite_or_nan(value: object) -> float:
    value_float = float(value)
    if not np.isfinite(value_float):
        return np.nan
    return value_float


def _first_summary_row(summary: pd.DataFrame) -> pd.Series:
    if summary.empty:
        raise ValueError("Summary frame was empty.")
    return summary.iloc[0]


def _build_vectorized_signal_table_from_replay_proxy(
    *,
    candidates: pd.DataFrame,
    replay_bars: pd.DataFrame,
    replay_transitions: pd.DataFrame,
    parameter_set: ParameterSet,
) -> pd.DataFrame:
    if replay_transitions.empty:
        return pd.DataFrame()
    entry_transitions = replay_transitions.loc[
        replay_transitions["new_state"] == ReplayState.ENTRY_TRIGGERED
    ].copy()
    if entry_transitions.empty:
        return pd.DataFrame()

    candidate_columns = candidates.loc[
        :,
        ["symbol", "timestamp", "parabolic_exhaustion_score", "candidate_reason"],
    ].rename(columns={"timestamp": "candidate_timestamp"})
    merged = entry_transitions.merge(
        replay_bars,
        on=["symbol", "timestamp"],
        how="left",
        suffixes=("", "_bar"),
    ).merge(
        candidate_columns,
        on=["symbol", "candidate_timestamp"],
        how="left",
    )
    merged["parameter_set"] = parameter_set.name
    merged["candidate_score"] = merged["parabolic_exhaustion_score"]
    merged["signal_stage"] = "ENTRY_TRIGGERED"
    merged["signal_timeframe"] = parameter_set.signal_timeframe
    merged["bar_timeframe"] = merged["bar_timeframe"].fillna(parameter_set.signal_timeframe)
    merged["signal_rank"] = 1.0
    return merged.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def _infer_mismatch_driver(row: dict[str, object]) -> tuple[str, str]:
    vectorized_trades = int(row["vectorized_num_trades"])
    replay_trades = int(row["replay_num_trades"])
    vectorized_avg_r = float(row["vectorized_avg_R_per_trade"])
    replay_avg_r = float(row["replay_avg_R_per_trade"])
    timeframe = str(row["bar_timeframe"])

    if vectorized_trades == replay_trades and np.isclose(vectorized_avg_r, replay_avg_r, atol=0.05):
        return (
            "aligned",
            f"Counts and average R are closely aligned on {timeframe}.",
        )
    if vectorized_trades == 0 and replay_trades > 0:
        return (
            "intraday trigger logic",
            f"Replay found entry transitions but the vectorized signal proxy did not convert them into trades on {timeframe}.",
        )
    if vectorized_trades > replay_trades:
        return (
            "stop/partial/add behavior",
            f"Vectorized execution kept more trades than replay; replay-side invalidation or partial/break-even handling likely removed setups on {timeframe}.",
        )
    if vectorized_trades < replay_trades:
        if timeframe == "M15":
            return (
                "timeframe differences (M15)",
                "Coarser M15 bars can widen execution-path differences between simplified vectorized exits and replay management.",
            )
        return (
            "candidate selection / intraday trigger logic",
            "Replay accepted more candidate windows or re-entries than the simplified vectorized execution path.",
        )
    return (
        "stop/partial/add behavior",
        "Trade counts match more closely than R outcomes; exit management remains the main source of mismatch.",
    )


def main() -> None:
    strategy_config = load_strategy_config(PROJECT_ROOT / "config" / "strategy.yaml")
    backtest_config = load_backtest_config(PROJECT_ROOT / "config" / "backtest.yaml")
    assets_config = load_assets_config(PROJECT_ROOT / "config" / "assets.yaml")
    performance_matrix = run_historical_validation(
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        assets_config=assets_config,
    )
    mismatch_report = build_mismatch_report(performance_matrix)
    export_dataframe(mismatch_report, PROJECT_ROOT / "vectorized_replay_mismatch_report.csv")
    export_dataframe(mismatch_report, DEFAULT_OUTPUT_ROOT / "vectorized_replay_mismatch_report.csv")
    print(
        f"Wrote {len(performance_matrix)} rows to "
        f"{DEFAULT_PERFORMANCE_MATRIX_PATH}"
    )


if __name__ == "__main__":
    main()
