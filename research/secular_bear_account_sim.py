"""Funded-account simulation for the secular-bear pullback strategy."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.secular_bear_oanda_matrix import ASSETS, load_oanda_history, pullback_signal, regime_bearish, with_indicators
from signal_platform.env import load_dotenv

OUTPUT_DIR = Path("reports/secular_bear_account")
INITIAL_BALANCE = 100_000.0
DEFAULT_RISK_FRACTION = 0.01
MAX_DRAWDOWN_DOLLARS = 10_000.0
DAILY_DRAWDOWN_DOLLARS = 5_000.0
COOLDOWN = pd.Timedelta(hours=1)


@dataclass
class Tranche:
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    units: float
    risk_dollars: float
    bars_held: int = 0

    @property
    def risk_per_unit(self) -> float:
        return self.stop_price - self.entry_price


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def mark_to_market(tranche: Tranche, price: float) -> float:
    return tranche.units * (tranche.entry_price - price)


def close_tranches(
    tranches: list[Tranche], exit_time: pd.Timestamp, exit_price: float, reason: str
) -> tuple[float, list[dict[str, object]]]:
    realized = 0.0
    records: list[dict[str, object]] = []
    for tranche in tranches:
        pnl = tranche.units * (tranche.entry_price - exit_price)
        realized += pnl
        records.append(
            {
                "entry_time": tranche.entry_time.isoformat(),
                "exit_time": exit_time.isoformat(),
                "entry_price": round(tranche.entry_price, 6),
                "exit_price": round(exit_price, 6),
                "risk_dollars": round(tranche.risk_dollars, 2),
                "pnl_dollars": round(pnl, 2),
                "r_multiple": round(pnl / tranche.risk_dollars, 3) if tranche.risk_dollars else 0.0,
                "bars_held": tranche.bars_held,
                "reason": reason,
            }
        )
    return realized, records


def simulate(
    symbol: str,
    execution_interval: str,
    regime: str = "alligator",
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    kill_on_limits: bool = True,
) -> dict[str, object]:
    if execution_interval == "1d":
        execution = with_indicators(load_oanda_history(symbol, "D"))
        trend_view = execution
    else:
        execution = with_indicators(load_oanda_history(symbol, "H4"))
        trend_view = with_indicators(load_oanda_history(symbol, "D"))

    balance = INITIAL_BALANCE
    peak_equity = INITIAL_BALANCE
    max_drawdown = 0.0
    tranches: list[Tranche] = []
    trade_log: list[dict[str, object]] = []
    last_stop_time: pd.Timestamp | None = None
    failed = False
    fail_reason: str | None = None
    fail_time: str | None = None
    day_anchor: pd.Timestamp | None = None
    day_start_equity = INITIAL_BALANCE
    worst_daily_drawdown = 0.0

    for idx in range(220, len(execution) - 1):
        bar = execution.iloc[idx]
        bar_time = execution.index[idx]
        current_day = bar_time.normalize()
        if day_anchor is None or current_day != day_anchor:
            day_anchor = current_day
            open_equity = balance + sum(mark_to_market(tranche, float(bar["close"])) for tranche in tranches)
            day_start_equity = open_equity

        if execution_interval == "4h":
            daily_slice = trend_view[trend_view.index <= bar_time]
            if len(daily_slice) < 220:
                continue
            trend_ok = regime_bearish(daily_slice, regime, len(daily_slice) - 1)
            trend_break = not trend_ok
        else:
            trend_ok = regime_bearish(execution, regime, idx)
            trend_break = not trend_ok

        for tranche in tranches:
            tranche.bars_held += 1

        stop_triggered = any(float(bar["high"]) >= tranche.stop_price for tranche in tranches)
        if tranches and (stop_triggered or trend_break):
            reason = "stop" if stop_triggered else "trend_break"
            exit_price = float(bar["close"])
            realized, records = close_tranches(tranches, bar_time, exit_price, reason)
            balance += realized
            trade_log.extend(records)
            tranches = []
            if reason == "stop":
                last_stop_time = bar_time

        equity = balance + sum(mark_to_market(tranche, float(bar["close"])) for tranche in tranches)
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)
        worst_daily_drawdown = max(worst_daily_drawdown, day_start_equity - equity)

        if kill_on_limits:
            if peak_equity - equity > MAX_DRAWDOWN_DOLLARS:
                failed = True
                fail_reason = "max_drawdown"
                fail_time = bar_time.isoformat()
            elif day_start_equity - equity > DAILY_DRAWDOWN_DOLLARS:
                failed = True
                fail_reason = "daily_drawdown"
                fail_time = bar_time.isoformat()

        if failed and kill_on_limits:
            if tranches:
                realized, records = close_tranches(tranches, bar_time, float(bar["close"]), fail_reason or "failure")
                balance += realized
                trade_log.extend(records)
                tranches = []
            break

        if last_stop_time is not None and (bar_time - last_stop_time) < COOLDOWN:
            continue

        basket_positive = not tranches or sum(mark_to_market(tranche, float(bar["close"])) for tranche in tranches) > 0
        signal = pullback_signal(execution, regime, idx) if trend_ok else None
        if signal and basket_positive:
            next_bar = execution.iloc[idx + 1]
            entry_price = float(next_bar["open"])
            stop_price = float(signal["swing_high"] + signal["atr"])
            risk_per_unit = stop_price - entry_price
            if risk_per_unit > 0:
                risk_dollars = balance * risk_fraction
                units = risk_dollars / risk_per_unit
                tranches.append(
                    Tranche(
                        entry_time=execution.index[idx + 1],
                        entry_price=entry_price,
                        stop_price=stop_price,
                        units=units,
                        risk_dollars=risk_dollars,
                    )
                )

    if tranches and not failed:
        exit_price = float(execution.iloc[-1]["close"])
        exit_time = execution.index[-1]
        realized, records = close_tranches(tranches, exit_time, exit_price, "final_bar")
        balance += realized
        trade_log.extend(records)
        tranches = []

    wins = [trade for trade in trade_log if trade["pnl_dollars"] > 0]
    losses = [trade for trade in trade_log if trade["pnl_dollars"] < 0]
    win_rs = [trade["r_multiple"] for trade in trade_log if trade["r_multiple"] > 0]
    loss_rs = [trade["r_multiple"] for trade in trade_log if trade["r_multiple"] < 0]
    avg_hold = sum(trade["bars_held"] for trade in trade_log) / len(trade_log) if trade_log else 0.0
    total_r = sum(trade["r_multiple"] for trade in trade_log)
    avg_r = total_r / len(trade_log) if trade_log else 0.0
    avg_win_r = sum(win_rs) / len(win_rs) if win_rs else 0.0
    avg_loss_r = sum(loss_rs) / len(loss_rs) if loss_rs else 0.0
    reward_risk_ratio = (avg_win_r / abs(avg_loss_r)) if avg_loss_r else None
    return {
        "symbol": symbol,
        "execution_interval": execution_interval,
        "regime_filter": regime,
        "risk_fraction": risk_fraction,
        "kill_on_limits": kill_on_limits,
        "starting_balance": INITIAL_BALANCE,
        "ending_balance": round(balance, 2),
        "net_pnl": round(balance - INITIAL_BALANCE, 2),
        "return_pct": round(((balance / INITIAL_BALANCE) - 1) * 100, 2),
        "closed_tranches": len(trade_log),
        "win_rate": round((len(wins) / len(trade_log)) * 100, 2) if trade_log else 0.0,
        "total_r": round(total_r, 3),
        "avg_r": round(avg_r, 3),
        "profit_factor": round(
            sum(t["pnl_dollars"] for t in wins) / abs(sum(t["pnl_dollars"] for t in losses)), 2
        )
        if losses
        else None,
        "avg_win_r": round(avg_win_r, 3),
        "avg_loss_r": round(avg_loss_r, 3),
        "reward_risk_ratio": round(reward_risk_ratio, 3) if reward_risk_ratio is not None else None,
        "avg_win_dollars": round(sum(t["pnl_dollars"] for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_dollars": round(sum(t["pnl_dollars"] for t in losses) / len(losses), 2) if losses else 0.0,
        "max_drawdown_dollars": round(max_drawdown, 2),
        "max_drawdown_pct": round((max_drawdown / INITIAL_BALANCE) * 100, 2),
        "worst_daily_drawdown_dollars": round(worst_daily_drawdown, 2),
        "within_overall_limit": max_drawdown <= MAX_DRAWDOWN_DOLLARS,
        "within_daily_limit": worst_daily_drawdown <= DAILY_DRAWDOWN_DOLLARS,
        "failed": failed,
        "fail_reason": fail_reason,
        "fail_time": fail_time,
        "avg_bars_held": round(avg_hold, 2),
        "avg_hold_hours": round(avg_hold * (24 if execution_interval == "1d" else 4), 2),
    }


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)

    results: list[dict[str, object]] = []
    for asset in ASSETS:
        symbol = asset["symbol"]
        for interval in ("4h", "1d"):
            result = simulate(symbol, interval)
            result["category"] = asset["category"]
            results.append(result)

    output_path = OUTPUT_DIR / "funded_account_alligator.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
