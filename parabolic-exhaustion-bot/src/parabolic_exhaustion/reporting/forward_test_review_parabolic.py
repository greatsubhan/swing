from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from parabolic_exhaustion.live.profiles import PROJECT_ROOT, load_live_profile


DEFAULT_PROFILE_NAME = "NAS100_PARABOLIC_PAPER"


def build_forward_test_review(
    *,
    profile_name: str = DEFAULT_PROFILE_NAME,
    project_root: Path = PROJECT_ROOT,
) -> pd.DataFrame:
    runtime = load_live_profile(profile_name, project_root=project_root)
    log_path = runtime.forward_test_log_path
    output_path = project_root / "forward_test_review_parabolic.csv"

    if not log_path.exists():
        summary = pd.DataFrame(
            [
                {
                    "profile_name": profile_name,
                    "symbol": ",".join(runtime.profile.markets),
                    "parameter_set_id": runtime.profile.parameter_set_id,
                    "trade_count": 0,
                    "win_rate_pct": 0.0,
                    "profit_factor": 0.0,
                    "average_R": 0.0,
                    "max_drawdown_R": 0.0,
                    "backtest_profit_factor": np.nan,
                    "backtest_avg_R_per_trade": np.nan,
                    "backtest_approx_trades_per_day": np.nan,
                    "profit_factor_delta_vs_backtest": np.nan,
                    "average_R_delta_vs_backtest": np.nan,
                    "notes": f"Forward-test log not found at {log_path}",
                }
            ]
        )
        summary.to_csv(output_path, index=False)
        return summary

    log = pd.read_csv(log_path, parse_dates=["timestamp"])
    closed = log.loc[log["realized_result_R"].notna()].copy()
    closed = closed.drop_duplicates(subset=["setup_id", "state", "timestamp"])
    closed = closed.sort_values("timestamp").reset_index(drop=True)
    trade_count = int(len(closed))

    if closed.empty:
        profit_factor = 0.0
        average_r = 0.0
        win_rate_pct = 0.0
        max_drawdown_r = 0.0
    else:
        r = closed["realized_result_R"].astype(float)
        gross_wins = r.loc[r > 0].sum()
        gross_losses = r.loc[r < 0].sum()
        cumulative = r.cumsum()
        drawdown = cumulative - cumulative.cummax()
        profit_factor = float(gross_wins / abs(gross_losses)) if gross_losses < 0 else np.inf
        average_r = float(r.mean())
        win_rate_pct = float((r > 0).mean() * 100.0)
        max_drawdown_r = float(drawdown.min())

    backtest_reference = _load_backtest_reference(
        project_root=project_root,
        symbol=runtime.profile.markets[0],
        parameter_set_id=runtime.profile.parameter_set_id,
    )
    summary = pd.DataFrame(
        [
            {
                "profile_name": profile_name,
                "symbol": ",".join(runtime.profile.markets),
                "parameter_set_id": runtime.profile.parameter_set_id,
                "trade_count": trade_count,
                "win_rate_pct": round(win_rate_pct, 2),
                "profit_factor": profit_factor if np.isfinite(profit_factor) else np.nan,
                "average_R": average_r,
                "max_drawdown_R": max_drawdown_r,
                "backtest_profit_factor": backtest_reference.get("profit_factor"),
                "backtest_avg_R_per_trade": backtest_reference.get("avg_R_per_trade"),
                "backtest_approx_trades_per_day": backtest_reference.get("approx_trades_per_day"),
                "profit_factor_delta_vs_backtest": _delta(
                    profit_factor if np.isfinite(profit_factor) else np.nan,
                    backtest_reference.get("profit_factor"),
                ),
                "average_R_delta_vs_backtest": _delta(
                    average_r,
                    backtest_reference.get("avg_R_per_trade"),
                ),
                "notes": _build_notes(trade_count=trade_count, log_path=log_path, backtest_reference=backtest_reference),
            }
        ]
    )
    summary.to_csv(output_path, index=False)
    return summary


def _load_backtest_reference(
    *,
    project_root: Path,
    symbol: str,
    parameter_set_id: str,
) -> dict[str, float]:
    review_path = project_root / "strategy_review_table.csv"
    if not review_path.exists():
        return {}
    review = pd.read_csv(review_path)
    matched = review.loc[
        (review["symbol"] == symbol)
        & (review["parameter_set_id"] == parameter_set_id)
    ]
    if matched.empty:
        return {}
    row = matched.iloc[0]
    return {
        "profit_factor": float(row["profit_factor"]),
        "avg_R_per_trade": float(row["avg_R_per_trade"]),
        "approx_trades_per_day": float(row["approx_trades_per_day"]),
    }


def _delta(observed: float | None, reference: float | None) -> float | None:
    if observed is None or reference is None:
        return None
    if pd.isna(observed) or pd.isna(reference):
        return None
    return float(observed - reference)


def _build_notes(
    *,
    trade_count: int,
    log_path: Path,
    backtest_reference: dict[str, float],
) -> str:
    if trade_count == 0:
        return f"No closed trades logged yet. Source: {log_path}"
    if not backtest_reference:
        return f"Closed trades summarized from {log_path}; no matching backtest baseline found."
    return (
        f"Closed trades summarized from {log_path}; compared against strategy_review_table.csv "
        f"baseline for the configured NAS100 parabolic parameter set."
    )


def main() -> None:
    summary = build_forward_test_review()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
