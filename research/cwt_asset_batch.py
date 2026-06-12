"""Batch CWT funded-style backtest grouped by asset type.

This expands the locked CWT benchmark across the configured market universe and
reports per-symbol metrics for bot keep/skip decisions.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signal_platform.env import load_dotenv
from research.cwt_risk_ladder_matrix import generate_trade_log

CONFIG_PATH = Path("config/cwt_market_constraints.json")
OUTPUT_DIR = Path("reports/cwt_forex")
REPORT_START = "2023-01-01"
REPORT_END = "2026-04-01"
REPORT_TAG = "3y"
OUTPUT_JSON = OUTPUT_DIR / f"asset_batch_report_{REPORT_TAG}.json"
OUTPUT_MD = OUTPUT_DIR / f"ASSET_BATCH_REPORT_{REPORT_TAG}.md"

STARTING_BALANCE = 100_000.0
ASSET_DAILY_CAP_DOLLARS = 1_000.0
PORTFOLIO_DAILY_CAP_DOLLARS = 5_000.0
OVERALL_BRAKE_EQUITY = 95_000.0
LADDER = [0.07, 0.20, 0.45, 1.00]
EXIT_MODE = "rr1"
SCENARIO_FILTER = "both"
GROUP_ORDER = ["major_fx", "minor_cross_fx", "indices", "commodities"]

INDEX_CANONICAL = {
    "US500": "SPX500_USD",
    "SPX": "SPX500_USD",
    "SPX500_USD": "SPX500_USD",
    "US30": "US30_USD",
    "DJIA": "US30_USD",
    "US30_USD": "US30_USD",
    "US100": "NAS100_USD",
    "NDX": "NAS100_USD",
    "USTEC": "NAS100_USD",
    "NAS100_USD": "NAS100_USD",
    "UK100": "UK100_GBP",
    "FTSE": "UK100_GBP",
    "UK100_GBP": "UK100_GBP",
    "FR40": "FR40_EUR",
    "CAC": "FR40_EUR",
    "FR40_EUR": "FR40_EUR",
    "JP225": "JP225_USD",
    "NI225": "JP225_USD",
    "JP225_USD": "JP225_USD",
}

COMMODITY_CANONICAL = {
    "USOIL": "WTICO_USD",
    "WTICO_USD": "WTICO_USD",
    "UKOIL": "BCO_USD",
    "BCO_USD": "BCO_USD",
    "XAU_USD": "XAU_USD",
    "XAG_USD": "XAG_USD",
    "NATGAS": "NATGAS",
    "COPPER": "COPPER",
    "PLATINUM": "PLATINUM",
    "PALLADIUM": "PALLADIUM",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def risk_pct_to_dollars(risk_pct: float) -> float:
    return STARTING_BALANCE * (risk_pct / 100.0)


def canonical_symbol(group_id: str, symbol: str) -> str:
    if group_id == "indices":
        return INDEX_CANONICAL.get(symbol, symbol)
    if group_id == "commodities":
        return COMMODITY_CANONICAL.get(symbol, symbol)
    return symbol


def load_batches() -> dict[str, list[dict[str, str]]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    batches: dict[str, list[dict[str, str]]] = {}
    for group in config["groups"]:
        group_id = group["group_id"]
        if group_id not in GROUP_ORDER:
            continue
        seen: set[str] = set()
        entries: list[dict[str, str]] = []
        for raw_symbol in group["symbols"]:
            symbol = canonical_symbol(group_id, raw_symbol)
            if symbol in seen:
                continue
            seen.add(symbol)
            entries.append(
                {
                    "symbol": symbol,
                    "minimum_timeframe": group["minimum_timeframe"],
                }
            )
        batches[group_id] = entries
    return batches


def max_streak(values: list[float], positive: bool) -> int:
    best = 0
    current = 0
    for value in values:
        hit = value > 0 if positive else value <= 0
        if hit:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


def replay_symbol(symbol: str, minimum_timeframe: str) -> dict[str, object]:
    execution_granularity = "M5" if minimum_timeframe == "5m" else "M15"
    trades = generate_trade_log(
        symbol=symbol,
        execution_granularity=execution_granularity,
        execution_label=minimum_timeframe,
        exit_mode=EXIT_MODE,
        scenario_filter=SCENARIO_FILTER,
        start=REPORT_START,
        end=REPORT_END,
    )

    equity = STARTING_BALANCE
    peak_equity = STARTING_BALANCE
    max_drawdown = 0.0
    current_day: str | None = None
    daily_asset_risk = 0.0
    daily_portfolio_risk = 0.0
    ladder_index = 0
    ladder_resets = 0
    ladder_advances = 0
    risk_step_counts: Counter[float] = Counter()

    skipped_asset_cap = 0
    skipped_portfolio_cap = 0
    skipped_overall_brake = 0

    processed_trades: list[dict[str, object]] = []
    pnl_dollars_series: list[float] = []
    r_series: list[float] = []
    hold_bars: list[int] = []
    scenario_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for trade in trades:
        day = str(trade["entry_time"])[:10]
        if current_day != day:
            current_day = day
            daily_asset_risk = 0.0
            daily_portfolio_risk = 0.0

        risk_pct = LADDER[min(ladder_index, len(LADDER) - 1)]
        risk_dollars = risk_pct_to_dollars(risk_pct)

        if equity < OVERALL_BRAKE_EQUITY:
            skipped_overall_brake += 1
            continue
        if daily_asset_risk + risk_dollars > ASSET_DAILY_CAP_DOLLARS:
            skipped_asset_cap += 1
            continue
        if daily_portfolio_risk + risk_dollars > PORTFOLIO_DAILY_CAP_DOLLARS:
            skipped_portfolio_cap += 1
            continue

        daily_asset_risk += risk_dollars
        daily_portfolio_risk += risk_dollars
        risk_step_counts[risk_pct] += 1

        r_multiple = float(trade["r_multiple"])
        pnl_dollars = risk_dollars * r_multiple
        equity += pnl_dollars
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)

        pnl_dollars_series.append(pnl_dollars)
        r_series.append(r_multiple)
        hold_bars.append(int(trade.get("bars_held", 0)))
        scenario_counts[str(trade.get("scenario", "unknown"))] += 1
        reason_counts[str(trade.get("reason", "unknown"))] += 1

        if pnl_dollars > 0:
            ladder_index = 0
            ladder_resets += 1
        else:
            ladder_index = min(ladder_index + 1, len(LADDER) - 1)
            ladder_advances += 1

        processed_trades.append(
            {
                "entry_time": trade["entry_time"],
                "exit_time": trade["exit_time"],
                "risk_pct": risk_pct,
                "risk_dollars": risk_dollars,
                "r_multiple": r_multiple,
                "pnl_dollars": pnl_dollars,
                "equity_after": equity,
            }
        )

    wins = [value for value in pnl_dollars_series if value > 0]
    losses = [value for value in pnl_dollars_series if value < 0]
    winner_rs = [value for value in r_series if value > 0]
    loser_rs = [value for value in r_series if value <= 0]

    return {
        "symbol": symbol,
        "minimum_timeframe": minimum_timeframe,
        "execution_timeframe": minimum_timeframe,
        "date_range": {"start": REPORT_START, "end": REPORT_END},
        "trades_taken": len(processed_trades),
        "trades_generated": len(trades),
        "trades_skipped_asset_cap": skipped_asset_cap,
        "trades_skipped_portfolio_cap": skipped_portfolio_cap,
        "trades_skipped_overall_brake": skipped_overall_brake,
        "ending_balance": round_or_none(equity),
        "net_pnl_dollars": round_or_none(equity - STARTING_BALANCE),
        "return_pct": round_or_none(((equity / STARTING_BALANCE) - 1) * 100),
        "win_rate": round_or_none((len(wins) / len(processed_trades)) * 100 if processed_trades else 0.0),
        "profit_factor": round_or_none(sum(wins) / abs(sum(losses)) if losses else None),
        "avg_r": round_or_none(sum(r_series) / len(r_series) if r_series else 0.0, 3),
        "total_r": round_or_none(sum(r_series), 3),
        "reward_risk_ratio": round_or_none(
            (sum(winner_rs) / len(winner_rs)) / abs(sum(loser_rs) / len(loser_rs))
            if winner_rs and loser_rs
            else None,
            3,
        ),
        "avg_trade_pnl_dollars": round_or_none(sum(pnl_dollars_series) / len(pnl_dollars_series) if pnl_dollars_series else 0.0),
        "max_drawdown_dollars": round_or_none(max_drawdown),
        "max_winning_streak": max_streak(pnl_dollars_series, positive=True),
        "max_losing_streak": max_streak(pnl_dollars_series, positive=False),
        "avg_bars_held": round_or_none(sum(hold_bars) / len(hold_bars) if hold_bars else 0.0),
        "scenario1_trades": int(scenario_counts.get("scenario1", 0)),
        "scenario2_trades": int(scenario_counts.get("scenario2", 0)),
        "target_exits": int(reason_counts.get("target", 0)),
        "stop_exits": int(reason_counts.get("stop", 0)),
        "bias_flip_exits": int(reason_counts.get("bias_flip", 0)),
        "timeout_exits": int(reason_counts.get("timeout", 0)),
        "final_bar_exits": int(reason_counts.get("final_bar", 0)),
        "risk_step_counts": {f"{step:.2f}": int(risk_step_counts.get(step, 0)) for step in LADDER},
    }


def group_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    kept = [row for row in rows if keep_bucket(row) == "keep"]
    return {
        "symbols_tested": len(rows),
        "positive_return_count": sum(1 for row in rows if (row["return_pct"] or 0) > 0),
        "profit_factor_gt_1_count": sum(1 for row in rows if (row["profit_factor"] or 0) > 1.0),
        "keep_candidate_count": len(kept),
        "mean_net_pnl_dollars": round_or_none(
            sum(float(row["net_pnl_dollars"] or 0) for row in rows) / len(rows) if rows else 0.0
        ),
        "mean_ending_balance": round_or_none(
            sum(float(row["ending_balance"] or 0) for row in rows) / len(rows) if rows else 0.0
        ),
        "mean_return_pct": round_or_none(sum(float(row["return_pct"] or 0) for row in rows) / len(rows) if rows else 0.0),
        "mean_win_rate": round_or_none(sum(float(row["win_rate"] or 0) for row in rows) / len(rows) if rows else 0.0),
        "mean_profit_factor": round_or_none(
            sum(float(row["profit_factor"] or 0) for row in rows) / len(rows) if rows else 0.0
        ),
        "mean_max_drawdown_dollars": round_or_none(
            sum(float(row["max_drawdown_dollars"] or 0) for row in rows) / len(rows) if rows else 0.0
        ),
    }


def keep_bucket(row: dict[str, object]) -> str:
    if (row["return_pct"] or 0) > 0 and (row["profit_factor"] or 0) >= 1.2 and (row["win_rate"] or 0) >= 50:
        return "keep"
    if (row["return_pct"] or 0) > 0 and (row["profit_factor"] or 0) >= 1.0:
        return "watch"
    return "skip"


def write_markdown(report: dict[str, object]) -> None:
    lines: list[str] = []
    lines.append("# CWT Asset Batch Report")
    lines.append("")
    lines.append(f"Date range: `{REPORT_START}` to `{REPORT_END}`")
    lines.append("")
    lines.append("Locked configuration:")
    lines.append("- H1 bias")
    lines.append("- Minimum execution timeframe by asset class")
    lines.append("- Scenario 1 + Scenario 2")
    lines.append("- Fixed 1:1 exit")
    lines.append("- ZigZag/Cambist approximation: 12 / 5 / 3")
    lines.append("- Ladder: 0.07 / 0.20 / 0.45 / 1.00")
    lines.append("- Per-asset daily cap: $1,000")
    lines.append("- Portfolio daily cap: $5,000")
    lines.append("- Overall brake: $95,000")
    lines.append("")
    lines.append("Important interpretation:")
    lines.append("- Each symbol below is run as its own funded-style simulation from a fresh $100,000 starting balance.")
    lines.append("- This makes the keep/skip decision clean per asset for future bot selection.")
    lines.append("- Commodity-FX overlaps are not listed separately to avoid double-counting the same symbol.")
    lines.append("")

    for group_id in GROUP_ORDER:
        group = report["groups"].get(group_id)
        if not group:
            continue
        pretty_name = group["label"]
        lines.append(f"## {pretty_name}")
        lines.append("")
        if group["available"]:
            lines.append(
                "| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |"
            )
            lines.append(
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
            )
            sorted_rows = sorted(
                group["available"],
                key=lambda row: (row["return_pct"] or -9999),
                reverse=True,
            )
            for row in sorted_rows:
                verdict = keep_bucket(row)
                skipped = int(row["trades_skipped_asset_cap"]) + int(row["trades_skipped_portfolio_cap"]) + int(row["trades_skipped_overall_brake"])
                lines.append(
                    f"| {row['symbol']} | {row['execution_timeframe']} | {row['ending_balance']:.2f} | {row['net_pnl_dollars']:.2f} | {row['return_pct']:.2f} | "
                    f"{row['avg_trade_pnl_dollars']:.2f} | {row['win_rate']:.2f}% | {row['profit_factor'] if row['profit_factor'] is not None else 'n/a'} | "
                    f"{row['avg_r']:.3f} | {row['reward_risk_ratio'] if row['reward_risk_ratio'] is not None else 'n/a'} | "
                    f"{row['max_drawdown_dollars']:.2f} | {row['max_winning_streak']} | {row['max_losing_streak']} | "
                    f"{row['trades_taken']} | {skipped} | {verdict} |"
                )
            lines.append("")
            summary = group["summary"]
            lines.append("Batch takeaways:")
            lines.append(f"- Symbols tested: {summary['symbols_tested']}")
            lines.append(f"- Positive-return symbols: {summary['positive_return_count']}")
            lines.append(f"- PF above 1.0: {summary['profit_factor_gt_1_count']}")
            lines.append(f"- Keep candidates: {summary['keep_candidate_count']}")
            lines.append(f"- Mean ending balance: ${summary['mean_ending_balance']:.2f}")
            lines.append(f"- Mean net PnL: ${summary['mean_net_pnl_dollars']:.2f}")
            lines.append(f"- Mean return: {summary['mean_return_pct']:.2f}%")
            lines.append(f"- Mean win rate: {summary['mean_win_rate']:.2f}%")
            lines.append(f"- Mean profit factor: {summary['mean_profit_factor']:.2f}")
            lines.append(f"- Mean max drawdown: ${summary['mean_max_drawdown_dollars']:.2f}")
            lines.append("")
        if group["unavailable"]:
            lines.append("Unavailable / failed symbols:")
            for item in group["unavailable"]:
                lines.append(f"- {item['symbol']}: {item['error']}")
            lines.append("")

    keep_rows = report["keep_list"]
    watch_rows = report["watch_list"]
    skip_rows = report["skip_list"]

    lines.append("## Shortlist")
    lines.append("")
    lines.append("Keep:")
    for row in keep_rows:
        lines.append(
            f"- {row['symbol']} ({row['group']}, {row['execution_timeframe']}): ending balance ${row['ending_balance']:.2f}, "
            f"net PnL ${row['net_pnl_dollars']:.2f}, {row['return_pct']:.2f}% return, PF {row['profit_factor']}, "
            f"win rate {row['win_rate']:.2f}%, max DD ${row['max_drawdown_dollars']:.2f}"
        )
    if not keep_rows:
        lines.append("- None")
    lines.append("")
    lines.append("Watch:")
    for row in watch_rows:
        lines.append(
            f"- {row['symbol']} ({row['group']}, {row['execution_timeframe']}): ending balance ${row['ending_balance']:.2f}, "
            f"net PnL ${row['net_pnl_dollars']:.2f}, {row['return_pct']:.2f}% return, PF {row['profit_factor']}, "
            f"win rate {row['win_rate']:.2f}%"
        )
    if not watch_rows:
        lines.append("- None")
    lines.append("")
    lines.append("Skip:")
    for row in skip_rows[:20]:
        lines.append(
            f"- {row['symbol']} ({row['group']}, {row['execution_timeframe']}): ending balance ${row['ending_balance']:.2f}, "
            f"net PnL ${row['net_pnl_dollars']:.2f}, {row['return_pct']:.2f}% return, PF {row['profit_factor']}, "
            f"win rate {row['win_rate']:.2f}%"
        )
    if not skip_rows:
        lines.append("- None")
    lines.append("")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    load_dotenv(".env")
    ensure_dir(OUTPUT_DIR)
    batches = load_batches()

    report: dict[str, object] = {
        "config": {
            "starting_balance": STARTING_BALANCE,
            "date_range": {"start": REPORT_START, "end": REPORT_END},
            "exit_mode": EXIT_MODE,
            "scenario_filter": SCENARIO_FILTER,
            "risk_ladder_pct": LADDER,
            "per_asset_daily_cap_dollars": ASSET_DAILY_CAP_DOLLARS,
            "portfolio_daily_cap_dollars": PORTFOLIO_DAILY_CAP_DOLLARS,
            "overall_brake_equity": OVERALL_BRAKE_EQUITY,
        },
        "groups": {},
        "keep_list": [],
        "watch_list": [],
        "skip_list": [],
    }

    for group_id in GROUP_ORDER:
        entries = batches.get(group_id, [])
        available: list[dict[str, object]] = []
        unavailable: list[dict[str, str]] = []
        for entry in entries:
            symbol = entry["symbol"]
            minimum_timeframe = entry["minimum_timeframe"]
            try:
                result = replay_symbol(symbol, minimum_timeframe)
                result["group"] = group_id
                available.append(result)
            except Exception as exc:  # pragma: no cover - research collection path
                unavailable.append({"symbol": symbol, "error": str(exc)})

        label = {
            "major_fx": "Major FX",
            "minor_cross_fx": "Minor & Cross FX",
            "indices": "Indices",
            "commodities": "Commodities",
        }[group_id]
        report["groups"][group_id] = {
            "label": label,
            "available": available,
            "unavailable": unavailable,
            "summary": group_summary(available) if available else None,
        }

        for row in available:
            bucket = keep_bucket(row)
            if bucket == "keep":
                report["keep_list"].append(row)
            elif bucket == "watch":
                report["watch_list"].append(row)
            else:
                report["skip_list"].append(row)

    report["keep_list"].sort(key=lambda row: (row["return_pct"] or -9999), reverse=True)
    report["watch_list"].sort(key=lambda row: (row["return_pct"] or -9999), reverse=True)
    report["skip_list"].sort(key=lambda row: (row["return_pct"] or -9999), reverse=True)

    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
