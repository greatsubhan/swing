from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

MARKET_FAMILY_BY_SYMBOL = {
    "XAU_USD": "metals",
    "XAG_USD": "metals",
    "WTICO_USD": "metals",
    "NAS100_USD": "indices",
    "UK100_GBP": "indices",
    "US30_USD": "indices",
    "SPX500_USD": "indices",
}

TRADING_DAYS_PER_YEAR = 252.0
QUALITY_MIN_PROFIT_FACTOR = 1.5
QUALITY_MIN_TOTAL_TRADES = 4
QUALITY_MIN_POSITIVE_YEAR_RATIO = 0.25


def build_strategy_review_outputs(
    project_root: Path = PROJECT_ROOT,
    *,
    performance_filename: str = "performance_matrix.csv",
    robustness_filename: str = "robustness_ranking.csv",
    mismatch_filename: str = "vectorized_replay_mismatch_report.csv",
    walkforward_filename: str = "walkforward_summary.csv",
    strategy_review_filename: str = "strategy_review_table.csv",
    frequency_edge_filename: str = "frequency_edge_table.csv",
    candidate_filename: str = "candidate_live_setups.csv",
    notes_filename: str = "FREQUENCY_EDGE_NOTES.md",
) -> dict[str, pd.DataFrame]:
    performance = pd.read_csv(
        project_root / performance_filename,
        parse_dates=["data_start", "data_end", "replay_data_start", "replay_data_end"],
    )
    robustness = pd.read_csv(project_root / robustness_filename)
    mismatch = pd.read_csv(project_root / mismatch_filename)
    walkforward = pd.read_csv(project_root / walkforward_filename)

    review = performance.merge(
        robustness.loc[
            :,
            [
                "symbol",
                "parameter_set_id",
                "years_covered",
                "positive_years",
                "worst_year_profit_factor",
                "robustness_score",
            ],
        ],
        on=["symbol", "parameter_set_id"],
        how="left",
        suffixes=("", "_robustness"),
    ).merge(
        mismatch.loc[
            :,
            ["symbol", "parameter_set_id", "likely_mismatch_driver"],
        ],
        on=["symbol", "parameter_set_id"],
        how="left",
    )

    replay_years = (
        (review["replay_data_end"] - review["replay_data_start"]).dt.total_seconds()
        / (365.25 * 24.0 * 60.0 * 60.0)
    ).replace(0.0, np.nan)
    review["market_family"] = review["symbol"].map(MARKET_FAMILY_BY_SYMBOL)
    review["data_start"] = review["replay_data_start"]
    review["data_end"] = review["replay_data_end"]
    review["years_covered"] = replay_years.round(2)
    review["trades_per_year"] = (review["replay_num_trades"] / replay_years).replace([np.inf, -np.inf], np.nan)
    review["trades_per_month"] = review["trades_per_year"] / 12.0
    review["approx_trades_per_day"] = review["trades_per_year"] / TRADING_DAYS_PER_YEAR
    review["gross_R"] = review["replay_avg_R_per_trade"] * review["replay_num_trades"]
    review["years_tested"] = review["years_covered_robustness"]
    review["vectorized_replay_aligned"] = review["likely_mismatch_driver"].eq("aligned")
    review["meets_frequency_goal"] = review["approx_trades_per_day"].between(1.0, 2.0, inclusive="both")
    review["meets_quality_bar"] = review.apply(_meets_quality_bar, axis=1)
    review["frequency_bucket"] = review["approx_trades_per_day"].map(_frequency_bucket)

    strategy_review_table = review.loc[
        :,
        [
            "symbol",
            "market_family",
            "parameter_set_id",
            *([ "opening_window_variant" ] if "opening_window_variant" in review.columns else []),
            "bar_timeframe",
            "data_start",
            "data_end",
            "years_covered",
            "num_signals",
            "num_trades",
            "trades_per_year",
            "trades_per_month",
            "approx_trades_per_day",
            "win_rate_pct",
            "profit_factor",
            "avg_R_per_trade",
            "gross_R",
            "max_drawdown_R",
            "positive_years",
            "years_tested",
            "robustness_score",
            "killzone_only",
            "vectorized_replay_aligned",
            "meets_frequency_goal",
            "meets_quality_bar",
        ],
    ].sort_values(["market_family", "symbol", "robustness_score"], ascending=[True, True, False]).reset_index(drop=True)

    frequency_edge_table = strategy_review_table.loc[
        :,
        [
            "symbol",
            "parameter_set_id",
            *([ "opening_window_variant" ] if "opening_window_variant" in strategy_review_table.columns else []),
            "approx_trades_per_day",
            "profit_factor",
            "avg_R_per_trade",
            "win_rate_pct",
            "max_drawdown_R",
            "robustness_score",
            "meets_frequency_goal",
            "meets_quality_bar",
        ],
    ].copy()
    frequency_edge_table["frequency_bucket"] = review["frequency_bucket"].values
    frequency_edge_table["bucket_order"] = frequency_edge_table["frequency_bucket"].map(_frequency_bucket_order)
    frequency_edge_table = frequency_edge_table.sort_values(
        ["bucket_order", "approx_trades_per_day", "robustness_score", "profit_factor"],
        ascending=[True, False, False, False],
    ).drop(columns=["bucket_order"]).reset_index(drop=True)

    candidate_live_setups = strategy_review_table.loc[
        strategy_review_table["vectorized_replay_aligned"] & strategy_review_table["meets_quality_bar"]
    ].sort_values(
        ["meets_frequency_goal", "robustness_score", "profit_factor"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    strategy_review_table.to_csv(project_root / strategy_review_filename, index=False)
    frequency_edge_table.to_csv(project_root / frequency_edge_filename, index=False)
    candidate_live_setups.to_csv(project_root / candidate_filename, index=False)
    write_frequency_edge_notes(
        strategy_review_table=strategy_review_table,
        frequency_edge_table=frequency_edge_table,
        candidate_live_setups=candidate_live_setups,
        destination=project_root / notes_filename,
        walkforward=walkforward,
    )
    return {
        "strategy_review_table": strategy_review_table,
        "frequency_edge_table": frequency_edge_table,
        "candidate_live_setups": candidate_live_setups,
    }


def write_frequency_edge_notes(
    *,
    strategy_review_table: pd.DataFrame,
    frequency_edge_table: pd.DataFrame,
    candidate_live_setups: pd.DataFrame,
    destination: Path,
    walkforward: pd.DataFrame,
) -> None:
    meets_frequency_goal = strategy_review_table.loc[strategy_review_table["meets_frequency_goal"]]
    best_nas100 = candidate_live_setups.loc[
        candidate_live_setups["symbol"] == "NAS100_USD"
    ].head(3)
    best_other_indices = candidate_live_setups.loc[
        candidate_live_setups["market_family"] == "indices"
    ]
    best_other_indices = best_other_indices.loc[best_other_indices["symbol"] != "NAS100_USD"].head(3)
    metals = strategy_review_table.loc[strategy_review_table["market_family"] == "metals"]
    highest_frequency = frequency_edge_table.head(5)

    notes = [
        "# Frequency Edge Notes",
        "",
        "Quality bar used in this review:",
        f"- `profit_factor >= {QUALITY_MIN_PROFIT_FACTOR}`",
        "- `avg_R_per_trade > 0`",
        "- `gross_R > 0`",
        "- `abs(max_drawdown_R) <= gross_R`",
        f"- at least `{QUALITY_MIN_TOTAL_TRADES}` total trades",
        f"- positive year ratio >= `{QUALITY_MIN_POSITIVE_YEAR_RATIO:.2f}`",
        "",
        "Frequency assumptions:",
        f"- `approx_trades_per_day = trades_per_year / {int(TRADING_DAYS_PER_YEAR)}`",
        "- `meets_frequency_goal` is true only for approximately `1.0` to `2.0` trades/day",
        "",
    ]

    if meets_frequency_goal.empty:
        notes.append("- No current setup gets close to the `1–2 trades/day` goal. The best setups are still well below daily frequency.")
    else:
        notes.extend(
            [
                "- Setups that currently meet the `1–2 trades/day` goal:",
                *[
                    f"  - `{row.symbol}` / `{row.parameter_set_id}` at about `{row.approx_trades_per_day:.2f}` trades/day."
                    for row in meets_frequency_goal.itertuples(index=False)
                ],
            ]
        )

    notes.extend(
        [
            "",
            "- As frequency rises in the current dataset, quality does not improve enough to justify a daily-trade target. The higher-frequency rows remain far below `1 trade/day`, and loosening filters mostly adds low-quality or zero-edge trades rather than scalable flow.",
            "",
            "## NAS100",
            "",
        ]
    )
    if best_nas100.empty:
        notes.append("- NAS100 does not currently clear the quality bar, which would be a strong warning against live use.")
    else:
        notes.extend(
            [
                f"- `{row.parameter_set_id}`: about `{row.approx_trades_per_day:.3f}` trades/day, profit factor `{row.profit_factor:.2f}`, average `{row.avg_R_per_trade:.2f} R`, robustness `{row.robustness_score:.2f}`."
                for row in best_nas100.itertuples(index=False)
            ]
        )

    notes.extend(
        [
            "",
            "## Other Indices",
            "",
        ]
    )
    if best_other_indices.empty:
        notes.append("- No non-NAS100 index setup clears the current quality bar. `SPX500_USD` is inactive, and `UK100_GBP`/`US30_USD` remain too sparse or too weak.")
    else:
        notes.extend(
            [
                f"- `{row.symbol}` / `{row.parameter_set_id}`: about `{row.approx_trades_per_day:.3f}` trades/day, profit factor `{row.profit_factor:.2f}`."
                for row in best_other_indices.itertuples(index=False)
            ]
        )

    notes.extend(
        [
            "",
            "## Metals",
            "",
        ]
    )
    if metals["meets_quality_bar"].any():
        qualified_metals = metals.loc[metals["meets_quality_bar"]].head(5)
        notes.extend(
            [
                f"- `{row.symbol}` / `{row.parameter_set_id}` unexpectedly clears the quality bar at `{row.approx_trades_per_day:.3f}` trades/day."
                for row in qualified_metals.itertuples(index=False)
            ]
        )
    else:
        notes.append("- Metals do not currently clear the quality bar. With current logic they should be treated as non-viable for live alerts.")

    notes.extend(
        [
            "",
            "## Conclusion",
            "",
            "- NAS100 should remain the only serious candidate at this stage.",
            "- Even NAS100 behaves like a low-frequency edge rather than a `1–2 trades/day` system.",
            "- The current strategy should be treated as a selective, low-frequency setup. If daily trade flow is a hard requirement, it likely needs a second setup rather than forcing this one to trade more often.",
            "",
            "Highest-frequency rows in the current review:",
        ]
    )
    notes.extend(
        [
            f"- `{row.symbol}` / `{row.parameter_set_id}`: `{row.approx_trades_per_day:.3f}` trades/day, profit factor `{row.profit_factor:.2f}`, avg R `{row.avg_R_per_trade:.2f}`."
            for row in highest_frequency.itertuples(index=False)
        ]
    )
    destination.write_text("\n".join(notes) + "\n", encoding="utf-8")


def _meets_quality_bar(row: pd.Series) -> bool:
    gross_r = float(row["gross_R"])
    max_drawdown_r = float(row["max_drawdown_R"])
    years_tested = int(row["years_tested"])
    positive_years = int(row["positive_years"])
    if years_tested <= 0:
        return False
    positive_year_ratio = positive_years / years_tested
    return bool(
        row["profit_factor"] >= QUALITY_MIN_PROFIT_FACTOR
        and row["avg_R_per_trade"] > 0
        and gross_r > 0
        and abs(max_drawdown_r) <= gross_r
        and row["num_trades"] >= QUALITY_MIN_TOTAL_TRADES
        and positive_year_ratio >= QUALITY_MIN_POSITIVE_YEAR_RATIO
    )


def _frequency_bucket(value: float) -> str:
    if pd.isna(value):
        return "< 1 trade/week"
    if value < (1.0 / 5.0):
        return "< 1 trade/week"
    if value < (4.0 / 5.0):
        return "1-4 trades/week"
    if value <= 1.2:
        return "~1 trade/day"
    return "> 1 trade/day"


def _frequency_bucket_order(label: str) -> int:
    order = {
        "< 1 trade/week": 0,
        "1-4 trades/week": 1,
        "~1 trade/day": 2,
        "> 1 trade/day": 3,
    }
    return order[label]


def main() -> None:
    outputs = build_strategy_review_outputs()
    print(
        f"Wrote {len(outputs['strategy_review_table'])} strategy rows, "
        f"{len(outputs['frequency_edge_table'])} frequency rows, and "
        f"{len(outputs['candidate_live_setups'])} candidate rows."
    )


if __name__ == "__main__":
    main()
