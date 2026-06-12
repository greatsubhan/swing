"""Performance reporting and sweep helpers."""
from __future__ import annotations

from typing import Dict, List
import pandas as pd

from .data_models import PerformanceSummary, SimulationDiagnostics


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


def summarize(trade_log: pd.DataFrame, diagnostics: SimulationDiagnostics | None = None) -> PerformanceSummary:
    if trade_log.empty:
        diagnostics = diagnostics or SimulationDiagnostics()
        return PerformanceSummary(
            trades=0,
            win_rate=0,
            avg_r=0,
            expectancy_r=0,
            max_drawdown_r=0,
            profit_factor=0,
            avg_hold_bars=0,
            longs=0,
            shorts=0,
            total_net_pnl=0.0,
            total_commission=0.0,
            max_drawdown_currency=0.0,
            skipped_trades=(
                diagnostics.skipped_max_daily_drawdown
                + diagnostics.skipped_filters
                + diagnostics.skipped_max_open_risk
                + diagnostics.skipped_max_trades_per_day
                + diagnostics.skipped_max_trades_per_symbol_per_day
            ),
            partial_size_trades=diagnostics.partial_size_trades,
        )

    diagnostics = diagnostics or SimulationDiagnostics()
    wins = trade_log[trade_log["pnl_r"] > 0]["pnl_r"].sum()
    losses = abs(trade_log[trade_log["pnl_r"] <= 0]["pnl_r"].sum())
    equity = trade_log["pnl_r"].cumsum()
    dd = equity - equity.cummax()
    cash_equity = trade_log["net_pnl"].cumsum() if "net_pnl" in trade_log else pd.Series(dtype=float)
    cash_dd = (cash_equity - cash_equity.cummax()).min() if not cash_equity.empty else 0.0

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
        total_net_pnl=float(trade_log["net_pnl"].sum()) if "net_pnl" in trade_log else 0.0,
        total_commission=float(trade_log["commission_paid"].sum()) if "commission_paid" in trade_log else 0.0,
        max_drawdown_currency=float(abs(cash_dd)),
        skipped_trades=(
            diagnostics.skipped_max_daily_drawdown
            + diagnostics.skipped_filters
            + diagnostics.skipped_max_open_risk
            + diagnostics.skipped_max_trades_per_day
            + diagnostics.skipped_max_trades_per_symbol_per_day
        ),
        partial_size_trades=diagnostics.partial_size_trades,
        by_symbol=_bucket_metrics(trade_log, "symbol"),
        by_timeframe=_bucket_metrics(trade_log, "timeframe"),
        by_trend_maturity=_bucket_metrics(trade_log, "trend_maturity"),
        by_bollinger_bucket=_bucket_metrics(trade_log, "bollinger_context"),
    )


def parameter_sweep_rows(results: List[dict]) -> pd.DataFrame:
    return pd.DataFrame(results)
