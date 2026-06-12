"""Backtest adapter for signal-driven simulation (no broker execution)."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import List

import pandas as pd

from .config import EngineConfig
from .data_models import Signal, SimulationDiagnostics, TradeResult
from .trendline import line_from_points, line_value


def _apply_fill_costs(price: float, side: str, is_entry: bool, spread_points: float, slippage_points: float) -> float:
    """Apply adverse fill adjustments in raw price units."""
    half_spread = spread_points / 2.0
    adjustment = half_spread + slippage_points

    if side == "long":
        return price + adjustment if is_entry else price - adjustment
    return price - adjustment if is_entry else price + adjustment


def _trade_plan(df: pd.DataFrame, sig: Signal, cfg: EngineConfig) -> dict | None:
    index_lookup = {str(ts): idx for idx, ts in enumerate(df.index)}
    start = index_lookup.get(sig.timestamp)
    if start is None:
        return None
    entry_index = start + 1
    if entry_index >= len(df):
        return None

    entry_open = float(df.iloc[entry_index]["open"])
    entry = _apply_fill_costs(
        entry_open,
        sig.signal_type,
        is_entry=True,
        spread_points=cfg.risk.spread_points,
        slippage_points=cfg.risk.slippage_points,
    )
    stop = sig.stop_loss
    target = sig.target_1
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return None

    expiry_index = min(len(df) - 1, entry_index + cfg.structure.max_setup_age_bars * 4)
    trendline_points = sig.structure.trendline_points
    slope, intercept = line_from_points(
        (trendline_points[0].index, trendline_points[0].price),
        (trendline_points[1].index, trendline_points[1].price),
    )
    trendline_tolerance = sig.structure.trendline_tolerance

    exit_index = expiry_index
    exit_reason = "expired"
    exit_base_price = float(df.iloc[expiry_index]["close"])

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
            exit_base_price = stop
        elif exit_reason == "target":
            exit_base_price = target
        else:
            exit_base_price = float(row["close"])
        exit_index = j
        break

    exit_price = _apply_fill_costs(
        exit_base_price,
        sig.signal_type,
        is_entry=False,
        spread_points=cfg.risk.spread_points,
        slippage_points=cfg.risk.slippage_points,
    )
    direction = 1.0 if sig.signal_type == "long" else -1.0
    return {
        "signal": sig,
        "entry_index": entry_index,
        "entry_time": str(df.index[entry_index]),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "risk_per_unit": risk_per_unit,
        "exit_index": exit_index,
        "exit_time": str(df.index[exit_index]),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "bars_held": exit_index - entry_index,
        "direction": direction,
    }


def simulate_signals(df: pd.DataFrame, signals: List[Signal], cfg: EngineConfig) -> tuple[List[TradeResult], SimulationDiagnostics]:
    trades: List[TradeResult] = []
    diagnostics = SimulationDiagnostics()

    trade_plans = [plan for sig in signals if (plan := _trade_plan(df, sig, cfg)) is not None]
    trade_plans.sort(key=lambda plan: (plan["entry_time"], plan["signal"].symbol, plan["signal"].setup_id))

    active_trades: list[dict] = []
    trades_by_day: dict[str, int] = {}
    symbol_trades_by_day: dict[tuple[str, str], int] = {}
    realized_pnl_r_by_day: dict[str, float] = {}

    for plan in trade_plans:
        entry_dt = datetime.fromisoformat(plan["entry_time"].replace("Z", "+00:00"))
        entry_day = entry_dt.date().isoformat()

        still_open: list[dict] = []
        for active in active_trades:
            if active["exit_time"] <= plan["entry_time"]:
                exit_day = datetime.fromisoformat(active["exit_time"].replace("Z", "+00:00")).date().isoformat()
                realized_pnl_r_by_day[exit_day] = realized_pnl_r_by_day.get(exit_day, 0.0) + active["pnl_r"]
            else:
                still_open.append(active)
        active_trades = still_open

        if cfg.portfolio.max_daily_drawdown is not None:
            if realized_pnl_r_by_day.get(entry_day, 0.0) <= -cfg.portfolio.max_daily_drawdown:
                diagnostics.skipped_max_daily_drawdown += 1
                continue

        if cfg.portfolio.max_trades_per_day is not None:
            if trades_by_day.get(entry_day, 0) >= cfg.portfolio.max_trades_per_day:
                diagnostics.skipped_max_trades_per_day += 1
                continue

        symbol_key = (plan["signal"].symbol, entry_day)
        if cfg.portfolio.max_trades_per_symbol_per_day is not None:
            if symbol_trades_by_day.get(symbol_key, 0) >= cfg.portfolio.max_trades_per_symbol_per_day:
                diagnostics.skipped_max_trades_per_symbol_per_day += 1
                continue

        size_fraction = 1.0
        if cfg.portfolio.max_open_risk is not None:
            open_risk = sum(active["size_fraction"] for active in active_trades)
            remaining_risk = cfg.portfolio.max_open_risk - open_risk
            if remaining_risk <= 0:
                diagnostics.skipped_max_open_risk += 1
                continue
            if remaining_risk < 1.0:
                if not cfg.portfolio.allow_partial_size:
                    diagnostics.skipped_max_open_risk += 1
                    continue
                size_fraction = max(0.0, remaining_risk)
                diagnostics.partial_size_trades += 1

        gross_pnl = (plan["exit_price"] - plan["entry_price"]) * plan["direction"] * size_fraction
        commission_paid = cfg.risk.commission_per_trade * size_fraction
        net_pnl = gross_pnl - commission_paid
        pnl_r = net_pnl / plan["risk_per_unit"]
        pnl_pct = (net_pnl / plan["entry_price"]) if plan["entry_price"] else 0.0

        trade = TradeResult(
            trade_id=f"{plan['signal'].setup_id}:{len(trades) + 1}",
            symbol=plan["signal"].symbol,
            timeframe=plan["signal"].timeframe,
            profile_name=plan["signal"].profile_name or cfg.profile_name,
            side=plan["signal"].signal_type,
            signal_time=plan["signal"].timestamp,
            entry_time=plan["entry_time"],
            exit_time=plan["exit_time"],
            entry_price=plan["entry_price"],
            stop_price=plan["stop_price"],
            target_price=plan["target_price"],
            exit_price=plan["exit_price"],
            exit_reason=plan["exit_reason"],
            size_fraction=round(size_fraction, 4),
            gross_pnl=round(gross_pnl, 6),
            commission_paid=round(commission_paid, 6),
            net_pnl=round(net_pnl, 6),
            pnl_r=round(pnl_r, 4),
            pnl_pct=round(pnl_pct, 6),
            bars_held=plan["bars_held"],
            trend_maturity=plan["signal"].trend_maturity,
            quality_score=plan["signal"].quality_score,
            bollinger_context=plan["signal"].bollinger_context.extension_state,
            atr_at_entry=plan["signal"].atr_at_entry,
            bar_range_at_entry=plan["signal"].bar_range_at_entry,
            retrace_pct=plan["signal"].retrace_pct,
            rr_target=plan["signal"].risk_reward,
            volatility_regime=plan["signal"].volatility_regime,
            session=plan["signal"].session,
            structure_tag=plan["signal"].structure_tag,
            higher_timeframe_bias=plan["signal"].higher_timeframe_bias,
            setup_id=plan["signal"].setup_id,
        )
        trades.append(trade)
        diagnostics.accepted_trades += 1
        trades_by_day[entry_day] = trades_by_day.get(entry_day, 0) + 1
        symbol_trades_by_day[symbol_key] = symbol_trades_by_day.get(symbol_key, 0) + 1
        active_trades.append({"exit_time": plan["exit_time"], "size_fraction": size_fraction, "pnl_r": pnl_r})

    return trades, diagnostics


def to_trade_log_df(trades: List[TradeResult]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])
