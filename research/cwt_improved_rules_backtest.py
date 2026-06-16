"""Compare baseline CWT versus an improved ruleset on a 100k bankroll.

This script replays the existing CWT trade history through two paths:

- baseline: existing detected trades with the current ladder behavior
- improved: same detected opportunities, but with the suggested rule stack:
  - one-bar follow-through confirmation
  - high-noise session skip
  - duplicate-cluster suppression
  - mild stop help via +10% widening plus a 0.35 ATR minimum stop floor

It is intentionally a trade-level comparison study. It does not rescan fresh
setups from raw market data; instead it asks whether the suggested execution and
filtering changes improve the outcome of the already-detected CWT opportunities.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cwt_sl_forensics import (  # noqa: E402
    LADDER_SEQUENCE,
    _build_views,
    _entry_index,
    _load_bar_history,
    _parse_timestamp,
    _recent_noise_metrics,
    _symbol_point_floors,
)

OUTPUT_DIR = ROOT / "reports" / "cwt_improved_backtest"
REPORT_PATH = OUTPUT_DIR / "CWT_IMPROVED_BACKTEST_REPORT.md"
SUMMARY_PATH = OUTPUT_DIR / "cwt_improved_backtest_summary.json"
COMPARISON_CSV = OUTPUT_DIR / "cwt_improved_backtest_comparison.csv"
TRADE_LOG_CSV = OUTPUT_DIR / "cwt_improved_backtest_trade_log.csv"

STARTING_CAPITAL = 100_000.0

STOP_SCALE = 1.10
MIN_ATR_MULTIPLE = 0.35


def _max_drawdown_pct(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)
    return max_drawdown * 100.0


def _realized_r(entry: dict[str, Any]) -> float:
    if entry.get("outcome") == "tp_hit":
        return float(entry.get("risk_reward") or 1.0)
    if entry.get("outcome") == "sl_hit":
        return -1.0
    return 0.0


def _followthrough_passes(side: str, confirmation_bar: Any, reference_entry: float) -> bool:
    close = float(confirmation_bar["close"])
    open_price = float(confirmation_bar["open"])
    if side == "long":
        return close > open_price and close > reference_entry
    return close < open_price and close < reference_entry


def _simulate_improved_combo(
    row: dict[str, Any],
    frame: Any,
    symbol_point_floors: dict[str, float],
) -> dict[str, Any]:
    entry_idx = row.get("_entry_index")
    if entry_idx is None:
        return {"status": "skipped", "skip_reason": "missing_entry_bar"}
    if row.get("duplicate_cluster_exposure"):
        return {"status": "skipped", "skip_reason": "duplicate_cluster"}
    if row.get("high_noise_session"):
        return {"status": "skipped", "skip_reason": "high_noise_session"}

    confirmation_idx = int(entry_idx)
    delayed_idx = confirmation_idx + 1
    if delayed_idx >= len(frame):
        return {"status": "skipped", "skip_reason": "missing_confirmation_entry"}

    confirmation_bar = frame.iloc[confirmation_idx]
    reference_entry = float(row["entry"])
    side = str(row["side"])
    if not _followthrough_passes(side, confirmation_bar, reference_entry):
        return {"status": "skipped", "skip_reason": "missing_followthrough"}

    entry_row = frame.iloc[delayed_idx]
    entry_price = float(entry_row["open"])
    base_stop = float(row["stop_loss"])
    risk_distance = abs(entry_price - base_stop) * STOP_SCALE
    atr_value = float(entry_row["atr14"]) if pd.notna(entry_row["atr14"]) else None
    if atr_value is not None:
        risk_distance = max(risk_distance, MIN_ATR_MULTIPLE * atr_value)
    risk_distance = max(risk_distance, float(symbol_point_floors.get(str(row["symbol"]), 0.0)))
    stop_price = entry_price - risk_distance if side == "long" else entry_price + risk_distance
    target_price = float(row["target_1"])
    if (side == "long" and entry_price >= target_price) or (side == "short" and entry_price <= target_price):
        return {"status": "skipped", "skip_reason": "target_already_passed"}

    bars_checked = 0
    for idx in range(delayed_idx + 1, len(frame)):
        bars_checked += 1
        bar = frame.iloc[idx]
        high = float(bar["high"])
        low = float(bar["low"])
        timestamp = frame.index[idx].isoformat()
        if side == "long":
            if low <= stop_price and high >= target_price:
                return {
                    "status": "closed",
                    "outcome": "sl_hit",
                    "realized_r": -1.0,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }
            if low <= stop_price:
                return {
                    "status": "closed",
                    "outcome": "sl_hit",
                    "realized_r": -1.0,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }
            if high >= target_price:
                realized_r = abs(target_price - entry_price) / risk_distance if risk_distance else 0.0
                return {
                    "status": "closed",
                    "outcome": "tp_hit",
                    "realized_r": realized_r,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }
        else:
            if high >= stop_price and low <= target_price:
                return {
                    "status": "closed",
                    "outcome": "sl_hit",
                    "realized_r": -1.0,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }
            if high >= stop_price:
                return {
                    "status": "closed",
                    "outcome": "sl_hit",
                    "realized_r": -1.0,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }
            if low <= target_price:
                realized_r = abs(target_price - entry_price) / risk_distance if risk_distance else 0.0
                return {
                    "status": "closed",
                    "outcome": "tp_hit",
                    "realized_r": realized_r,
                    "bars_checked": bars_checked,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "outcome_timestamp": timestamp,
                }

    return {
        "status": "open",
        "bars_checked": bars_checked,
        "entry_price": entry_price,
        "stop_price": stop_price,
    }


def _load_rows_with_context() -> list[dict[str, Any]]:
    rows = _build_views()
    bar_cache: dict[tuple[str, str], Any] = {}
    symbol_point_floors = _symbol_point_floors([row for row in rows if row.get("status") == "closed"])
    prepared: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "closed":
            continue
        frame = _load_bar_history(str(row["symbol"]), str(row["timeframe"]), bar_cache)
        entry_idx = _entry_index(frame, str(row["signal_timestamp"]))
        row = dict(row)
        row["_entry_index"] = entry_idx
        if entry_idx is not None:
            noise = _recent_noise_metrics(frame, entry_idx)
            row["high_noise_session"] = bool(noise["high_noise"])
        else:
            row["high_noise_session"] = False
        result = _simulate_improved_combo(row, frame, symbol_point_floors)
        row["improved_status"] = result.get("status")
        row["improved_outcome"] = result.get("outcome")
        row["improved_realized_r"] = result.get("realized_r")
        row["improved_bars_checked"] = result.get("bars_checked")
        row["improved_skip_reason"] = result.get("skip_reason")
        row["improved_entry_price"] = result.get("entry_price")
        row["improved_stop_price"] = result.get("stop_price")
        prepared.append(row)
    return prepared


def _simulate_bankroll(
    rows: list[dict[str, Any]],
    *,
    mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: (_parse_timestamp(row["signal_timestamp"]), str(row["setup_id"])))
    equity = STARTING_CAPITAL
    equity_curve = [STARTING_CAPITAL]
    step_index = 0
    trade_count = 0
    win_count = 0
    gross_profit_r = 0.0
    gross_loss_r = 0.0
    total_r = 0.0
    skipped = Counter()
    step_use_counts = Counter()
    per_symbol = Counter()
    trade_log: list[dict[str, Any]] = []

    for row in ordered:
        if mode == "baseline":
            status = "closed"
            outcome = row.get("outcome")
            realized_r = _realized_r(row)
            bars_checked = row.get("bars_checked")
            entry_price = row.get("entry")
            stop_price = row.get("stop_loss")
        else:
            status = row.get("improved_status")
            outcome = row.get("improved_outcome")
            realized_r = float(row.get("improved_realized_r") or 0.0)
            bars_checked = row.get("improved_bars_checked")
            entry_price = row.get("improved_entry_price")
            stop_price = row.get("improved_stop_price")

        if status == "skipped":
            skipped[str(row.get("improved_skip_reason") or "unknown")] += 1
            trade_log.append(
                {
                    "mode": mode,
                    "executed": False,
                    "skip_reason": str(row.get("improved_skip_reason") or "unknown"),
                    "signal_timestamp": row["signal_timestamp"],
                    "setup_id": row["setup_id"],
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "side": row["side"],
                    "scenario": row.get("scenario"),
                    "ladder_step_at_signal": step_index + 1,
                    "risk_pct_at_signal": LADDER_SEQUENCE[step_index],
                    "equity_before": round(equity, 2),
                    "equity_after": round(equity, 2),
                }
            )
            continue
        if status != "closed":
            continue

        trade_count += 1
        per_symbol[str(row["symbol"])] += 1
        risk_pct = LADDER_SEQUENCE[step_index]
        step_use_counts[risk_pct] += 1
        risk_fraction = risk_pct / 100.0
        equity_before = equity
        pnl = equity_before * risk_fraction * realized_r
        equity += pnl
        equity_curve.append(equity)
        total_r += realized_r
        if realized_r > 0:
            win_count += 1
            gross_profit_r += realized_r
        elif realized_r < 0:
            gross_loss_r += abs(realized_r)

        next_step = step_index
        if outcome == "tp_hit":
            next_step = 0
        elif outcome == "sl_hit":
            next_step = min(step_index + 1, len(LADDER_SEQUENCE) - 1)

        trade_log.append(
            {
                "mode": mode,
                "executed": True,
                "skip_reason": "",
                "signal_timestamp": row["signal_timestamp"],
                "setup_id": row["setup_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "side": row["side"],
                "scenario": row.get("scenario"),
                "ladder_step_at_signal": step_index + 1,
                "risk_pct_at_signal": risk_pct,
                "equity_before": round(equity_before, 2),
                "entry_price": entry_price,
                "stop_price": stop_price,
                "bars_checked": bars_checked,
                "outcome": outcome,
                "realized_r": round(realized_r, 6),
                "pnl": round(pnl, 2),
                "equity_after": round(equity, 2),
                "next_ladder_step": next_step + 1,
            }
        )
        step_index = next_step

    profit_factor = (gross_profit_r / gross_loss_r) if gross_loss_r else None
    summary = {
        "mode": mode,
        "starting_capital": STARTING_CAPITAL,
        "trade_count": trade_count,
        "skipped_count": int(sum(skipped.values())),
        "wins": win_count,
        "losses": trade_count - win_count,
        "win_rate_pct": round((win_count / trade_count) * 100.0, 2) if trade_count else 0.0,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "total_r": round(total_r, 6),
        "avg_r": round(total_r / trade_count, 6) if trade_count else 0.0,
        "ending_equity": round(equity, 2),
        "net_pnl": round(equity - STARTING_CAPITAL, 2),
        "return_pct": round(((equity / STARTING_CAPITAL) - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(_max_drawdown_pct(equity_curve), 2),
        "step_use_counts": {f"{step:.2f}%": int(count) for step, count in sorted(step_use_counts.items())},
        "skipped_reason_counts": dict(skipped),
        "per_symbol_trade_counts": dict(sorted(per_symbol.items())),
    }
    return summary, trade_log


def _comparison_row(dataset: str, baseline: dict[str, Any], improved: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "baseline_trades": baseline["trade_count"],
        "improved_trades": improved["trade_count"],
        "trade_delta": improved["trade_count"] - baseline["trade_count"],
        "baseline_skipped": baseline["skipped_count"],
        "improved_skipped": improved["skipped_count"],
        "baseline_win_rate_pct": baseline["win_rate_pct"],
        "improved_win_rate_pct": improved["win_rate_pct"],
        "win_rate_delta_pct": round(improved["win_rate_pct"] - baseline["win_rate_pct"], 2),
        "baseline_profit_factor": baseline["profit_factor"],
        "improved_profit_factor": improved["profit_factor"],
        "baseline_avg_r": baseline["avg_r"],
        "improved_avg_r": improved["avg_r"],
        "baseline_total_r": baseline["total_r"],
        "improved_total_r": improved["total_r"],
        "baseline_ending_equity": baseline["ending_equity"],
        "improved_ending_equity": improved["ending_equity"],
        "ending_equity_delta": round(improved["ending_equity"] - baseline["ending_equity"], 2),
        "baseline_return_pct": baseline["return_pct"],
        "improved_return_pct": improved["return_pct"],
        "baseline_max_drawdown_pct": baseline["max_drawdown_pct"],
        "improved_max_drawdown_pct": improved["max_drawdown_pct"],
    }


def build_report() -> dict[str, Any]:
    rows = _load_rows_with_context()
    datasets = {
        "operational_journal_root_only": [
            row for row in rows if row["source_section"] == "operational_journal" and row["trade_lens"] == "root_only"
        ],
        "since_inception_replay_root_only": [
            row for row in rows if row["source_section"] == "since_inception_replay" and row["trade_lens"] == "root_only"
        ],
        "since_inception_replay_raw": [
            row for row in rows if row["source_section"] == "since_inception_replay" and row["trade_lens"] == "raw"
        ],
    }

    summaries: dict[str, dict[str, Any]] = {}
    comparison_rows: list[dict[str, Any]] = []
    trade_logs: list[dict[str, Any]] = []

    for name, subset in datasets.items():
        baseline_summary, baseline_log = _simulate_bankroll(subset, mode="baseline")
        improved_summary, improved_log = _simulate_bankroll(subset, mode="improved")
        summaries[name] = {
            "baseline": baseline_summary,
            "improved": improved_summary,
        }
        comparison_rows.append(_comparison_row(name, baseline_summary, improved_summary))
        trade_logs.extend([{**row, "dataset": name} for row in baseline_log])
        trade_logs.extend([{**row, "dataset": name} for row in improved_log])

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assumptions": {
            "starting_capital": STARTING_CAPITAL,
            "ladder_sequence_pct": LADDER_SEQUENCE,
            "analysis_type": "trade_level_replay_of_existing_cwt_opportunities",
            "improved_ruleset": {
                "require_followthrough": True,
                "skip_high_noise": True,
                "skip_duplicate_cluster": True,
                "stop_scale": 1.10,
                "min_atr_multiple": 0.35,
            },
            "notes": [
                "This is not a fresh signal rescan from raw market data.",
                "It measures whether the suggested execution/filter changes improve the outcomes of the detected CWT opportunities.",
                "Root-only views are the cleaner operational comparison for tradable ideas.",
            ],
        },
        "datasets": summaries,
        "comparison_rows": comparison_rows,
        "trade_logs": trade_logs,
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps({k: v for k, v in payload.items() if k != "trade_logs"}, indent=2),
        encoding="utf-8",
    )

    comparison_fields = list(payload["comparison_rows"][0].keys())
    with COMPARISON_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison_fields)
        writer.writeheader()
        writer.writerows(payload["comparison_rows"])

    trade_fields = sorted({key for row in payload["trade_logs"] for key in row.keys()})
    with TRADE_LOG_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=trade_fields)
        writer.writeheader()
        writer.writerows(payload["trade_logs"])

    lines = [
        "# CWT Improved Rules Backtest",
        "",
        "## Improved Ruleset Tested",
        "",
        "- `Require one-bar follow-through`",
        "- `Skip high-noise sessions`",
        "- `Skip duplicate-cluster trades`",
        "- `Mild stop help`: `+10%` widen plus `0.35 ATR` minimum floor",
        "- Bankroll: `$100,000`",
        f"- Ladder: `{', '.join(f'{step:.2f}%' for step in LADDER_SEQUENCE)}`",
        "",
        "## Comparison",
        "",
        "| Dataset | Baseline Trades | Improved Trades | Trade Delta | Baseline Return | Improved Return | Baseline PF | Improved PF | Baseline Avg R | Improved Avg R | Baseline Max DD | Improved Max DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["comparison_rows"]:
        lines.append(
            f"| `{row['dataset']}` | `{row['baseline_trades']}` | `{row['improved_trades']}` | `{row['trade_delta']:+d}` | "
            f"`{row['baseline_return_pct']}%` | `{row['improved_return_pct']}%` | "
            f"`{row['baseline_profit_factor']}` | `{row['improved_profit_factor']}` | "
            f"`{row['baseline_avg_r']}` | `{row['improved_avg_r']}` | "
            f"`{row['baseline_max_drawdown_pct']}%` | `{row['improved_max_drawdown_pct']}%` |"
        )

    lines.extend(["", "## Skip Breakdown", ""])
    for dataset, block in payload["datasets"].items():
        lines.append(f"### `{dataset}`")
        lines.append("")
        lines.append(f"- Baseline trades: `{block['baseline']['trade_count']}`")
        lines.append(f"- Improved trades: `{block['improved']['trade_count']}`")
        lines.append(f"- Improved skipped: `{block['improved']['skipped_count']}`")
        for reason, count in sorted(block["improved"]["skipped_reason_counts"].items()):
            lines.append(f"- `{reason}`: `{count}`")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_report()
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH),
                "summary": str(SUMMARY_PATH),
                "comparison_csv": str(COMPARISON_CSV),
                "trade_log_csv": str(TRADE_LOG_CSV),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
