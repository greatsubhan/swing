from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from parabolic_exhaustion.backtest.historical_validation import (
    DEFAULT_OUTPUT_ROOT,
    PROJECT_ROOT,
    _finite_or_nan,
    _first_summary_row,
    _nan_or_int,
    _pct,
    _trade_frequency_per_month,
    _years_between,
    build_mismatch_report,
    build_robustness_ranking,
    build_walkforward_rows,
    export_dataframe,
    load_symbol_data,
)
from parabolic_exhaustion.backtest.replay import run_event_driven_replay
from parabolic_exhaustion.backtest.vectorized import run_vectorized_research
from parabolic_exhaustion.config import (
    AssetUniverseConfig,
    BacktestConfig,
    StrategyConfig,
    load_assets_config,
    load_backtest_config,
    load_strategy_config,
)
from parabolic_exhaustion.reporting.strategy_review import build_strategy_review_outputs
from parabolic_exhaustion.strategies.flow_strategy.config import (
    build_flow_backtest_variant,
    build_flow_strategy_variant,
    parameter_set_from_config,
)


FLOW_OUTPUT_ROOT = PROJECT_ROOT / "output" / "flow_validation"
FLOW_PERFORMANCE_PATH = PROJECT_ROOT / "performance_matrix_flow.csv"


