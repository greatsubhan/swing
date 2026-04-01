"""Performance reporting and sweep helpers."""
from __future__ import annotations

from typing import Dict, List
import pandas as pd

from .data_models import PerformanceSummary


def _bucket_metrics(df: pd.DataFrame, key: str) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    if df.empty:
        return out
    for k, g in df.groupby(key):
        out[str(k)] = {
            "trades": float(len(g)),
            "win_rate": float((g["pnl_r"] > 0).mean()),
            "avg_r": float(g["pnl_r"].mean()),
        }
    return out


def summarize(trade_log: pd.DataFrame) -> PerformanceSummary:
    if trade_log.empty:
        return PerformanceSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)

    wins = trade_log[trade_log["pnl_r"] > 0]["pnl_r"].sum()
    losses = abs(trade_log[trade_log["pnl_r"] <= 0]["pnl_r"].sum())
    equity = trade_log["pnl_r"].cumsum()
    dd = equity - equity.cummax()

    return PerformanceSummary(
        trades=len(trade_log),
        win_rate=float((trade_log["pnl_r"] > 0).mean()),
        avg_r=float(trade_log["pnl_r"].mean()),
        expectancy_r=float(trade_log["pnl_r"].mean()),
        max_drawdown_r=float(dd.min()),
        profit_factor=float(wins / losses) if losses else 999.0,
        avg_hold_bars=float(trade_log["bars_held"].mean()),
        longs=int((trade_log["side"] == "long").sum()),
        shorts=int((trade_log["side"] == "short").sum()),
        by_symbol=_bucket_metrics(trade_log, "symbol"),
        by_timeframe=_bucket_metrics(trade_log, "timeframe"),
        by_trend_maturity=_bucket_metrics(trade_log, "trend_maturity"),
        by_bollinger_bucket=_bucket_metrics(trade_log, "bollinger_context"),
    )


def parameter_sweep_rows(results: List[dict]) -> pd.DataFrame:
    return pd.DataFrame(results)
