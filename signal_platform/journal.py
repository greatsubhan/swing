"""Signal journaling, outcome tracking, and report helpers."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from little_rzy_bot.market_data import fetch_oanda_ohlcv

from .models import JournalEntry, PlatformSignal, SignalStatsSnapshot


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_journal(path: str | Path) -> list[JournalEntry]:
    journal_path = Path(path)
    if not journal_path.exists():
        return []
    payload = json.loads(journal_path.read_text() or "[]")
    allowed_fields = {field.name for field in fields(JournalEntry)}
    entries: list[JournalEntry] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        normalized = {key: value for key, value in entry.items() if key in allowed_fields}
        entries.append(JournalEntry(**normalized))
    return entries


def save_journal(path: str | Path, entries: list[JournalEntry]) -> None:
    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps([entry.to_dict() for entry in entries], indent=2))


def _next_ladder_state(entry: JournalEntry) -> tuple[int | None, float | None, str | None]:
    if entry.ladder_step_at_entry is None:
        return None, None, None
    sequence = entry.ladder_sequence_pct or []
    if not sequence:
        return None, None, None
    current_step = max(0, min(int(entry.ladder_step_at_entry), len(sequence) - 1))
    outcome = str(entry.outcome or "")
    if outcome == "tp_hit":
        return 0, float(sequence[0]), "reset_after_tp"
    if outcome == "sl_hit":
        next_step = min(current_step + 1, len(sequence) - 1)
        return next_step, float(sequence[next_step]), "advance_after_sl"
    if outcome in {"break_even", "breakeven"}:
        return current_step, float(sequence[current_step]), "hold_after_break_even"
    return current_step, float(sequence[current_step]), "unchanged"


def build_ladder_ledger(entries: list[JournalEntry]) -> dict[str, object]:
    by_symbol: dict[str, list[JournalEntry]] = {}
    for entry in entries:
        if entry.ladder_step_at_entry is None:
            continue
        by_symbol.setdefault(entry.symbol, []).append(entry)

    symbols_payload: dict[str, object] = {}
    for symbol, symbol_entries in sorted(by_symbol.items()):
        ordered = sorted(
            symbol_entries,
            key=lambda entry: (
                entry.signal_timestamp,
                entry.setup_id,
            ),
        )
        events: list[dict[str, object]] = []
        current_state: dict[str, object] | None = None
        for entry in ordered:
            events.append(
                {
                    "setup_id": entry.setup_id,
                    "timeframe": entry.timeframe,
                    "side": entry.side,
                    "signal_timestamp": entry.signal_timestamp,
                    "status": entry.status,
                    "outcome": entry.outcome,
                    "outcome_timestamp": entry.outcome_timestamp,
                    "ladder_step_at_entry": entry.ladder_step_at_entry,
                    "ladder_risk_pct_at_entry": entry.ladder_risk_pct_at_entry,
                    "ladder_risk_display_at_entry": entry.ladder_risk_display_at_entry,
                    "ladder_previous_outcome": entry.ladder_previous_outcome,
                    "ladder_previous_setup_id": entry.ladder_previous_setup_id,
                    "ladder_step_after_outcome": entry.ladder_step_after_outcome,
                    "ladder_next_risk_pct": entry.ladder_next_risk_pct,
                    "ladder_transition_note": entry.ladder_transition_note,
                }
            )
            current_state = {
                "last_setup_id": entry.setup_id,
                "status": entry.status,
                "outcome": entry.outcome,
                "ladder_step": entry.ladder_step_after_outcome if entry.status == "closed" else entry.ladder_step_at_entry,
                "risk_pct": entry.ladder_next_risk_pct if entry.status == "closed" else entry.ladder_risk_pct_at_entry,
                "updated_at": entry.outcome_timestamp or entry.signal_timestamp,
            }
        symbols_payload[symbol] = {
            "current_state": current_state,
            "events": events,
        }

    return {
        "updated_at_utc": utc_now_iso(),
        "symbol_count": len(symbols_payload),
        "symbols": symbols_payload,
    }


def save_ladder_ledger(path: str | Path, entries: list[JournalEntry]) -> None:
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(build_ladder_ledger(entries), indent=2))


def enrich_ladder_fields(entries: list[JournalEntry]) -> list[JournalEntry]:
    for entry in entries:
        raw_signal = entry.raw_signal or {}
        if entry.ladder_sequence_pct == [] and raw_signal.get("ladder_sequence_pct"):
            entry.ladder_sequence_pct = [float(value) for value in raw_signal.get("ladder_sequence_pct", [])]
        if entry.ladder_step_at_entry is None and raw_signal.get("ladder_step_index") is not None:
            entry.ladder_step_at_entry = int(raw_signal["ladder_step_index"])
        if entry.ladder_risk_pct_at_entry is None and raw_signal.get("risk_fraction") is not None:
            entry.ladder_risk_pct_at_entry = float(raw_signal["risk_fraction"]) * 100.0
        if entry.ladder_risk_display_at_entry is None:
            entry.ladder_risk_display_at_entry = raw_signal.get("risk_display")
        if entry.ladder_previous_outcome is None:
            entry.ladder_previous_outcome = raw_signal.get("previous_outcome")
        if entry.ladder_previous_setup_id is None:
            entry.ladder_previous_setup_id = raw_signal.get("previous_setup_id")
        if entry.status == "closed" and entry.ladder_step_after_outcome is None:
            next_step, next_risk_pct, transition_note = _next_ladder_state(entry)
            entry.ladder_step_after_outcome = next_step
            entry.ladder_next_risk_pct = next_risk_pct
            entry.ladder_transition_note = transition_note
    return entries


def append_new_signals(entries: list[JournalEntry], signals: list[PlatformSignal]) -> list[JournalEntry]:
    existing_ids = {entry.setup_id for entry in entries}
    now = utc_now_iso()
    for signal in signals:
        if not signal.is_tradable:
            continue
        if signal.setup_id in existing_ids:
            continue
        entries.append(
            JournalEntry(
                strategy_id=signal.strategy_id,
                strategy_name=signal.strategy_name,
                setup_id=signal.setup_id,
                symbol=signal.symbol,
                asset_class=signal.asset_class,
                timeframe=signal.timeframe,
                side=signal.side,
                signal_timestamp=signal.timestamp,
                dispatched_at_utc=now,
                entry=float(signal.entry or 0.0),
                stop_loss=float(signal.stop_loss or 0.0),
                target_1=float(signal.target_1 or 0.0),
                risk_reward=signal.risk_reward,
                quality_score=signal.quality_score,
                quality_grade=signal.quality_grade,
                status="open",
                is_root_signal=True,
                structure_id=signal.structure_id,
                root_signal_id=signal.root_signal_id or signal.setup_id,
                reinforcement_count_at_dispatch=signal.reinforcement_count,
                strength_score_at_dispatch=signal.strength_score,
                ladder_sequence_pct=[float(value) for value in signal.raw_signal.get("ladder_sequence_pct", [])],
                ladder_step_at_entry=(
                    int(signal.raw_signal["ladder_step_index"])
                    if signal.raw_signal.get("ladder_step_index") is not None
                    else None
                ),
                ladder_risk_pct_at_entry=(
                    float(signal.raw_signal["risk_fraction"]) * 100.0
                    if signal.raw_signal.get("risk_fraction") is not None
                    else None
                ),
                ladder_risk_display_at_entry=signal.raw_signal.get("risk_display"),
                ladder_previous_outcome=signal.raw_signal.get("previous_outcome"),
                ladder_previous_setup_id=signal.raw_signal.get("previous_setup_id"),
                raw_signal=signal.raw_signal,
            )
        )
    return entries


def backfill_known_signals(entries: list[JournalEntry], signals: list[PlatformSignal], known_setup_ids: set[str]) -> list[JournalEntry]:
    existing_ids = {entry.setup_id for entry in entries}
    bootstrap = [signal for signal in signals if signal.setup_id in known_setup_ids and signal.setup_id not in existing_ids]
    return append_new_signals(entries, bootstrap)


def build_stats_snapshot(entries: list[JournalEntry]) -> SignalStatsSnapshot:
    total = len(entries)
    closed = sum(1 for entry in entries if entry.status == "closed")
    open_count = total - closed
    outcome_counts = Counter(entry.outcome for entry in entries if entry.outcome)
    tp_hits = outcome_counts.get("tp_hit", 0)
    sl_hits = outcome_counts.get("sl_hit", 0)
    other = closed - tp_hits - sl_hits
    closed_with_outcome = tp_hits + sl_hits + max(other, 0)
    win_rate = (tp_hits / closed_with_outcome) if closed_with_outcome else 0.0
    holds = [entry.hold_hours() for entry in entries if entry.status == "closed"]
    hold_values = [value for value in holds if value is not None]
    realized = [entry.realized_r() for entry in entries if entry.status == "closed"]
    realized_values = [value for value in realized if value is not None]
    return SignalStatsSnapshot(
        total_signals=total,
        closed_signals=closed,
        open_signals=open_count,
        tp_hits=tp_hits,
        sl_hits=sl_hits,
        other_closures=max(other, 0),
        win_rate=win_rate,
        avg_hold_hours=mean(hold_values) if hold_values else None,
        total_realized_r=sum(realized_values) if realized_values else 0.0,
        avg_closed_r=mean(realized_values) if realized_values else None,
    )


def signal_with_stats(signal: PlatformSignal, stats: SignalStatsSnapshot) -> PlatformSignal:
    enriched = PlatformSignal(**signal.to_dict())
    enriched.raw_signal = {**signal.raw_signal, "stats_snapshot": stats.to_dict()}
    return enriched


def _outcome_price_for_entry(entry: JournalEntry, price: str, outcome_price_mode: str) -> str:
    mode = str(outcome_price_mode or "route_default").strip().lower()
    if mode == "side_aware":
        return "B" if entry.side == "long" else "A"
    return price


def _find_outcome(
    entry: JournalEntry,
    token: str | None,
    environment: str,
    price: str,
    outcome_price_mode: str = "route_default",
) -> tuple[str, str, float, int] | None:
    timeframe_key = entry.timeframe.lower()
    granularity = {
        "5m": "M5",
        "15m": "M15",
        "1h": "H1",
        "h1": "H1",
        "4h": "H4",
        "h4": "H4",
        "1d": "D",
        "d": "D",
    }.get(timeframe_key, "H1")
    fetched = fetch_oanda_ohlcv(
        instrument=entry.symbol,
        granularity=granularity,
        start=entry.signal_timestamp,
        end=None,
        price=_outcome_price_for_entry(entry, price, outcome_price_mode),
        token=token,
        environment=environment,
    )
    df = fetched.df.sort_index()
    if df.empty:
        return None
    bars_checked = 0
    for timestamp, row in df.iterrows():
        if str(timestamp.isoformat()) <= entry.signal_timestamp:
            continue
        bars_checked += 1
        high = float(row["high"])
        low = float(row["low"])
        if entry.side == "long":
            if low <= entry.stop_loss and high >= entry.target_1:
                return ("sl_hit", timestamp.isoformat(), entry.stop_loss, bars_checked)
            if low <= entry.stop_loss:
                return ("sl_hit", timestamp.isoformat(), entry.stop_loss, bars_checked)
            if high >= entry.target_1:
                return ("tp_hit", timestamp.isoformat(), entry.target_1, bars_checked)
        else:
            if high >= entry.stop_loss and low <= entry.target_1:
                return ("sl_hit", timestamp.isoformat(), entry.stop_loss, bars_checked)
            if high >= entry.stop_loss:
                return ("sl_hit", timestamp.isoformat(), entry.stop_loss, bars_checked)
            if low <= entry.target_1:
                return ("tp_hit", timestamp.isoformat(), entry.target_1, bars_checked)
    return None


def refresh_open_entries(
    entries: list[JournalEntry],
    token: str | None,
    environment: str,
    price: str,
    outcome_price_mode: str = "route_default",
) -> list[JournalEntry]:
    updates: list[JournalEntry] = []
    now = utc_now_iso()
    for entry in entries:
        if entry.status != "open":
            continue
        entry.last_checked_utc = now
        try:
            outcome = _find_outcome(
                entry,
                token=token,
                environment=environment,
                price=price,
                outcome_price_mode=outcome_price_mode,
            )
        except Exception as exc:
            entry.raw_signal = {**entry.raw_signal, "last_outcome_refresh_error": str(exc)}
            updates.append(entry)
            continue
        if not outcome:
            updates.append(entry)
            continue
        reason, timestamp, exit_price, bars_checked = outcome
        entry.status = "closed"
        entry.outcome = reason
        entry.outcome_timestamp = timestamp
        entry.exit_price = exit_price
        entry.bars_checked = bars_checked
        next_step, next_risk_pct, transition_note = _next_ladder_state(entry)
        entry.ladder_step_after_outcome = next_step
        entry.ladder_next_risk_pct = next_risk_pct
        entry.ladder_transition_note = transition_note
        updates.append(entry)
    return entries


def unresolved_entries(entries: list[JournalEntry]) -> list[JournalEntry]:
    return [entry for entry in entries if entry.status == "open"]


def pending_outcome_notifications(entries: list[JournalEntry], limit: int | None = None) -> list[JournalEntry]:
    pending = [
        entry
        for entry in entries
        if entry.status == "closed" and entry.outcome_timestamp and not entry.outcome_notified
    ]
    pending.sort(
        key=lambda entry: (
            entry.outcome_timestamp or "",
            entry.dispatched_at_utc,
            entry.setup_id,
        )
    )
    if limit is not None:
        return pending[:limit]
    return pending


def resolved_entries_since(entries: list[JournalEntry], since_utc: datetime) -> list[JournalEntry]:
    resolved: list[JournalEntry] = []
    for entry in entries:
        if entry.status != "closed" or not entry.outcome_timestamp or entry.outcome_notified:
            continue
        ts = datetime.fromisoformat(entry.outcome_timestamp.replace("Z", "+00:00"))
        if ts >= since_utc:
            resolved.append(entry)
    return resolved


def journal_summary_message(entries: list[JournalEntry], period_label: str, since_utc: datetime) -> str:
    data = journal_summary_data(entries, period_label, since_utc)
    return (
        f"{data['period_label']} report\n"
        f"Signals sent: {data['signals_sent']}\n"
        f"Still open: {data['open_count']}\n"
        f"TP hit: {data['tp_hits']}\n"
        f"SL hit: {data['sl_hits']}\n"
        f"Net realized: {data['total_realized_r']:.2f}R\n"
        f"Average closed trade: {data['avg_closed_r_text']}\n"
        f"Average hold time: {data['avg_hold_text']}\n"
        f"TP list: {data['tp_list_text']}\n"
        f"SL list: {data['sl_list_text']}\n"
        f"Open list: {data['open_list_text']}"
    )


def journal_summary_data(entries: list[JournalEntry], period_label: str, since_utc: datetime) -> dict[str, object]:
    period_entries = [entry for entry in entries if datetime.fromisoformat(entry.dispatched_at_utc.replace("Z", "+00:00")) >= since_utc]
    resolved = [entry for entry in period_entries if entry.status == "closed"]
    open_count = sum(1 for entry in period_entries if entry.status == "open")
    tp_hits = sum(1 for entry in resolved if entry.outcome == "tp_hit")
    sl_hits = sum(1 for entry in resolved if entry.outcome == "sl_hit")
    realized = [entry.realized_r() for entry in resolved]
    realized_values = [value for value in realized if value is not None]
    total_realized_r = sum(realized_values) if realized_values else 0.0
    avg_closed_r = mean(realized_values) if realized_values else None
    holds = [entry.hold_hours() for entry in resolved]
    hold_values = [value for value in holds if value is not None]
    avg_hold = mean(hold_values) if hold_values else None
    avg_hold_text = f"{avg_hold:.1f}h" if avg_hold is not None else "n/a"
    avg_closed_r_text = f"{avg_closed_r:.2f}R" if avg_closed_r is not None else "n/a"
    tp_list = [f"{entry.symbol} ({entry.realized_r():.2f}R)" for entry in resolved if entry.outcome == "tp_hit"]
    sl_list = [f"{entry.symbol} ({entry.realized_r():.2f}R)" for entry in resolved if entry.outcome == "sl_hit"]
    open_list = [f"{entry.symbol}" for entry in period_entries if entry.status == "open"]
    return {
        "period_label": period_label,
        "signals_sent": len(period_entries),
        "open_count": open_count,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "total_realized_r": total_realized_r,
        "avg_closed_r": avg_closed_r,
        "avg_closed_r_text": avg_closed_r_text,
        "avg_hold_hours": avg_hold,
        "avg_hold_text": avg_hold_text,
        "tp_list": tp_list,
        "sl_list": sl_list,
        "open_list": open_list,
        "tp_list_text": ", ".join(tp_list) or "none",
        "sl_list_text": ", ".join(sl_list) or "none",
        "open_list_text": ", ".join(open_list) or "none",
    }


def load_report_state(path: str | Path) -> dict[str, str]:
    state_path = Path(path)
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text() or "{}")


def save_report_state(path: str | Path, state: dict[str, str]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))


def report_period_keys(now: datetime) -> tuple[str, str]:
    iso_year, iso_week, _ = now.isocalendar()
    weekly = f"{iso_year}-W{iso_week:02d}"
    monthly = f"{now.year}-{now.month:02d}"
    return weekly, monthly