def run_flow_historical_validation(
    *,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    assets_config: AssetUniverseConfig,
    parameter_config_attr: str = "flow_validation_parameter_sets",
    output_root: Path = FLOW_OUTPUT_ROOT,
    performance_matrix_path: Path = FLOW_PERFORMANCE_PATH,
    output_suffix: str = "flow",
) -> pd.DataFrame:
    output_root.mkdir(parents=True, exist_ok=True)
    raw_parameter_sets = getattr(backtest_config, parameter_config_attr)
    parameter_sets = [parameter_set_from_config(config) for config in raw_parameter_sets]
    if not parameter_sets:
        raise ValueError(f"No {parameter_config_attr} configured in backtest.yaml.")

    rows: list[dict[str, object]] = []
    walkforward_rows: list[dict[str, object]] = []
    parameter_docs: list[dict[str, object]] = []

    flow_symbols = set(strategy_config.flow_strategy.markets)
    instruments = [instrument for instrument in assets_config.instruments if instrument.symbol in flow_symbols]
    if not instruments:
        raise ValueError("No configured assets matched flow_strategy.markets.")

    for parameter_set in parameter_sets:
        parameter_docs.append(
            {
                "parameter_set_id": parameter_set.id,
                "symbols": ",".join(parameter_set.symbols),
                "opening_window_variant": parameter_set.opening_window_variant,
                "min_daily_atr_pct": parameter_set.min_daily_atr_pct,
                "min_vwap_slope_atr": parameter_set.min_vwap_slope_atr,
                "pullback_distance_atr": parameter_set.pullback_distance_atr,
                "max_extension_atr": parameter_set.max_extension_atr,
                "stop_atr_buffer": parameter_set.stop_atr_buffer,
                "stop_lookback_bars": parameter_set.stop_lookback_bars,
                "target_r": parameter_set.target_r,
                "partial_take_r": parameter_set.partial_take_r,
                "killzone_only": parameter_set.killzone_only,
                "max_trades_per_day": parameter_set.max_trades_per_day,
                "notes": parameter_set.notes,
            }
        )

    for instrument in instruments:
        data_window = load_symbol_data(instrument.symbol, asset_class=instrument.asset_class)
        if data_window.bar_timeframe.upper() != strategy_config.flow_strategy.signal_timeframe.upper():
            continue

        symbol_output_root = output_root / instrument.symbol
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

        for parameter_set in parameter_sets:
            if instrument.symbol not in parameter_set.symbols:
                continue

            strategy_variant = build_flow_strategy_variant(
                strategy_config=strategy_config,
                parameter_set=parameter_set,
            )
            backtest_variant = build_flow_backtest_variant(
                backtest_config=backtest_config,
                parameter_set=parameter_set,
            )
            strategy_context = {"parameter_set": parameter_set}
            vectorized_result = run_vectorized_research(
                daily_bars=data_window.daily_bars,
                intraday_bars_by_timeframe={data_window.bar_timeframe: data_window.intraday_bars},
                strategy_config=strategy_variant,
                backtest_config=backtest_variant,
                output_dir=symbol_output_root / parameter_set.id / "vectorized",
                strategy_type="flow_strategy",
                strategy_context=strategy_context,
            )
            replay_result = run_event_driven_replay(
                daily_bars=data_window.daily_bars,
                intraday_bars_by_timeframe={data_window.bar_timeframe: data_window.intraday_bars},
                strategy_config=strategy_variant,
                backtest_config=backtest_variant,
                output_dir=symbol_output_root / parameter_set.id / "replay",
                strategy_type="flow_strategy",
                strategy_context=strategy_context,
            )
            rows.append(
                build_flow_performance_matrix_row(
                    symbol=instrument.symbol,
                    data_window=data_window,
                    parameter_set_id=parameter_set.id,
                    opening_window_variant=parameter_set.opening_window_variant,
                    killzone_only=parameter_set.killzone_only,
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

    performance_matrix = pd.DataFrame(rows).sort_values(["symbol", "parameter_set_id"]).reset_index(drop=True)
    performance_matrix = performance_matrix.replace([np.inf, -np.inf], np.nan)
    walkforward_summary = pd.DataFrame(walkforward_rows).sort_values(
        ["symbol", "parameter_set_id", "year"]
    ).reset_index(drop=True)
    robustness_ranking = build_robustness_ranking(
        performance_matrix=performance_matrix,
        walkforward_summary=walkforward_summary,
    )
    mismatch_report = build_mismatch_report(performance_matrix)

    export_dataframe(performance_matrix, performance_matrix_path)
    export_dataframe(performance_matrix, output_root / f"performance_matrix_{output_suffix}.csv")
    export_dataframe(walkforward_summary, PROJECT_ROOT / f"walkforward_summary_{output_suffix}.csv")
    export_dataframe(walkforward_summary, output_root / f"walkforward_summary_{output_suffix}.csv")
    export_dataframe(robustness_ranking, PROJECT_ROOT / f"robustness_ranking_{output_suffix}.csv")
    export_dataframe(robustness_ranking, output_root / f"robustness_ranking_{output_suffix}.csv")
    export_dataframe(mismatch_report, PROJECT_ROOT / f"vectorized_replay_mismatch_report_{output_suffix}.csv")
    export_dataframe(mismatch_report, output_root / f"vectorized_replay_mismatch_report_{output_suffix}.csv")
    export_dataframe(pd.DataFrame(parameter_docs), output_root / f"parameter_sets_{output_suffix}.csv")

    write_flow_rules(strategy_config=strategy_config, destination=PROJECT_ROOT / "FLOW_STRATEGY_RULES.md")
    build_strategy_review_outputs(
        project_root=PROJECT_ROOT,
        performance_filename=f"performance_matrix_{output_suffix}.csv",
        robustness_filename=f"robustness_ranking_{output_suffix}.csv",
        mismatch_filename=f"vectorized_replay_mismatch_report_{output_suffix}.csv",
        walkforward_filename=f"walkforward_summary_{output_suffix}.csv",
        strategy_review_filename=f"strategy_review_table_{output_suffix}.csv",
        frequency_edge_filename=f"frequency_edge_table_{output_suffix}.csv",
        candidate_filename=f"candidate_live_setups_{output_suffix}.csv",
        notes_filename=f"FREQUENCY_EDGE_NOTES_{output_suffix.upper()}.md",
    )
    write_flow_notes(
        performance_matrix=performance_matrix,
        robustness_ranking=robustness_ranking,
        strategy_review_table=pd.read_csv(PROJECT_ROOT / f"strategy_review_table_{output_suffix}.csv"),
        candidate_live_setups=pd.read_csv(PROJECT_ROOT / f"candidate_live_setups_{output_suffix}.csv"),
        destination=PROJECT_ROOT / "FLOW_STRATEGY_NOTES.md" if output_suffix == "flow" else PROJECT_ROOT / "FLOW_OPENING_HOUR_NOTES.md",
    )
    return performance_matrix


def build_flow_performance_matrix_row(
    *,
    symbol: str,
    data_window,
    parameter_set_id: str,
    opening_window_variant: str,
    killzone_only: bool,
    vectorized_result: dict[str, pd.DataFrame],
    replay_result,
) -> dict[str, object]:
    vectorized_summary_row = _first_summary_row(vectorized_result["summary"])
    replay_summary_row = _first_summary_row(replay_result.summary_metrics)

    vectorized_total_pnl = float(vectorized_summary_row["total_pnl_points"])
    replay_total_pnl = float(replay_summary_row["total_pnl_points"])
    diff_pct = np.nan
    if not np.isclose(vectorized_total_pnl, 0.0):
        diff_pct = ((replay_total_pnl - vectorized_total_pnl) / abs(vectorized_total_pnl)) * 100.0

    return {
        "symbol": symbol,
        "parameter_set_id": parameter_set_id,
        "data_start": data_window.data_start,
        "data_end": data_window.data_end,
        "years_covered": round(_years_between(data_window.data_start, data_window.data_end), 2),
        "replay_data_start": data_window.replay_data_start,
        "replay_data_end": data_window.replay_data_end,
        "bar_timeframe": data_window.bar_timeframe,
        "opening_window_variant": opening_window_variant,
        "num_trading_days": int(data_window.daily_bars["timestamp"].dt.floor("D").nunique()),
        "num_bars_used": int(len(data_window.intraday_bars)),
        "killzone_only": killzone_only,
        "num_signals": _nan_or_int(replay_summary_row["confirmed_setup_count"]),
        "num_trades": _nan_or_int(replay_summary_row["trade_count"]),
        "win_rate_pct": _pct(replay_summary_row["win_rate"]),
        "profit_factor": _finite_or_nan(replay_summary_row["profit_factor"]),
        "avg_R_per_trade": _finite_or_nan(replay_summary_row["average_r"]),
        "avg_trade_duration_min": _finite_or_nan(replay_summary_row["average_hold_minutes"]),
        "max_drawdown_R": _finite_or_nan(replay_summary_row["max_drawdown_r"]),
        "vectorized_vs_replay_PnL_diff_pct": _finite_or_nan(diff_pct),
        "vectorized_num_signals": int(len(vectorized_result["signals"])),
        "vectorized_num_trades": int(len(vectorized_result["trades"])),
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
        "vectorized_trade_frequency_per_month": _trade_frequency_per_month(
            vectorized_result["trades"], data_window.replay_data_start, data_window.replay_data_end
        ),
        "replay_trade_frequency_per_month": _trade_frequency_per_month(
            replay_result.trade_log, data_window.replay_data_start, data_window.replay_data_end
        ),
    }


def write_flow_rules(*, strategy_config: StrategyConfig, destination: Path) -> None:
    flow = strategy_config.flow_strategy
    lines = [
        "# Flow Strategy Rules",
        "",
        "Strategy B uses a session VWAP pullback continuation model.",
        "",
        "## Instruments",
        "",
        f"- `{', '.join(flow.markets)}`",
        "",
        "## Timeframes",
        "",
        f"- Daily context: `{flow.daily_context_timeframe}`",
        f"- Execution timeframe: `{flow.signal_timeframe}`",
        "",
        "## Session And Kill-Zone Windows",
        "",
        "- Uses the existing London and New York session definitions from `config/strategy.yaml`.",
        "- Kill zones are optional per parameter set and stay objective timing filters only.",
        "",
        "## Entry Rules",
        "",
        "- Daily ATR regime must be above the configured minimum.",
        "- Long bias: price above VWAP, EMA fast above EMA slow, positive VWAP slope, and recent pullback back toward VWAP.",
        "- Short bias: price below VWAP, EMA fast below EMA slow, negative VWAP slope, and recent pullback back toward VWAP.",
        "- Long trigger: bullish continuation bar closes through the prior bar high after the pullback.",
        "- Short trigger: bearish continuation bar closes through the prior bar low after the pullback.",
        "",
        "## Stop Rules",
        "",
        "- Long stop: recent swing low minus ATR buffer.",
        "- Short stop: recent swing high plus ATR buffer.",
        "",
        "## Take-Profit Rules",
        "",
        "- Partial profit at configured partial R.",
        "- Stop moves to break-even after the partial when enabled.",
        "- Final target at configured target R.",
        "- Exit on VWAP invalidation before the partial or at forced end-of-session cutoff.",
        "",
        "## Risk And Trade Limits",
        "",
        f"- Max trades per day per symbol: default `{flow.max_trades_per_day}` before parameter overrides.",
        "- Fixed-R trade model with no overnight holds.",
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_flow_notes(
    *,
    performance_matrix: pd.DataFrame,
    robustness_ranking: pd.DataFrame,
    strategy_review_table: pd.DataFrame,
    candidate_live_setups: pd.DataFrame,
    destination: Path,
) -> None:
    has_opening_windows = "opening_window_variant" in strategy_review_table.columns
    title = "# Opening Hour Flow Strategy Notes" if destination.name == "FLOW_OPENING_HOUR_NOTES.md" else "# Flow Strategy Notes"
    best_by_symbol = {}
    for symbol in sorted(strategy_review_table["symbol"].unique()):
        best_by_symbol[symbol] = strategy_review_table.loc[
            strategy_review_table["symbol"] == symbol
        ].sort_values(["meets_quality_bar", "robustness_score", "profit_factor"], ascending=[False, False, False]).head(3)

    frequency_hits = strategy_review_table.loc[strategy_review_table["meets_frequency_goal"]]
    quality_hits = strategy_review_table.loc[strategy_review_table["meets_quality_bar"]]
    nas100_rows = best_by_symbol.get("NAS100_USD", pd.DataFrame())
    us30_rows = best_by_symbol.get("US30_USD", pd.DataFrame())
    nas100_frequency_leader = strategy_review_table.loc[
        strategy_review_table["symbol"] == "NAS100_USD"
    ].sort_values("approx_trades_per_day", ascending=False).head(1)
    us30_frequency_leader = strategy_review_table.loc[
        strategy_review_table["symbol"] == "US30_USD"
    ].sort_values("approx_trades_per_day", ascending=False).head(1)
    opening_window_summary = pd.DataFrame()
    if has_opening_windows:
        opening_window_summary = strategy_review_table.groupby("opening_window_variant", as_index=False).agg(
            avg_profit_factor=("profit_factor", "mean"),
            avg_avg_r=("avg_R_per_trade", "mean"),
            total_trades=("num_trades", "sum"),
            max_robustness=("robustness_score", "max"),
            quality_hits=("meets_quality_bar", "sum"),
            frequency_hits=("meets_frequency_goal", "sum"),
        ).sort_values(
            ["quality_hits", "frequency_hits", "avg_profit_factor", "max_robustness"],
            ascending=[False, False, False, False],
        )

    skip_open_rows = pd.DataFrame()
    if has_opening_windows:
        skip_open_rows = strategy_review_table.loc[
            strategy_review_table["opening_window_variant"].isin(["open_0935_1030", "open_0945_1030", "open_1000_1100"])
        ]

    lines = [
        title,
        "",
        "Strategy B is a new intraday VWAP pullback continuation model run on NAS100_USD and US30_USD.",
        "",
        "## NAS100_USD",
        "",
    ]
    if nas100_rows.empty:
        lines.append("- No NAS100 strategy rows were produced.")
    else:
        lines.extend(
            [
                f"- `{row.parameter_set_id}`: trades/day `{row.approx_trades_per_day:.3f}`, profit factor `{row.profit_factor:.2f}`, avg R `{row.avg_R_per_trade:.2f}`, max drawdown `{row.max_drawdown_R:.2f} R`, robustness `{row.robustness_score:.2f}`."
                for row in nas100_rows.itertuples(index=False)
            ]
        )

    lines.extend(["", "## US30_USD", ""])
    if us30_rows.empty:
        lines.append("- No US30 strategy rows were produced.")
    else:
        lines.extend(
            [
                f"- `{row.parameter_set_id}`: trades/day `{row.approx_trades_per_day:.3f}`, profit factor `{row.profit_factor:.2f}`, avg R `{row.avg_R_per_trade:.2f}`, max drawdown `{row.max_drawdown_R:.2f} R`, robustness `{row.robustness_score:.2f}`."
                for row in us30_rows.itertuples(index=False)
            ]
        )

    lines.extend(["", "## Frequency Goal", ""])
    if frequency_hits.empty:
        lines.append("- No current setup lands in the target zone of roughly 1-2 trades per day.")
    else:
        lines.extend(
            [
                f"- `{row.symbol}` / `{row.parameter_set_id}` meets the frequency goal at `{row.approx_trades_per_day:.2f}` trades/day."
                for row in frequency_hits.itertuples(index=False)
            ]
        )
    if not nas100_frequency_leader.empty:
        row = nas100_frequency_leader.iloc[0]
        lines.append(
            f"- NAS100 came closest with `{row['parameter_set_id']}` at `{row['approx_trades_per_day']:.3f}` trades/day."
        )
    if not us30_frequency_leader.empty:
        row = us30_frequency_leader.iloc[0]
        lines.append(
            f"- US30 came closest with `{row['parameter_set_id']}` at `{row['approx_trades_per_day']:.3f}` trades/day."
        )

    lines.extend(["", "## Edge And Robustness", ""])
    if quality_hits.empty:
        lines.append("- No current setup clears the existing quality bar across profit factor, average R, drawdown discipline, and walk-forward consistency.")
    else:
        lines.extend(
            [
                f"- `{row.symbol}` / `{row.parameter_set_id}` clears the quality bar with profit factor `{row.profit_factor:.2f}` and robustness `{row.robustness_score:.2f}`."
                for row in quality_hits.head(6).itertuples(index=False)
            ]
        )

    if has_opening_windows:
        lines.extend(["", "## Opening Window Comparison", ""])
        if opening_window_summary.empty:
            lines.append("- No opening-window summary could be computed.")
        else:
            best_window = opening_window_summary.iloc[0]
            lines.append(
                f"- Best opening window in this pass: `{best_window.opening_window_variant}` with average profit factor `{best_window.avg_profit_factor:.2f}`, max robustness `{best_window.max_robustness:.2f}`, and `{int(best_window.quality_hits)}` quality-bar hits."
            )
            for row in opening_window_summary.itertuples(index=False):
                lines.append(
                    f"- `{row.opening_window_variant}`: average profit factor `{row.avg_profit_factor:.2f}`, average R `{row.avg_avg_r:.2f}`, total trades `{int(row.total_trades)}`, quality hits `{int(row.quality_hits)}`, frequency hits `{int(row.frequency_hits)}`."
                )

        lines.extend(["", "## Skipping The Open", ""])
        open_0930 = strategy_review_table.loc[strategy_review_table["opening_window_variant"] == "open_0930_1030"]
        if open_0930.empty or skip_open_rows.empty:
            lines.append("- Not enough data to compare the full 09:30 open against delayed windows.")
        else:
            direct_open_pf = float(open_0930["profit_factor"].mean())
            delayed_pf = float(skip_open_rows["profit_factor"].mean())
            direct_open_r = float(open_0930["avg_R_per_trade"].mean())
            delayed_r = float(skip_open_rows["avg_R_per_trade"].mean())
            if delayed_pf > direct_open_pf and delayed_r >= direct_open_r:
                lines.append(
                    f"- Skipping the first 5-15 minutes improved the average edge in this batch: delayed windows averaged profit factor `{delayed_pf:.2f}` vs `{direct_open_pf:.2f}` and average R `{delayed_r:.2f}` vs `{direct_open_r:.2f}`."
                )
            else:
                lines.append(
                    f"- Skipping the first 5-15 minutes did not improve the average edge consistently in this batch: delayed windows averaged profit factor `{delayed_pf:.2f}` vs `{direct_open_pf:.2f}` and average R `{delayed_r:.2f}` vs `{direct_open_r:.2f}`."
                )

    lines.extend(
        [
            "",
            "## Forward-Test Readiness",
            "",
            f"- Candidate live setups found: `{len(candidate_live_setups)}`.",
            f"- Setups that clear both quality and frequency: `{int((strategy_review_table['meets_quality_bar'] & strategy_review_table['meets_frequency_goal']).sum())}`.",
            "- Strategy B is promising enough for forward testing only if at least one setup clears both the quality bar and the practical frequency target after this batch.",
            "- If no row clears both, it should stay in research rather than being promoted into the live bot.",
        ]
    )
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    strategy_config = load_strategy_config(PROJECT_ROOT / "config" / "strategy.yaml")
    backtest_config = load_backtest_config(PROJECT_ROOT / "config" / "backtest.yaml")
    assets_config = load_assets_config(PROJECT_ROOT / "config" / "assets.yaml")
    performance_matrix = run_flow_historical_validation(
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        assets_config=assets_config,
    )
    print(f"Wrote {len(performance_matrix)} Strategy B rows to {FLOW_PERFORMANCE_PATH}")


if __name__ == "__main__":
    main()
