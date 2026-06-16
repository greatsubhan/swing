"""Replay a bankroll curve for CWT since-inception signals.

This uses the existing replay signal export under reports/cwt_since_inception
and applies the current live CWT ladder per symbol.

Assumptions:
- source of truth is reports/cwt_since_inception/replay_signals.csv
- watchlist is the same as that replay bundle (`core-mixed`)
- ladder is per symbol, matching the live scanner / journal logic
- only closed signals affect realized bankroll
- open signals are reported separately and left unrealized
- risk is sized as a percentage of current equity at entry time
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = REPO_ROOT / "reports" / "cwt_since_inception" / "replay_signals.csv"
OUTPUT_DIR = REPO_ROOT / "reports" / "cwt_since_inception"
OUTPUT_CSV = OUTPUT_DIR / "bankroll_trade_log.csv"
OUTPUT_JSON = OUTPUT_DIR / "bankroll_summary.json"
OUTPUT_MD = OUTPUT_DIR / "BANKROLL_REPORT.md"

STARTING_CAPITAL = 100_000.0
LADDER = [0.07, 0.20, 0.45, 1.00]


@dataclass
class ClosedTrade:
    setup_id: str
    symbol: str
    asset_class: str
    timeframe: str
    signal_type: str
    timestamp: str
    scenario: str
    outcome: str
    realized_r: float


def _load_rows() -> list[dict[str, str]]:
    with INPUT_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _coerce_closed_trades(rows: list[dict[str, str]]) -> tuple[list[ClosedTrade], list[dict[str, str]]]:
    closed: list[ClosedTrade] = []
    open_rows: list[dict[str, str]] = []
    for row in rows:
        status = str(row.get("status") or "").strip().lower()
        if status != "closed":
            open_rows.append(row)
            continue
        realized_r_raw = str(row.get("realized_r") or "").strip()
        if not realized_r_raw:
            continue
        closed.append(
            ClosedTrade(
                setup_id=str(row["setup_id"]),
                symbol=str(row["symbol"]),
                asset_class=str(row.get("asset_class") or ""),
                timeframe=str(row.get("timeframe") or ""),
                signal_type=str(row.get("signal_type") or ""),
                timestamp=str(row["timestamp"]),
                scenario=str(row.get("scenario") or ""),
                outcome=str(row.get("outcome") or ""),
                realized_r=float(realized_r_raw),
            )
        )
    closed.sort(key=lambda trade: (trade.timestamp, trade.setup_id))
    return closed, open_rows


def replay_bankroll(closed_trades: list[ClosedTrade]) -> tuple[list[dict[str, object]], dict[str, object]]:
    equity = STARTING_CAPITAL
    peak_equity = STARTING_CAPITAL
    max_drawdown = 0.0

    ladder_index_by_symbol: dict[str, int] = defaultdict(int)
    step_use_counts: Counter[float] = Counter()
    symbol_summary: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "net_pnl": 0.0,
            "start_equity_reference": STARTING_CAPITAL,
            "max_step_used": 0.0,
        }
    )

    trade_log: list[dict[str, object]] = []
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0

    for index, trade in enumerate(closed_trades, start=1):
        ladder_index = ladder_index_by_symbol[trade.symbol]
        risk_pct = LADDER[min(ladder_index, len(LADDER) - 1)]
        risk_dollars = equity * (risk_pct / 100.0)
        pnl_dollars = risk_dollars * trade.realized_r
        equity_before = equity
        equity += pnl_dollars
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)

        won = pnl_dollars > 0
        if won:
            wins += 1
            gross_profit += pnl_dollars
            next_ladder_index = 0
        else:
            losses += 1
            gross_loss += abs(pnl_dollars)
            next_ladder_index = min(ladder_index + 1, len(LADDER) - 1)

        ladder_index_by_symbol[trade.symbol] = next_ladder_index
        step_use_counts[risk_pct] += 1

        symbol_stats = symbol_summary[trade.symbol]
        symbol_stats["trades"] = int(symbol_stats["trades"]) + 1
        symbol_stats["wins"] = int(symbol_stats["wins"]) + (1 if won else 0)
        symbol_stats["losses"] = int(symbol_stats["losses"]) + (0 if won else 1)
        symbol_stats["net_pnl"] = float(symbol_stats["net_pnl"]) + pnl_dollars
        symbol_stats["max_step_used"] = max(float(symbol_stats["max_step_used"]), risk_pct)

        trade_log.append(
            {
                "trade_number": index,
                "timestamp": trade.timestamp,
                "setup_id": trade.setup_id,
                "symbol": trade.symbol,
                "asset_class": trade.asset_class,
                "timeframe": trade.timeframe,
                "side": trade.signal_type,
                "scenario": trade.scenario,
                "outcome": trade.outcome,
                "realized_r": round(trade.realized_r, 4),
                "ladder_step_at_entry": ladder_index + 1,
                "risk_pct_at_entry": round(risk_pct, 4),
                "risk_dollars_at_entry": round(risk_dollars, 2),
                "equity_before": round(equity_before, 2),
                "pnl_dollars": round(pnl_dollars, 2),
                "equity_after": round(equity, 2),
                "next_ladder_step": next_ladder_index + 1,
                "next_risk_pct": round(LADDER[next_ladder_index], 4),
            }
        )

    summary = {
        "config": {
            "starting_capital": STARTING_CAPITAL,
            "ladder_pct": LADDER,
            "input_csv": str(INPUT_PATH),
            "sizing_rule": "risk_pct_of_current_equity",
            "ladder_scope": "per_symbol",
            "open_trade_treatment": "excluded_from_realized_bankroll",
        },
        "portfolio": {
            "closed_trades": len(closed_trades),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round((wins / len(closed_trades)) * 100.0, 2) if closed_trades else 0.0,
            "ending_equity": round(equity, 2),
            "net_pnl_dollars": round(equity - STARTING_CAPITAL, 2),
            "return_pct": round(((equity / STARTING_CAPITAL) - 1.0) * 100.0, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
            "max_drawdown_dollars": round(max_drawdown, 2),
            "max_drawdown_pct": round((max_drawdown / peak_equity) * 100.0, 2) if peak_equity else 0.0,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "step_use_counts": {f"{step:.2f}%": count for step, count in sorted(step_use_counts.items())},
        },
        "per_symbol": {
            symbol: {
                "trades": int(stats["trades"]),
                "wins": int(stats["wins"]),
                "losses": int(stats["losses"]),
                "win_rate_pct": round((int(stats["wins"]) / int(stats["trades"])) * 100.0, 2) if int(stats["trades"]) else 0.0,
                "net_pnl_dollars": round(float(stats["net_pnl"]), 2),
                "max_step_used_pct": round(float(stats["max_step_used"]), 2),
            }
            for symbol, stats in sorted(symbol_summary.items())
        },
    }
    return trade_log, summary


def _markdown_report(summary: dict[str, object], open_rows: list[dict[str, str]], trade_log: list[dict[str, object]]) -> str:
    portfolio = summary["portfolio"]
    per_symbol = summary["per_symbol"]
    top_winners = sorted(trade_log, key=lambda row: float(row["pnl_dollars"]), reverse=True)[:10]
    top_losers = sorted(trade_log, key=lambda row: float(row["pnl_dollars"]))[:10]

    lines = [
        "# CWT Since Inception Bankroll Replay",
        "",
        "## Assumptions",
        "",
        f"- Starting capital: `${summary['config']['starting_capital']:,.0f}`",
        f"- Source file: `{summary['config']['input_csv']}`",
        f"- Ladder: `{', '.join(f'{step:.2f}%' for step in summary['config']['ladder_pct'])}`",
        "- Ladder scope: `per symbol`",
        "- Position sizing: `risk % of current equity at entry time`",
        "- Only closed trades are included in realized bankroll",
        f"- Open trades excluded from realized curve: `{len(open_rows)}`",
        "",
        "## Portfolio Result",
        "",
        f"- Closed trades: `{portfolio['closed_trades']}`",
        f"- Wins / losses: `{portfolio['wins']} / {portfolio['losses']}`",
        f"- Win rate: `{portfolio['win_rate_pct']}%`",
        f"- Ending equity: `${portfolio['ending_equity']:,.2f}`",
        f"- Net PnL: `${portfolio['net_pnl_dollars']:,.2f}`",
        f"- Return: `{portfolio['return_pct']}%`",
        f"- Profit factor: `{portfolio['profit_factor']}`",
        f"- Max drawdown: `${portfolio['max_drawdown_dollars']:,.2f}` (`{portfolio['max_drawdown_pct']}%`)",
        "",
        "## Ladder Usage",
        "",
    ]
    for step_label, count in portfolio["step_use_counts"].items():
        lines.append(f"- `{step_label}` used `{count}` times")

    lines.extend(
        [
            "",
            "## By Symbol",
            "",
            "| Symbol | Trades | Win Rate | Net PnL | Max Ladder Step |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for symbol, stats in per_symbol.items():
        lines.append(
            f"| `{symbol}` | `{stats['trades']}` | `{stats['win_rate_pct']}%` | `${stats['net_pnl_dollars']:,.2f}` | `{stats['max_step_used_pct']}%` |"
        )

    lines.extend(
        [
            "",
            "## Largest Winners",
            "",
            "| Timestamp | Symbol | R | Risk % | PnL | Equity After |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in top_winners:
        lines.append(
            f"| `{row['timestamp']}` | `{row['symbol']}` | `{row['realized_r']}` | `{row['risk_pct_at_entry']}%` | `${row['pnl_dollars']:,.2f}` | `${row['equity_after']:,.2f}` |"
        )

    lines.extend(
        [
            "",
            "## Largest Losers",
            "",
            "| Timestamp | Symbol | R | Risk % | PnL | Equity After |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in top_losers:
        lines.append(
            f"| `{row['timestamp']}` | `{row['symbol']}` | `{row['realized_r']}` | `{row['risk_pct_at_entry']}%` | `${row['pnl_dollars']:,.2f}` | `${row['equity_after']:,.2f}` |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    closed_trades, open_rows = _coerce_closed_trades(rows)
    trade_log, summary = replay_bankroll(closed_trades)

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trade_log[0].keys()) if trade_log else [])
        if trade_log:
            writer.writeheader()
            writer.writerows(trade_log)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(_markdown_report(summary, open_rows, trade_log), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary_json": str(OUTPUT_JSON),
                "trade_log_csv": str(OUTPUT_CSV),
                "report_md": str(OUTPUT_MD),
                "closed_trades": len(closed_trades),
                "open_trades_excluded": len(open_rows),
                "ending_equity": summary["portfolio"]["ending_equity"],
                "return_pct": summary["portfolio"]["return_pct"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
