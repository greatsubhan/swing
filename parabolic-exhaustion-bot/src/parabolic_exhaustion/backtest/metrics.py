from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_trade_log(
    trade_log: pd.DataFrame,
    *,
    candidate_count: int,
    signal_count: int,
    parameter_set: str,
) -> pd.DataFrame:
    if trade_log.empty:
        return pd.DataFrame(
            [
                {
                    "parameter_set": parameter_set,
                    "candidate_count": candidate_count,
                    "confirmed_setup_count": signal_count,
                    "trade_count": 0,
                    "win_rate": 0.0,
                    "expectancy_r": 0.0,
                    "average_r": 0.0,
                    "total_r": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown_r": 0.0,
                    "average_hold_minutes": 0.0,
                    "total_pnl_points": 0.0,
                }
            ]
        )

    r = trade_log["r_multiple"].fillna(0.0)
    gross_wins = trade_log.loc[r > 0, "pnl_points"].sum()
    gross_losses = trade_log.loc[r < 0, "pnl_points"].sum()
    cumulative_r = r.cumsum()
    drawdown = cumulative_r - cumulative_r.cummax()

    return pd.DataFrame(
        [
            {
                "parameter_set": parameter_set,
                "candidate_count": candidate_count,
                "confirmed_setup_count": signal_count,
                "trade_count": int(len(trade_log)),
                "win_rate": float((r > 0).mean()),
                "expectancy_r": float(r.mean()),
                "average_r": float(r.mean()),
                "total_r": float(r.sum()),
                "profit_factor": float(gross_wins / abs(gross_losses)) if gross_losses < 0 else np.inf,
                "max_drawdown_r": float(drawdown.min()),
                "average_hold_minutes": float(trade_log["hold_minutes"].mean()),
                "total_pnl_points": float(trade_log["pnl_points"].sum()),
            }
        ]
    )
