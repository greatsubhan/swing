"""Research-only Measured Drift v2 with controlled add-to-winner logic."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.workflows import run_backtest
from research.secular_bear_oanda_matrix import load_oanda_history
from signal_platform.env import load_dotenv

OUTPUT_DIR = Path("reports/measured_drift_v2_static_funded")
START = "2020-01-01"
END = "2026-04-01"
INITIAL_BALANCE = 100_000.0
RISK_FRACTION = 0.01
DAILY_FLOOR = 95_000.0
OVERALL_FLOOR = 90_000.0
MAX_CONCURRENT_TRADES = 2

ASSETS = [
    {"symbol": "WTICO_USD", "label": "WTI", "asset_class": "energy"},
    {"symbol": "BCO_USD", "label": "BRENT", "asset_class": "energy"},
    {"symbol": "XAG_USD", "label": "XAG", "asset_class": "metal"},
    {"symbol": "XAU_USD", "label": "XAU", "asset_class": "metal"},
    {"symbol": "UK100_GBP", "label": "UK100", "asset_class": "index"},
    {"symbol": "NAS100_USD", "label": "NAS100", "asset_class": "index"},
]


@dataclass
class AcceptedTrade:
    row: pd.Series
    risk_dollars: float
    is_add: bool


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_frame(symbol: str) -> pd.DataFrame:
    return load_oanda_history(symbol, "H4")


def _prepare_trade_log(symbol: str, asset_class: str) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    df = fetch_frame(symbol)
    _, trade_log, summary, _ = run_backtest(df, symbol=symbol, asset_class=asset_class, timeframe="4h", higher_timeframe="1d")
    if trade_log.empty:
        return df, summary, trade_log
    trade_log = trade_log.copy()
    trade_log["entry_dt"] = pd.to_datetime(trade_log["entry_time"], utc=True)
    trade_log["exit_dt"] = pd.to_datetime(trade_log["exit_time"], utc=True)
    return df, summary, trade_log.sort_values(["entry_dt", "exit_dt"]).reset_index(drop=True)


def _price_before(df: pd.DataFrame, at_dt: pd.Timestamp) -> float | None:
    prior = df[df.index < at_dt]
    if prior.empty:
        return None
    return float(prior.iloc[-1]["close"])


def _reached_one_r(trade: pd.Series, df: pd.DataFrame, cutoff_dt: pd.Timestamp) -> bool:
    window = df[(df.index >= trade["entry_dt"]) & (df.index < cutoff_dt)]
    if window.empty:
        return False
    risk = abs(float(trade["entry_price"]) - float(trade["stop_price"]))
    if risk <= 0:
        return False
    if trade["side"] == "long":
        return float(window["high"].max()) >= float(trade["entry_price"]) + risk
    return float(window["low"].min()) <= float(trade["entry_price"]) - risk


def _basket_positive(active: list[AcceptedTrade], df: pd.DataFrame, at_dt: pd.Timestamp) -> bool:
    price = _price_before(df, at_dt)
    if price is None:
        return False
    total = 0.0
    for accepted in active:
        trade = accepted.row
        risk = abs(float(trade["entry_price"]) - float(trade["stop_price"]))
        if risk <= 0:
            continue
        pnl_r = ((price - float(trade["entry_price"])) / risk) if trade["side"] == "long" else ((float(trade["entry_price"]) - price) / risk)
        total += pnl_r * accepted.risk_dollars
    return total > 0


def simulate_asset(symbol: str, asset_class: str) -> dict[str, object]:
    df, base_summary, trade_log = _prepare_trade_log(symbol, asset_class)
    if trade_log.empty:
        return {
            "symbol": symbol,
            "trades": 0,
            "adds_taken": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "profit_factor": None,
            "reward_risk_ratio": None,
            "ending_balance": INITIAL_BALANCE,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "max_drawdown_dollars": 0.0,
            "worst_daily_drawdown_dollars": 0.0,
            "failed": False,
            "fail_reason": None,
            "fail_time": None,
        }

    balance = INITIAL_BALANCE
    peak_equity = INITIAL_BALANCE
    max_drawdown = 0.0
    worst_daily_drawdown = 0.0
    failed = False
    fail_reason: str | None = None
    fail_time: str | None = None
    day_anchor: pd.Timestamp | None = None
    day_peak_equity = INITIAL_BALANCE
    active: list[AcceptedTrade] = []
    realized_rows: list[dict[str, object]] = []
    adds_taken = 0

    for _, candidate in trade_log.iterrows():
        entry_dt = candidate["entry_dt"]

        still_open: list[AcceptedTrade] = []
        for accepted in active:
            trade = accepted.row
            if trade["exit_dt"] <= entry_dt:
                exit_dt = trade["exit_dt"]
                if day_anchor is None or exit_dt.normalize() != day_anchor:
                    day_anchor = exit_dt.normalize()
                    day_peak_equity = balance

                pnl_dollars = float(trade["pnl_r"]) * accepted.risk_dollars
                balance += pnl_dollars
                peak_equity = max(peak_equity, balance)
                day_peak_equity = max(day_peak_equity, balance)
                max_drawdown = max(max_drawdown, peak_equity - balance)
                worst_daily_drawdown = max(worst_daily_drawdown, day_peak_equity - balance)
                realized_rows.append(
                    {
                        "pnl_r": float(trade["pnl_r"]),
                        "risk_dollars": round(accepted.risk_dollars, 2),
                        "pnl_dollars": round(pnl_dollars, 2),
                        "is_add": accepted.is_add,
                    }
                )
                if balance < OVERALL_FLOOR:
                    failed = True
                    fail_reason = "overall_floor"
                    fail_time = str(trade["exit_time"])
                    break
                if balance < DAILY_FLOOR:
                    failed = True
                    fail_reason = "daily_floor"
                    fail_time = str(trade["exit_time"])
                    break
            else:
                still_open.append(accepted)

        active = still_open
        if failed:
            break

        risk_budget = balance * RISK_FRACTION
        open_risk = 0.0
        same_side = True
        any_freed = False
        for accepted in active:
            trade = accepted.row
            if trade["side"] != candidate["side"]:
                same_side = False
            if _reached_one_r(trade, df, entry_dt):
                any_freed = True
            else:
                open_risk += accepted.risk_dollars

        if not active:
            risk_dollars = risk_budget
            is_add = False
        else:
            if not same_side or len(active) >= MAX_CONCURRENT_TRADES:
                continue
            if not any_freed or not _basket_positive(active, df, entry_dt):
                continue
            risk_dollars = risk_budget - open_risk
            if risk_dollars <= 0:
                continue
            is_add = True

        active.append(AcceptedTrade(row=candidate, risk_dollars=risk_dollars, is_add=is_add))
        if is_add:
            adds_taken += 1

    for accepted in active:
        trade = accepted.row
        exit_dt = trade["exit_dt"]
        if day_anchor is None or exit_dt.normalize() != day_anchor:
            day_anchor = exit_dt.normalize()
            day_peak_equity = balance
        pnl_dollars = float(trade["pnl_r"]) * accepted.risk_dollars
        balance += pnl_dollars
        peak_equity = max(peak_equity, balance)
        day_peak_equity = max(day_peak_equity, balance)
        max_drawdown = max(max_drawdown, peak_equity - balance)
        worst_daily_drawdown = max(worst_daily_drawdown, day_peak_equity - balance)
        realized_rows.append(
            {
                "pnl_r": float(trade["pnl_r"]),
                "risk_dollars": round(accepted.risk_dollars, 2),
                "pnl_dollars": round(pnl_dollars, 2),
                "is_add": accepted.is_add,
            }
        )

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
        "adds_taken": adds_taken,
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
        "base_trades": int(base_summary.trades),
        "base_avg_r": round(float(base_summary.avg_r), 3),
        "base_profit_factor": round(float(base_summary.profit_factor), 2),
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
        "period_start": START,
        "period_end_exclusive": END,
        "starting_balance": INITIAL_BALANCE,
        "risk_fraction": RISK_FRACTION,
        "daily_floor": DAILY_FLOOR,
        "overall_floor": OVERALL_FLOOR,
        "max_concurrent_trades": MAX_CONCURRENT_TRADES,
        "rule_note": "One controlled add allowed only when an active trade has reached +1R and open basket risk stays within 1% of balance.",
        "assets": rows,
    }
    output_path = OUTPUT_DIR / "static_funded_v2_results.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
