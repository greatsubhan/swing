"""Focused CWT risk-ladder replay on the strongest first-pass pairs.

This replays trade sequences from the CWT setup engine and applies:

- flat 0.15% risk per trade
- recovery ladder 0.15 / 0.30 / 0.60 / 1.20

The ladder resets after a winning trade and advances after a losing or
non-positive trade. This is a money-management overlay, not a source of edge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signal_platform.env import load_dotenv
from research.cwt_forex_backtest import (
    BUFFER_ATR_FRACTION,
    MAX_BARS_HELD,
    Position,
    compute_bias_series,
    compute_mt5_zigzag,
    load_oanda_history,
    project_cambist_levels,
    scenario_one_long,
    scenario_one_short,
    scenario_two_long,
    scenario_two_short,
    trailing_stop,
    with_indicators,
)

OUTPUT_DIR = Path("reports/cwt_forex")
LADDER = [0.15, 0.30, 0.60, 1.20]
FLAT_RISK = 0.15
FOCUS_SYMBOLS = ["USD_JPY", "EUR_USD", "NZD_USD", "USD_CAD"]
EXIT_MODES = ["rr1", "jaw_trail"]
SCENARIO_FILTERS = ["scenario1", "scenario2", "both"]


def generate_trade_log(
    symbol: str,
    execution_granularity: str = "M5",
    execution_label: str = "5m",
    exit_mode: str = "rr1",
    scenario_filter: str = "both",
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, object]]:
    history_start = start or START
    history_end = end or END
    execution = with_indicators(load_oanda_history(symbol, execution_granularity, start=history_start, end=history_end))
    bias_frame = with_indicators(load_oanda_history(symbol, "H1", start=history_start, end=history_end))
    pivot_high, pivot_low = compute_mt5_zigzag(execution, symbol)
    cambist = project_cambist_levels(execution, pivot_high, pivot_low)
    bias_frame = bias_frame.copy()
    bias_frame["bias_signal"] = compute_bias_series(bias_frame)
    execution = execution.sort_index().copy()
    execution["timestamp"] = execution.index
    execution["ts_key"] = pd.Index(execution.index).asi8
    bias_lookup = bias_frame[["bias_signal"]].sort_index().copy()
    bias_lookup["ts_key"] = pd.Index(bias_lookup.index).asi8
    execution = pd.merge_asof(
        execution,
        bias_lookup[["ts_key", "bias_signal"]],
        on="ts_key",
        direction="backward",
    )
    execution = execution.set_index("timestamp").drop(columns=["ts_key"])
    execution["bias_signal"] = execution["bias_signal"].fillna(0).astype("int64")
    execution["active_blue"] = cambist["active_blue"]
    execution["active_red"] = cambist["active_red"]

    position: Position | None = None
    trade_log: list[dict[str, object]] = []

    for idx in range(120, len(execution) - 1):
        row = execution.iloc[idx]
        bar_time = execution.index[idx]
        if pd.isna(row["atr14"]) or pd.isna(row["jaw"]):
            continue

        bias = int(row["bias_signal"])
        active_blue = float(row["active_blue"]) if pd.notna(row["active_blue"]) else None
        active_red = float(row["active_red"]) if pd.notna(row["active_red"]) else None

        if position is not None:
            position.bars_held += 1
            if exit_mode == "jaw_trail":
                previous_row = execution.iloc[idx - 1]
                position.stop_price = trailing_stop(position, previous_row)

            exit_price: float | None = None
            reason: str | None = None
            if position.side == "long":
                if row["low"] <= position.stop_price:
                    exit_price = position.stop_price
                    reason = "stop"
                elif position.target_price is not None and row["high"] >= position.target_price:
                    exit_price = position.target_price
                    reason = "target"
                elif bias == -1:
                    exit_price = float(row["close"])
                    reason = "bias_flip"
            else:
                if row["high"] >= position.stop_price:
                    exit_price = position.stop_price
                    reason = "stop"
                elif position.target_price is not None and row["low"] <= position.target_price:
                    exit_price = position.target_price
                    reason = "target"
                elif bias == 1:
                    exit_price = float(row["close"])
                    reason = "bias_flip"

            if exit_price is None and position.bars_held >= MAX_BARS_HELD:
                exit_price = float(row["close"])
                reason = "timeout"

            if exit_price is not None and reason is not None:
                if position.side == "long":
                    r_multiple = (exit_price - position.entry_price) / position.initial_risk
                else:
                    r_multiple = (position.entry_price - exit_price) / position.initial_risk
                trade_log.append(
                    {
                        "symbol": symbol,
                        "side": position.side,
                        "scenario": position.scenario,
                        "entry_time": position.entry_time.isoformat(),
                        "exit_time": bar_time.isoformat(),
                        "bars_held": position.bars_held,
                        "r_multiple": round(float(r_multiple), 6),
                        "reason": reason,
                    }
                )
                position = None
                continue

        if position is not None:
            continue

        long_signal = scenario_one_long(execution, idx, bias)
        short_signal = scenario_one_short(execution, idx, bias)
        if long_signal is None and short_signal is None:
            long_signal = scenario_two_long(execution, idx, bias, active_red)
            short_signal = scenario_two_short(execution, idx, bias, active_blue)

        signal = long_signal if long_signal is not None else short_signal
        if signal is None:
            continue
        if scenario_filter != "both" and signal["scenario"] != scenario_filter:
            continue

        next_bar = execution.iloc[idx + 1]
        entry_time = execution.index[idx + 1]
        entry_price = float(next_bar["open"])
        buffer = signal["atr"] * BUFFER_ATR_FRACTION
        if signal is long_signal:
            side = "long"
            stop_price = float(signal["stop_anchor"] - buffer)
            if stop_price >= entry_price:
                continue
            risk = entry_price - stop_price
            target = entry_price + risk if exit_mode == "rr1" else None
        else:
            side = "short"
            stop_price = float(signal["stop_anchor"] + buffer)
            if stop_price <= entry_price:
                continue
            risk = stop_price - entry_price
            target = entry_price - risk if exit_mode == "rr1" else None

        if risk <= 0:
            continue

        position = Position(
            symbol=symbol,
            side=side,
            entry_time=entry_time,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target,
            initial_risk=risk,
            scenario=signal["scenario"],
        )

    if position is not None:
        final_bar = execution.iloc[-1]
        final_price = float(final_bar["close"])
        if position.side == "long":
            r_multiple = (final_price - position.entry_price) / position.initial_risk
        else:
            r_multiple = (position.entry_price - final_price) / position.initial_risk
        trade_log.append(
            {
                "symbol": symbol,
                "side": position.side,
                "scenario": position.scenario,
                "entry_time": position.entry_time.isoformat(),
                "exit_time": execution.index[-1].isoformat(),
                "bars_held": position.bars_held,
                "r_multiple": round(float(r_multiple), 6),
                "reason": "final_bar",
            }
        )

    return trade_log


def replay_flat(trades: list[dict[str, object]], risk_pct: float = FLAT_RISK) -> dict[str, object]:
    pnl_pcts: list[float] = []
    for trade in trades:
        pnl = float(trade["r_multiple"]) * risk_pct
        pnl_pcts.append(pnl)
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p < 0]
    return {
        "mode": "flat",
        "risk_sequence": [risk_pct],
        "trades": len(trades),
        "net_pct": round(sum(pnl_pcts), 3),
        "avg_pct_per_trade": round(sum(pnl_pcts) / len(pnl_pcts), 4) if pnl_pcts else 0.0,
        "win_rate": round((len(wins) / len(pnl_pcts)) * 100, 2) if pnl_pcts else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "max_loss_streak": loss_streak(trades),
    }


def loss_streak(trades: list[dict[str, object]]) -> int:
    best = 0
    current = 0
    for trade in trades:
        if float(trade["r_multiple"]) <= 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def replay_ladder(trades: list[dict[str, object]], ladder: list[float] = LADDER) -> dict[str, object]:
    pnl_pcts: list[float] = []
    risk_steps: list[float] = []
    ladder_idx = 0
    for trade in trades:
        risk_pct = ladder[min(ladder_idx, len(ladder) - 1)]
        risk_steps.append(risk_pct)
        pnl = float(trade["r_multiple"]) * risk_pct
        pnl_pcts.append(pnl)
        if pnl > 0:
            ladder_idx = 0
        else:
            ladder_idx = min(ladder_idx + 1, len(ladder) - 1)
    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p < 0]
    return {
        "mode": "ladder",
        "risk_sequence": ladder,
        "trades": len(trades),
        "net_pct": round(sum(pnl_pcts), 3),
        "avg_pct_per_trade": round(sum(pnl_pcts) / len(pnl_pcts), 4) if pnl_pcts else 0.0,
        "win_rate": round((len(wins) / len(pnl_pcts)) * 100, 2) if pnl_pcts else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "max_loss_streak": loss_streak(trades),
        "max_risk_step_used": max(risk_steps) if risk_steps else 0.0,
    }


def main() -> None:
    load_dotenv(".env")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for symbol in FOCUS_SYMBOLS:
        for exit_mode in EXIT_MODES:
            for scenario_filter in SCENARIO_FILTERS:
                trades = generate_trade_log(
                    symbol=symbol,
                    execution_granularity="M5",
                    execution_label="5m",
                    exit_mode=exit_mode,
                    scenario_filter=scenario_filter,
                )
                flat = replay_flat(trades)
                ladder = replay_ladder(trades)
                rows.append(
                    {
                        "symbol": symbol,
                        "execution_timeframe": "5m",
                        "exit_mode": exit_mode,
                        "scenario_filter": scenario_filter,
                        "trade_count": len(trades),
                        "flat_0_15": flat,
                        "ladder_notes": ladder,
                        "ladder_minus_flat_net_pct": round(ladder["net_pct"] - flat["net_pct"], 3),
                    }
                )

    out_path = OUTPUT_DIR / "ladder_matrix.json"
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
