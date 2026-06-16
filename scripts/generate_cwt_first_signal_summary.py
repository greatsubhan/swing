"""Generate a first-signal-only CWT performance summary.

This report collapses repetitive same-direction follow-up signals into a single
tradable idea per symbol/timeframe/side cluster so we can estimate how the CWT
board behaves when only the first signal of a move is taken.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOURNAL_PATH = ROOT / "platform_output" / "strategy_four" / "signal_journal.json"
OUTPUT_DIR = ROOT / "reports" / "cwt_operational"
JSON_OUT = OUTPUT_DIR / "CWT_FIRST_SIGNAL_ONLY_SUMMARY.json"
MD_OUT = OUTPUT_DIR / "CWT_FIRST_SIGNAL_ONLY_SUMMARY.md"
STARTING_CAPITAL = 100_000.0
REPETITION_WINDOW_BARS = 12
TIMEFRAME_MINUTES = {"5m": 5, "15m": 15}


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


@dataclass
class TradeResult:
    setup_id: str
    symbol: str
    timeframe: str
    side: str
    signal_timestamp: str
    outcome: str
    risk_fraction: float
    realized_r: float
    pnl_amount: float
    equity_after: float
    filter_reason: str


def _risk_fraction(entry: dict[str, object]) -> float:
    raw = entry.get("raw_signal") or {}
    return float(raw.get("risk_fraction", 0.0) or 0.0)


def _cooldown_window(entry: dict[str, object]) -> timedelta:
    timeframe = str(entry.get("timeframe", "5m")).lower()
    minutes = TIMEFRAME_MINUTES.get(timeframe, 5)
    return timedelta(minutes=minutes * REPETITION_WINDOW_BARS)


def _select_first_signals(entries: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected: list[dict[str, object]] = []
    suppressed: list[dict[str, object]] = []
    last_selected_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    ordered = sorted(
        [
            entry
            for entry in entries
            if bool(entry.get("is_root_signal", True))
        ],
        key=lambda entry: (_parse_timestamp(entry.get("signal_timestamp")), str(entry.get("setup_id", ""))),
    )

    for entry in ordered:
        key = (str(entry.get("symbol")), str(entry.get("timeframe")), str(entry.get("side")))
        previous = last_selected_by_key.get(key)
        if previous is not None:
            previous_signal_time = _parse_timestamp(previous.get("signal_timestamp"))
            current_signal_time = _parse_timestamp(entry.get("signal_timestamp"))
            time_gap = current_signal_time - previous_signal_time

            if previous.get("status") != "closed":
                entry = {**entry, "suppressed_reason": "same_direction_active_trade"}
                suppressed.append(entry)
                continue

            if previous.get("outcome") == "tp_hit" and time_gap <= _cooldown_window(entry):
                entry = {**entry, "suppressed_reason": "same_direction_post_tp_cluster"}
                suppressed.append(entry)
                continue

        selected.append(entry)
        last_selected_by_key[key] = entry

    return selected, suppressed


def _realized_r(entry: dict[str, object]) -> float | None:
    outcome = entry.get("outcome")
    if entry.get("status") != "closed" or not outcome:
        return None
    if outcome == "tp_hit":
        return float(entry.get("risk_reward") or 1.0)
    if outcome == "sl_hit":
        return -1.0
    if outcome in {"break_even", "breakeven"}:
        return 0.0
    return 0.0


def build_summary() -> dict[str, object]:
    entries = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    selected, suppressed = _select_first_signals(entries)

    equity = STARTING_CAPITAL
    trade_results: list[TradeResult] = []
    closed_selected = [entry for entry in selected if entry.get("status") == "closed" and entry.get("outcome")]

    for entry in closed_selected:
        risk_fraction = _risk_fraction(entry)
        realized_r = float(_realized_r(entry) or 0.0)
        pnl_amount = equity * risk_fraction * realized_r
        equity += pnl_amount
        trade_results.append(
            TradeResult(
                setup_id=str(entry.get("setup_id")),
                symbol=str(entry.get("symbol")),
                timeframe=str(entry.get("timeframe")),
                side=str(entry.get("side")),
                signal_timestamp=str(entry.get("signal_timestamp")),
                outcome=str(entry.get("outcome")),
                risk_fraction=risk_fraction,
                realized_r=realized_r,
                pnl_amount=round(pnl_amount, 2),
                equity_after=round(equity, 2),
                filter_reason="selected",
            )
        )

    by_symbol: dict[str, dict[str, object]] = defaultdict(
        lambda: {"signals": 0, "tp": 0, "sl": 0, "net_risk_pct": 0.0}
    )
    for entry in closed_selected:
        symbol = str(entry.get("symbol"))
        outcome = str(entry.get("outcome"))
        risk_fraction = _risk_fraction(entry)
        by_symbol[symbol]["signals"] += 1
        if outcome == "tp_hit":
            by_symbol[symbol]["tp"] += 1
        elif outcome == "sl_hit":
            by_symbol[symbol]["sl"] += 1
        by_symbol[symbol]["net_risk_pct"] += risk_fraction * (1.0 if outcome == "tp_hit" else -1.0 if outcome == "sl_hit" else 0.0) * 100.0

    outcome_counts = Counter(entry.get("outcome") for entry in closed_selected)
    summary = {
        "assumptions": {
            "starting_capital": STARTING_CAPITAL,
            "method": "first_signal_only_same_direction_cluster_filter",
            "repetition_window_bars": REPETITION_WINDOW_BARS,
            "repetition_window_minutes": {
                timeframe: minutes * REPETITION_WINDOW_BARS for timeframe, minutes in TIMEFRAME_MINUTES.items()
            },
            "notes": [
                "Only root signals are considered tradable.",
                "Same-symbol/timeframe/side follow-up signals are suppressed while the prior selected trade is still open.",
                "After a TP, same-direction follow-ups inside the repetition window are treated as cluster duplicates rather than new trades.",
                "After an SL, the next qualifying same-direction signal is allowed so the ladder can progress.",
            ],
        },
        "headline": {
            "selected_signals": len(selected),
            "suppressed_repetitive_signals": len(suppressed),
            "closed_selected_signals": len(closed_selected),
            "open_selected_signals": sum(1 for entry in selected if entry.get("status") != "closed"),
            "tp_hits": outcome_counts.get("tp_hit", 0),
            "sl_hits": outcome_counts.get("sl_hit", 0),
            "win_rate": (outcome_counts.get("tp_hit", 0) / len(closed_selected)) if closed_selected else 0.0,
            "ending_equity": round(equity, 2),
            "net_profit": round(equity - STARTING_CAPITAL, 2),
        },
        "by_symbol": {
            symbol: {
                **payload,
                "net_risk_pct": round(float(payload["net_risk_pct"]), 2),
            }
            for symbol, payload in sorted(by_symbol.items())
        },
        "suppressed_reason_counts": Counter(entry.get("suppressed_reason", "unknown") for entry in suppressed),
        "trade_results": [asdict(result) for result in trade_results],
    }
    return summary


def _markdown(summary: dict[str, object]) -> str:
    headline = summary["headline"]
    assumptions = summary["assumptions"]
    lines = [
        "# CWT First Signal Only Summary",
        "",
        "## Headline",
        f"- Starting capital: `${assumptions['starting_capital']:,.2f}`",
        f"- Selected signals: `{headline['selected_signals']}`",
        f"- Suppressed repetitive signals: `{headline['suppressed_repetitive_signals']}`",
        f"- Closed selected signals: `{headline['closed_selected_signals']}`",
        f"- Open selected signals: `{headline['open_selected_signals']}`",
        f"- TP: `{headline['tp_hits']}`",
        f"- SL: `{headline['sl_hits']}`",
        f"- Win rate: `{headline['win_rate'] * 100:.2f}%`",
        f"- Ending equity: `${headline['ending_equity']:,.2f}`",
        f"- Net profit: `${headline['net_profit']:,.2f}`",
        "",
        "## Assumptions",
    ]
    for note in assumptions["notes"]:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## By Symbol",
            "| Symbol | Signals | TP | SL | Net Risk % |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for symbol, payload in summary["by_symbol"].items():
        lines.append(
            f"| `{symbol}` | `{payload['signals']}` | `{payload['tp']}` | `{payload['sl']}` | `{payload['net_risk_pct']:+.2f}%` |"
        )
    lines.extend(
        [
            "",
            "## Suppressed Repetition Reasons",
            "| Reason | Count |",
            "|---|---:|",
        ]
    )
    for reason, count in sorted(summary["suppressed_reason_counts"].items()):
        lines.append(f"| `{reason}` | `{count}` |")
    return "\n".join(lines) + "\n"


def main() -> None:
    summary = build_summary()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    MD_OUT.write_text(_markdown(summary), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
