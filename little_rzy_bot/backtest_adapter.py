"""Backtest adapter for signal-driven simulation (no broker execution)."""
from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from .config import EngineConfig
from .data_models import Signal, TradeResult


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
        entry = _apply_costs(sig.entry, cfg.risk.fee_bps, cfg.risk.slippage_bps, adverse=(sig.signal_type == "long"))
        stop = sig.stop_loss
        target = sig.target_1
        risk = abs(entry - stop)

        for j in range(start + 1, min(len(df), start + 1 + cfg.structure.max_setup_age_bars * 4)):
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
                continue

            exit_price = stop if exit_reason == "stop" else target
            pnl_r = ((exit_price - entry) / risk) if sig.signal_type == "long" else ((entry - exit_price) / risk)
            pnl_pct = ((exit_price / entry) - 1) if sig.signal_type == "long" else ((entry / exit_price) - 1)
            trades.append(
                TradeResult(
                    symbol=sig.symbol,
                    timeframe=sig.timeframe,
                    side=sig.signal_type,
                    signal_time=sig.timestamp,
                    entry_time=str(df.index[start + 1]),
                    exit_time=str(df.index[j]),
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    pnl_r=round(pnl_r, 4),
                    pnl_pct=round(pnl_pct, 4),
                    bars_held=j - (start + 1),
                    trend_maturity=sig.trend_maturity,
                    quality_score=sig.quality_score,
                    bollinger_context=sig.bollinger_context.extension_state,
                    setup_id=sig.setup_id,
                )
            )
            break
    return trades


def to_trade_log_df(trades: List[TradeResult]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in trades])
