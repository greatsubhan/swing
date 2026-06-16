"""Funded-style CWT simulation with ladder and daily guardrails.

Current lead configuration:

- H1 bias
- M5 execution
- Scenario 1 + Scenario 2
- Fixed 1R exit
- Risk ladder: 0.15 / 0.30 / 0.60 / 1.20
- Per-asset daily planned risk cap: 1.00% of starting balance
- Portfolio daily planned risk cap: 5.00% of starting balance

Interpretation used here:

- ladder percentages are based on starting balance, not floating equity
- if the next ladder step would breach the asset/day or portfolio/day cap,
  that trade is skipped rather than clipped
- the extra equity-protection brake halts new risk if account equity drops
  below 95% of starting balance
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signal_platform.env import load_dotenv
from research.cwt_risk_ladder_matrix import generate_trade_log

OUTPUT_DIR = Path("reports/cwt_forex")
STARTING_BALANCE = 100_000.0
ASSET_DAILY_CAP_DOLLARS = 1_000.0
PORTFOLIO_DAILY_CAP_DOLLARS = 5_000.0
OVERALL_BRAKE_EQUITY = 95_000.0
LADDER = [0.15, 0.30, 0.60, 1.20]
FOCUS_SYMBOLS = ["USD_JPY", "EUR_USD", "NZD_USD", "USD_CAD"]
EXIT_MODE = "rr1"
SCENARIO_FILTER = "both"


def risk_pct_to_dollars(risk_pct: float) -> float:
    return STARTING_BALANCE * (risk_pct / 100.0)


def replay_portfolio() -> dict[str, object]:
    raw_trades: list[dict[str, object]] = []
    for symbol in FOCUS_SYMBOLS:
        trades = generate_trade_log(
            symbol=symbol,
            execution_granularity="M5",
            execution_label="5m",
            exit_mode=EXIT_MODE,
            scenario_filter=SCENARIO_FILTER,
        )
        for trade in trades:
            trade = dict(trade)
            trade["entry_ts"] = trade["entry_time"]
            raw_trades.append(trade)

    raw_trades.sort(key=lambda trade: trade["entry_ts"])

    equity = STARTING_BALANCE
    peak_equity = STARTING_BALANCE
    max_drawdown = 0.0
    processed = 0
    skipped_daily_asset = 0
    skipped_daily_portfolio = 0
    skipped_overall_brake = 0
    ladder_resets = 0
    ladder_advances = 0
    risk_step_counts: dict[float, int] = defaultdict(int)

    daily_asset_risk: dict[str, float] = defaultdict(float)
    daily_portfolio_risk = 0.0
    ladder_index_by_symbol: dict[str, int] = defaultdict(int)
    trade_results: list[dict[str, object]] = []
    current_day: str | None = None

    per_symbol = {
        symbol: {
            "taken": 0,
            "skipped_asset_cap": 0,
            "skipped_portfolio_cap": 0,
            "skipped_overall_brake": 0,
            "net_pnl_dollars": 0.0,
            "net_pct": 0.0,
            "wins": 0,
            "losses": 0,
        }
        for symbol in FOCUS_SYMBOLS
    }

    for trade in raw_trades:
        entry_time = str(trade["entry_time"])
        day = entry_time[:10]
        symbol = str(trade["symbol"])

        if current_day != day:
            current_day = day
            daily_asset_risk = defaultdict(float)
            daily_portfolio_risk = 0.0

        step_idx = ladder_index_by_symbol[symbol]
        risk_pct = LADDER[min(step_idx, len(LADDER) - 1)]
        risk_dollars = risk_pct_to_dollars(risk_pct)

        if equity < OVERALL_BRAKE_EQUITY:
            skipped_overall_brake += 1
            per_symbol[symbol]["skipped_overall_brake"] += 1
            continue
        if daily_asset_risk[symbol] + risk_dollars > ASSET_DAILY_CAP_DOLLARS:
            skipped_daily_asset += 1
            per_symbol[symbol]["skipped_asset_cap"] += 1
            continue
        if daily_portfolio_risk + risk_dollars > PORTFOLIO_DAILY_CAP_DOLLARS:
            skipped_daily_portfolio += 1
            per_symbol[symbol]["skipped_portfolio_cap"] += 1
            continue

        daily_asset_risk[symbol] += risk_dollars
        daily_portfolio_risk += risk_dollars
        risk_step_counts[risk_pct] += 1

        r_multiple = float(trade["r_multiple"])
        pnl_dollars = risk_dollars * r_multiple
        equity += pnl_dollars
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)
        processed += 1
        per_symbol[symbol]["taken"] += 1
        per_symbol[symbol]["net_pnl_dollars"] += pnl_dollars
        per_symbol[symbol]["net_pct"] += (pnl_dollars / STARTING_BALANCE) * 100.0
        if pnl_dollars > 0:
            per_symbol[symbol]["wins"] += 1
            ladder_index_by_symbol[symbol] = 0
            ladder_resets += 1
        else:
            per_symbol[symbol]["losses"] += 1
            ladder_index_by_symbol[symbol] = min(step_idx + 1, len(LADDER) - 1)
            ladder_advances += 1

        trade_results.append(
            {
                "symbol": symbol,
                "entry_time": trade["entry_time"],
                "exit_time": trade["exit_time"],
                "reason": trade["reason"],
                "scenario": trade["scenario"],
                "risk_pct": risk_pct,
                "risk_dollars": round(risk_dollars, 2),
                "r_multiple": round(r_multiple, 4),
                "pnl_dollars": round(pnl_dollars, 2),
                "equity_after": round(equity, 2),
            }
        )

    wins = [row for row in trade_results if row["pnl_dollars"] > 0]
    losses = [row for row in trade_results if row["pnl_dollars"] < 0]
    return {
        "config": {
            "starting_balance": STARTING_BALANCE,
            "symbols": FOCUS_SYMBOLS,
            "execution_timeframe": "5m",
            "exit_mode": EXIT_MODE,
            "scenario_filter": SCENARIO_FILTER,
            "risk_ladder_pct": LADDER,
            "per_asset_daily_cap_dollars": ASSET_DAILY_CAP_DOLLARS,
            "portfolio_daily_cap_dollars": PORTFOLIO_DAILY_CAP_DOLLARS,
            "overall_brake_equity": OVERALL_BRAKE_EQUITY,
        },
        "portfolio_summary": {
            "ending_balance": round(equity, 2),
            "net_pnl_dollars": round(equity - STARTING_BALANCE, 2),
            "return_pct": round(((equity / STARTING_BALANCE) - 1) * 100, 2),
            "trades_taken": processed,
            "trades_skipped_asset_cap": skipped_daily_asset,
            "trades_skipped_portfolio_cap": skipped_daily_portfolio,
            "trades_skipped_overall_brake": skipped_overall_brake,
            "win_rate": round((len(wins) / processed) * 100, 2) if processed else 0.0,
            "profit_factor": round(
                sum(row["pnl_dollars"] for row in wins) / abs(sum(row["pnl_dollars"] for row in losses)),
                2,
            )
            if losses
            else None,
            "max_drawdown_dollars": round(max_drawdown, 2),
            "ladder_resets": ladder_resets,
            "ladder_advances": ladder_advances,
            "risk_step_counts": {str(step): count for step, count in sorted(risk_step_counts.items())},
        },
        "per_symbol_summary": {
            symbol: {
                **stats,
                "net_pnl_dollars": round(stats["net_pnl_dollars"], 2),
                "net_pct": round(stats["net_pct"], 2),
                "win_rate": round((stats["wins"] / stats["taken"]) * 100, 2) if stats["taken"] else 0.0,
            }
            for symbol, stats in per_symbol.items()
        },
        "sample_trades": trade_results[:40],
    }


def main() -> None:
    load_dotenv(".env")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = replay_portfolio()
    out_path = OUTPUT_DIR / "funded_ladder_sim.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
