"""Static-floor funded-account simulation for Measured Drift."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from little_rzy_bot.market_data import fetch_oanda_ohlcv
from little_rzy_bot.workflows import run_backtest
from signal_platform.env import load_dotenv

OUTPUT_DIR = Path("reports/measured_drift_static_funded")
START = "2020-01-01"
END = "2026-04-01"
INITIAL_BALANCE = 100_000.0
RISK_FRACTION = 0.01
DAILY_FLOOR = 95_000.0
OVERALL_FLOOR = 90_000.0

ASSETS = [
    {"symbol": "WTICO_USD", "label": "WTI", "asset_class": "energy"},
    {"symbol": "BCO_USD", "label": "BRENT", "asset_class": "energy"},
    {"symbol": "XAG_USD", "label": "XAG", "asset_class": "metal"},
    {"symbol": "XAU_USD", "label": "XAU", "asset_class": "metal"},
    {"symbol": "UK100_GBP", "label": "UK100", "asset_class": "index"},
    {"symbol": "NAS100_USD", "label": "NAS100", "asset_class": "index"},
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_frame(symbol: str) -> pd.DataFrame:
    return fetch_oanda_ohlcv(symbol, "H4", start=START, end=END, environment="practice").df


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


def simulate_asset(symbol: str, asset_class: str) -> dict[str, object]:
    df = fetch_frame(symbol)
    _, trade_log, summary, _ = run_backtest(df, symbol=symbol, asset_class=asset_class, timeframe="4h", higher_timeframe="1d")
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
    for _, trade in trade_log.iterrows():
        exit_dt = pd.to_datetime(trade["exit_time"], utc=True)
        if day_anchor is None or exit_dt.normalize() != day_anchor:
            day_anchor = exit_dt.normalize()
            day_peak_equity = balance

        risk_dollars = balance * RISK_FRACTION
        pnl_dollars = float(trade["pnl_r"]) * risk_dollars
        balance += pnl_dollars
        peak_equity = max(peak_equity, balance)
        day_peak_equity = max(day_peak_equity, balance)
        max_drawdown = max(max_drawdown, peak_equity - balance)
        worst_daily_drawdown = max(worst_daily_drawdown, day_peak_equity - balance)

        realized_rows.append(
            {
                "exit_time": trade["exit_time"],
                "pnl_r": float(trade["pnl_r"]),
                "risk_dollars": round(risk_dollars, 2),
                "pnl_dollars": round(pnl_dollars, 2),
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
    win_rs = [float(r) for r in trade_log["pnl_r"] if float(r) > 0]
    loss_rs = [float(r) for r in trade_log["pnl_r"] if float(r) < 0]
    avg_win_r = sum(win_rs) / len(win_rs) if win_rs else 0.0
    avg_loss_r = sum(loss_rs) / len(loss_rs) if loss_rs else 0.0
    reward_risk_ratio = avg_win_r / abs(avg_loss_r) if avg_loss_r else None

    return {
        "symbol": symbol,
        "trades": int(len(trade_log)),
        "win_rate": round(float((trade_log["pnl_r"] > 0).mean() * 100), 2) if not trade_log.empty else 0.0,
        "avg_r": round(float(trade_log["pnl_r"].mean()), 3) if not trade_log.empty else 0.0,
        "profit_factor": round(float(summary.profit_factor), 2) if trade_log is not None else None,
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
        "period_start": START,
        "period_end_exclusive": END,
        "starting_balance": INITIAL_BALANCE,
        "risk_fraction": RISK_FRACTION,
        "daily_floor": DAILY_FLOOR,
        "overall_floor": OVERALL_FLOOR,
        "assets": rows,
    }
    output_path = OUTPUT_DIR / "static_funded_results.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
