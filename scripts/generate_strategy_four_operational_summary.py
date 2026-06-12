"""Generate an operational summary for the live CWT route.

This script reads the persisted platform outputs for `strategy_four` and writes:

- a JSON metrics snapshot for machine use
- a Markdown report for human review

It is intentionally read-only with respect to live bot state.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_OUTPUT = REPO_ROOT / "platform_output" / "strategy_four"
REPORT_DIR = REPO_ROOT / "reports" / "cwt_operational"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from signal_platform.journal import build_stats_snapshot, load_journal


def _load_route_cycle_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _same_hour_burst_count(timestamps: list[str]) -> int:
    burst = 0
    for previous, current in zip(timestamps, timestamps[1:]):
        if previous[:13] == current[:13]:
            burst += 1
    return burst


def _build_duplicate_clusters(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        grouped[(str(entry["symbol"]), str(entry["timeframe"]), str(entry["side"]))].append(entry)

    clusters: list[dict[str, object]] = []
    for (symbol, timeframe, side), items in grouped.items():
        items.sort(key=lambda item: str(item.get("signal_timestamp", "")))
        timestamps = [str(item.get("signal_timestamp", "")) for item in items]
        burst_count = _same_hour_burst_count(timestamps)
        if len(items) < 2:
            continue
        clusters.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "side": side,
                "signals": len(items),
                "same_hour_bursts": burst_count,
                "first_signal": timestamps[0] if timestamps else None,
                "last_signal": timestamps[-1] if timestamps else None,
            }
        )
    clusters.sort(key=lambda row: (-int(row["signals"]), -int(row["same_hour_bursts"]), row["symbol"]))
    return clusters


def _build_symbol_breakdown(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for entry in entries:
        grouped[(str(entry["symbol"]), str(entry["timeframe"]), str(entry["side"]))].append(entry)

    rows: list[dict[str, object]] = []
    for (symbol, timeframe, side), items in grouped.items():
        tp_hits = sum(1 for item in items if item.get("outcome") == "tp_hit")
        sl_hits = sum(1 for item in items if item.get("outcome") == "sl_hit")
        closed = [item for item in items if item.get("status") == "closed"]
        closed_count = len(closed)
        win_rate = (tp_hits / closed_count) if closed_count else None
        rows.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "side": side,
                "signals": len(items),
                "closed": closed_count,
                "open": sum(1 for item in items if item.get("status") == "open"),
                "tp_hits": tp_hits,
                "sl_hits": sl_hits,
                "win_rate": round(win_rate, 4) if win_rate is not None else None,
            }
        )
    rows.sort(key=lambda row: (-int(row["signals"]), row["symbol"], row["timeframe"], row["side"]))
    return rows


def _build_reinforcement_summary(decisions: list[dict[str, object]]) -> dict[str, object]:
    counts = Counter(str(decision.get("classification", "unknown")) for decision in decisions)
    reinforcement_strengths = [
        int(decision.get("strength_score", 0))
        for decision in decisions
        if str(decision.get("classification")) == "reinforcement"
    ]
    root_symbols = Counter(
        str(decision.get("symbol", "unknown"))
        for decision in decisions
        if str(decision.get("classification")) == "root_signal"
    )
    return {
        "root_signals": counts.get("root_signal", 0),
        "reinforcements": counts.get("reinforcement", 0),
        "avg_reinforcement_strength": round(mean(reinforcement_strengths), 2) if reinforcement_strengths else None,
        "top_root_symbols": root_symbols.most_common(5),
    }


def _build_route_log_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    if not rows:
        return {
            "cycles": 0,
            "dispatch_error_cycles": 0,
            "avg_signals_found": None,
            "avg_suppressed_duplicates": None,
            "latest_cycle": None,
        }
    signal_counts = [int(row.get("signals_found", "0") or 0) for row in rows]
    suppressed = [int(row.get("suppressed_duplicates", "0") or 0) for row in rows]
    error_cycles = sum(1 for row in rows if int(row.get("dispatch_errors", "0") or 0) > 0)
    return {
        "cycles": len(rows),
        "dispatch_error_cycles": error_cycles,
        "avg_signals_found": round(mean(signal_counts), 2) if signal_counts else None,
        "avg_suppressed_duplicates": round(mean(suppressed), 2) if suppressed else None,
        "latest_cycle": rows[-1],
    }


def _recommendations(
    stats_total_signals: int,
    duplicate_clusters: list[dict[str, object]],
    route_summary: dict[str, object],
) -> list[str]:
    recommendations: list[str] = []

    if stats_total_signals < 50:
        return ["More data required."]

    if duplicate_clusters:
        biggest = duplicate_clusters[0]
        if int(biggest["signals"]) >= 10 and int(biggest["same_hour_bursts"]) >= 5:
            recommendations.append(
                "Reinforcement is doing useful work: clustered same-structure alerts are present, "
                "especially on the busiest symbols, so keeping one tradable root signal plus reinforcement updates is justified."
            )

    if int(route_summary.get("dispatch_error_cycles", 0)) > 0:
        recommendations.append(
            "There have been some dispatch-error cycles in the route log. Keep the new watchdog/restart layer in place and continue "
            "watching webhook delivery, but the errors are not yet large enough to justify strategy-level changes."
        )

    if not recommendations:
        recommendations.append("More data required.")

    return recommendations


def generate_summary() -> dict[str, object]:
    journal_entries = load_journal(STRATEGY_OUTPUT / "signal_journal.json")
    journal_dicts = [entry.to_dict() for entry in journal_entries]
    stats = build_stats_snapshot(journal_entries)
    route_cycle_rows = _load_route_cycle_rows(STRATEGY_OUTPUT / "route_cycle_log.csv")
    reinforcement_decisions = _load_jsonl(STRATEGY_OUTPUT / "reinforcement_decisions.jsonl")

    summary = {
        "strategy_id": "strategy_four",
        "strategy_name": "Cambist With Trend",
        "generated_from": {
            "journal_file": str(STRATEGY_OUTPUT / "signal_journal.json"),
            "route_cycle_log": str(STRATEGY_OUTPUT / "route_cycle_log.csv"),
            "reinforcement_log": str(STRATEGY_OUTPUT / "reinforcement_decisions.jsonl"),
        },
        "performance": asdict(stats),
        "symbol_breakdown": _build_symbol_breakdown(journal_dicts),
        "duplicate_clusters": _build_duplicate_clusters(journal_dicts)[:10],
        "reinforcement_summary": _build_reinforcement_summary(reinforcement_decisions),
        "route_log_summary": _build_route_log_summary(route_cycle_rows),
    }
    summary["recommendations"] = _recommendations(
        stats_total_signals=summary["performance"]["total_signals"],
        duplicate_clusters=summary["duplicate_clusters"],
        route_summary=summary["route_log_summary"],
    )
    return summary


def _markdown_report(summary: dict[str, object]) -> str:
    perf = summary["performance"]
    breakdown_rows = summary["symbol_breakdown"][:8]
    cluster_rows = summary["duplicate_clusters"][:5]
    reinforcement = summary["reinforcement_summary"]
    route_summary = summary["route_log_summary"]

    lines = [
        "# CWT Operational Summary",
        "",
        "## Headline Metrics",
        "",
        f"- Total signals: `{perf['total_signals']}`",
        f"- Closed signals: `{perf['closed_signals']}`",
        f"- Open signals: `{perf['open_signals']}`",
        f"- TP hits: `{perf['tp_hits']}`",
        f"- SL hits: `{perf['sl_hits']}`",
        f"- Win rate: `{perf['win_rate'] * 100:.2f}%`",
        f"- Total realized R: `{perf['total_realized_r']:.2f}R`",
        f"- Average closed R: `{perf['avg_closed_r']:.2f}R`" if perf["avg_closed_r"] is not None else "- Average closed R: `n/a`",
        f"- Average hold: `{perf['avg_hold_hours']:.2f}h`" if perf["avg_hold_hours"] is not None else "- Average hold: `n/a`",
        "",
        "## Reinforcement Snapshot",
        "",
        f"- Root detections processed: `{reinforcement['root_signals']}`",
        f"- Reinforcement detections processed: `{reinforcement['reinforcements']}`",
        (
            f"- Average reinforcement strength: `{reinforcement['avg_reinforcement_strength']:.2f}/100`"
            if reinforcement["avg_reinforcement_strength"] is not None
            else "- Average reinforcement strength: `n/a`"
        ),
        "",
        "## Busiest Symbol Buckets",
        "",
        "| Symbol | TF | Side | Signals | Closed | Open | TP | SL | Win Rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in breakdown_rows:
        win_rate_text = f"{row['win_rate'] * 100:.2f}%" if row["win_rate"] is not None else "n/a"
        lines.append(
            f"| `{row['symbol']}` | `{row['timeframe']}` | `{row['side']}` | `{row['signals']}` | "
            f"`{row['closed']}` | `{row['open']}` | `{row['tp_hits']}` | `{row['sl_hits']}` | `{win_rate_text}` |"
        )

    lines.extend(
        [
            "",
            "## Duplicate-Feeling Clusters",
            "",
            "| Symbol | TF | Side | Signals | Same-Hour Bursts | First | Last |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in cluster_rows:
        lines.append(
            f"| `{row['symbol']}` | `{row['timeframe']}` | `{row['side']}` | `{row['signals']}` | "
            f"`{row['same_hour_bursts']}` | `{row['first_signal']}` | `{row['last_signal']}` |"
        )

    lines.extend(
        [
            "",
            "## Route Health",
            "",
            f"- Logged route cycles: `{route_summary['cycles']}`",
            f"- Cycles with dispatch errors: `{route_summary['dispatch_error_cycles']}`",
            (
                f"- Average signals found per cycle: `{route_summary['avg_signals_found']}`"
                if route_summary["avg_signals_found"] is not None
                else "- Average signals found per cycle: `n/a`"
            ),
            (
                f"- Average suppressed duplicates per cycle: `{route_summary['avg_suppressed_duplicates']}`"
                if route_summary["avg_suppressed_duplicates"] is not None
                else "- Average suppressed duplicates per cycle: `n/a`"
            ),
            "",
            "## Recommendations",
            "",
        ]
    )
    for recommendation in summary["recommendations"]:
        lines.append(f"- {recommendation}")

    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = generate_summary()
    json_path = REPORT_DIR / "CWT_OPERATIONAL_SUMMARY.json"
    md_path = REPORT_DIR / "CWT_OPERATIONAL_SUMMARY.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(summary), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
