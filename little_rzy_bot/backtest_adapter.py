"""Backtest adapter for signal-driven simulation (no broker execution)."""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import Signal, TradeResult
from .trendline import line_from_points, line_value


def _apply_costs(price: float, fee_bps: float, slippage_bps: float, adverse: bool) -> float:
    bps = (fee_bps + slippage_bps) / 10000.0
    return price * (1 + bps) if adverse else price * (1 - bps)


def simulate_signals(df: pd.DataFrame, signals: List[Signal], cfg: EngineConfig) -> List[TradeResult]:
    trades: List[TradeResult] = []
    index_lookup = {str(ts): idx for idx, ts in enumerate(df.index)}

    for sig in signals:
        start = index_lookup.get(sig.timestamp)
        if start is None:
            continue
        entry_index = start + 1
        if entry_index >= len(df):
            continue

        entry_open = float(df.iloc[entry_index]["open"])
        entry = _apply_costs(entry_open, cfg.risk.fee_bps, cfg.risk.slippage_bps, adverse=(sig.signal_type == "long"))
        stop = sig.stop_loss
        target = sig.target_1
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        expiry_index = min(len(df) - 1, entry_index + cfg.structure.max_setup_age_bars * 4)
        trendline_points = sig.structure.trendline_points
        slope, intercept = line_from_points(
            (trendline_points[0].index, trendline_points[0].price),
            (trendline_points[1].index, trendline_points[1].price),
        )
        trendline_tolerance = sig.structure.trendline_tolerance

        for j in range(entry_index, expiry_index + 1):
            row = df.iloc[j]
            stop_hit = row["low"] <= stop if sig.signal_type == "long" else row["high"] >= stop
            target_hit = row["high"] >= target if sig.signal_type == "long" else row["low"] <= target
            if stop_hit and target_hit:
                exit_reason = "stop" if cfg.risk.stop_priority_when_both_hit else "target"
            elif stop_hit:
                exit_reason = "stop"
            elif target_hit:
                exit_reason = "target"
            else:
                trendline_at_bar = line_value(slope, intercept, j)
                close_price = float(row["close"])
                invalidated = (
                    close_price < trendline_at_bar - trendline_tolerance
                    if sig.signal_type == "long"
                    else close_price > trendline_at_bar + trendline_tolerance
                )
                if not invalidated:
                    continue
                exit_reason = "trendline_invalidation"

            if exit_reason == "stop":
                exit_price = stop
            elif exit_reason == "target":
                exit_price = target
            else:
                exit_price = float(row["close"])
            pnl_r = ((exit_price - entry) / risk) if sig.signal_type == "long" else ((entry - exit_price) / risk)
            pnl_pct = ((exit_price / entry) - 1) if sig.signal_type == "long" else ((entry / exit_price) - 1)
            trades.append(
                TradeResult(
                    symbol=sig.symbol,
                    timeframe=sig.timeframe,
                    side=sig.signal_type,
                    signal_time=sig.timestamp,
                    entry_time=str(df.index[entry_index]),
                    exit_time=str(df.index[j]),
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    pnl_r=round(pnl_r, 4),
                    pnl_pct=round(pnl_pct, 4),
                    bars_held=j - entry_index,
                    trend_maturity=sig.trend_maturity,
                    quality_score=sig.quality_score,
                    bollinger_context=sig.bollinger_context.extension_state,
                    setup_id=sig.setup_id,
                )
            )
            break
        else:
            exit_row = df.iloc[expiry_index]
            exit_price = float(exit_row["close"])
            pnl_r = ((exit_price - entry) / risk) if sig.signal_type == "long" else ((entry - exit_price) / risk)
            pnl_pct = ((exit_price / entry) - 1) if sig.signal_type == "long" else ((entry / exit_price) - 1)
            trades.append(
                TradeResult(
                    symbol=sig.symbol,
                    timeframe=sig.timeframe,
                    side=sig.signal_type,
                    signal_time=sig.timestamp,
                    entry_time=str(df.index[entry_index]),
                    exit_time=str(df.index[expiry_index]),
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    exit_price=exit_price,
                    exit_reason="expired",
                    pnl_r=round(pnl_r, 4),
                    pnl_pct=round(pnl_pct, 4),
                    bars_held=expiry_index - entry_index,
                    trend_maturity=sig.trend_maturity,
                    quality_score=sig.quality_score,
                    bollinger_context=sig.bollinger_context.extension_state,
                    setup_id=sig.setup_id,
                )
            )
    return trades


def to_trade_log_df(trades: List[TradeResult]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in trades])
