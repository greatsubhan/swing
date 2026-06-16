"""Research-only Measured Drift variant with breakeven at +1R and no adds."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.measured_drift_static_funded import (
    ASSETS,
    DAILY_FLOOR,
    INITIAL_BALANCE,
    OUTPUT_DIR as BASE_OUTPUT_DIR,
    OVERALL_FLOOR,
    RISK_FRACTION,
)
from research.secular_bear_oanda_matrix import load_oanda_history
from little_rzy_bot.workflows import run_backtest
from signal_platform.env import load_dotenv

OUTPUT_DIR = Path("reports/measured_drift_breakeven_static_funded")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def non_overlapping_trades(trade_log: pd.DataFrame) -> pd.DataFrame:
    if trade_log.empty:
        return trade_log
    ordered = trade_log.copy()
    ordered["entry_dt"] = pd.to_datetime(ordered["entry_time"], utc=True)
    ordered["exit_dt"] = pd.to_datetime(ordered["exit_time"], utc=True)
    ordered = ordered.sort_values(["entry_dt", "exit_dt"]).reset_index(drop=True)
    kept_rows = []
    current_exit: pd.Timestamp | None = None
    for _, row in ordered.iterrows():
        if current_exit is None or row["entry_dt"] >= current_exit:
            kept_rows.append(row)
            current_exit = row["exit_dt"]
    return pd.DataFrame(kept_rows)


def adjusted_trade_r(df: pd.DataFrame, trade: pd.Series) -> tuple[float, str]:
    entry_dt = pd.to_datetime(trade["entry_time"], utc=True)
    exit_dt = pd.to_datetime(trade["exit_time"], utc=True)
    window = df[(df.index >= entry_dt) & (df.index <= exit_dt)]
    if window.empty:
        return float(trade["pnl_r"]), str(trade["exit_reason"])

    side = str(trade["side"])
    entry = float(trade["entry_price"])
    stop = float(trade["stop_price"])
    target = float(trade["target_price"])
    risk = abs(entry - stop)
    if risk <= 0:
        return float(trade["pnl_r"]), str(trade["exit_reason"])

    breakeven_active = False
    rows = list(window.iterrows())
    for offset, (_, row) in enumerate(rows):
        high = float(row["high"])
        low = float(row["low"])

        if side == "long":
            target_hit = high >= target
            stop_hit = low <= stop
            be_trigger = high >= entry + risk
            be_hit = breakeven_active and low <= entry
        else:
            target_hit = low <= target
            stop_hit = high >= stop
            be_trigger = low <= entry - risk
            be_hit = breakeven_active and high >= entry

        if stop_hit:
            return -1.0, "stop"
        if target_hit:
            pnl_r = ((target - entry) / risk) if side == "long" else ((entry - target) / risk)
            return float(pnl_r), "target"
        if be_hit:
            return 0.0, "breakeven"

        # Activate breakeven from the next bar after +1R is seen.
        if be_trigger and offset < len(rows) - 1:
            breakeven_active = True

    return float(trade["pnl_r"]), str(trade["exit_reason"])


def simulate_asset(symbol: str, asset_class: str) -> dict[str, object]:
    df = load_oanda_history(symbol, "H4")
    _, trade_log, _, _ = run_backtest(df, symbol=symbol, asset_class=asset_class, timeframe="4h", higher_timeframe="1d")
    trade_log = non_overlapping_trades(trade_log)

    balance = INITIAL_BALANCE
    peak_equity = INITIAL_BALANCE
    max_drawdown = 0.0
    worst_daily_drawdown = 0.0
    failed = False
    fail_reason: str | None = None
    fail_time: str | None = None
    day_anchor: pd.Timestamp | None = None
    day_peak_equity = INITIAL_BALANCE

    realized_rows: list[dict[str, object]] = []
    breakeven_exits = 0
    for _, trade in trade_log.iterrows():
        exit_dt = pd.to_datetime(trade["exit_time"], utc=True)
        if day_anchor is None or exit_dt.normalize() != day_anchor:
            day_anchor = exit_dt.normalize()
            day_peak_equity = balance

        pnl_r, exit_reason = adjusted_trade_r(df, trade)
        risk_dollars = balance * RISK_FRACTION
        pnl_dollars = pnl_r * risk_dollars
        balance += pnl_dollars
        peak_equity = max(peak_equity, balance)
        day_peak_equity = max(day_peak_equity, balance)
        max_drawdown = max(max_drawdown, peak_equity - balance)
        worst_daily_drawdown = max(worst_daily_drawdown, day_peak_equity - balance)
        if exit_reason == "breakeven":
            breakeven_exits += 1
        realized_rows.append(
            {
                "pnl_r": round(pnl_r, 4),
                "risk_dollars": round(risk_dollars, 2),
                "pnl_dollars": round(pnl_dollars, 2),
                "exit_reason": exit_reason,
            }
        )

        if balance < OVERALL_FLOOR:
            failed = True
            fail_reason = "overall_floor"
            fail_time = trade["exit_time"]
            break
        if balance < DAILY_FLOOR:
            failed = True
            fail_reason = "daily_floor"
            fail_time = trade["exit_time"]
            break

    wins = [row for row in realized_rows if row["pnl_dollars"] > 0]
    losses = [row for row in realized_rows if row["pnl_dollars"] < 0]
    win_rs = [row["pnl_r"] for row in realized_rows if row["pnl_r"] > 0]
    loss_rs = [row["pnl_r"] for row in realized_rows if row["pnl_r"] < 0]
    total_r = sum(row["pnl_r"] for row in realized_rows)
    avg_r = total_r / len(realized_rows) if realized_rows else 0.0
    avg_win_r = sum(win_rs) / len(win_rs) if win_rs else 0.0
    avg_loss_r = sum(loss_rs) / len(loss_rs) if loss_rs else 0.0
    reward_risk_ratio = avg_win_r / abs(avg_loss_r) if avg_loss_r else None
    profit_factor = (
        sum(row["pnl_dollars"] for row in wins) / abs(sum(row["pnl_dollars"] for row in losses))
        if losses
        else None
    )

    return {
        "symbol": symbol,
        "trades": len(realized_rows),
        "breakeven_exits": breakeven_exits,
        "win_rate": round((len(wins) / len(realized_rows)) * 100, 2) if realized_rows else 0.0,
        "avg_r": round(avg_r, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "reward_risk_ratio": round(reward_risk_ratio, 3) if reward_risk_ratio is not None else None,
        "ending_balance": round(balance, 2),
        "net_pnl": round(balance - INITIAL_BALANCE, 2),
        "return_pct": round(((balance / INITIAL_BALANCE) - 1) * 100, 2),
        "max_drawdown_dollars": round(max_drawdown, 2),
        "worst_daily_drawdown_dollars": round(worst_daily_drawdown, 2),
        "failed": failed,
        "fail_reason": fail_reason,
        "fail_time": fail_time,
    }


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)

    rows = []
    for asset in ASSETS:
        result = simulate_asset(asset["symbol"], asset["asset_class"])
        result["label"] = asset["label"]
        rows.append(result)

    output = {
        "period_start": "2020-01-01",
        "period_end_exclusive": "2026-04-01",
        "starting_balance": INITIAL_BALANCE,
        "risk_fraction": RISK_FRACTION,
        "daily_floor": DAILY_FLOOR,
        "overall_floor": OVERALL_FLOOR,
        "rule_note": "Move stop to breakeven after +1R is reached; no adds.",
        "assets": rows,
    }
    output_path = OUTPUT_DIR / "static_funded_breakeven_results.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
