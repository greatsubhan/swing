"""Signal journaling, outcome tracking, and report helpers."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
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
    return [JournalEntry(**entry) for entry in payload]


def save_journal(path: str | Path, entries: list[JournalEntry]) -> None:
    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps([entry.to_dict() for entry in entries], indent=2))


def append_new_signals(entries: list[JournalEntry], signals: list[PlatformSignal]) -> list[JournalEntry]:
    existing_ids = {entry.setup_id for entry in entries}
    now = utc_now_iso()
    for signal in signals:
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
    return SignalStatsSnapshot(
        total_signals=total,
        closed_signals=closed,
        open_signals=open_count,
        tp_hits=tp_hits,
        sl_hits=sl_hits,
        other_closures=max(other, 0),
        win_rate=win_rate,
        avg_hold_hours=mean(hold_values) if hold_values else None,
    )


def signal_with_stats(signal: PlatformSignal, stats: SignalStatsSnapshot) -> PlatformSignal:
    enriched = PlatformSignal(**signal.to_dict())
    enriched.raw_signal = {**signal.raw_signal, "stats_snapshot": stats.to_dict()}
    return enriched


def _find_outcome(entry: JournalEntry, token: str | None, environment: str, price: str) -> tuple[str, str, float, int] | None:
    fetched = fetch_oanda_ohlcv(
        instrument=entry.symbol,
        granularity="H4" if entry.timeframe == "4h" else "D" if entry.timeframe == "1d" else "H1",
        start=entry.signal_timestamp,
        end=None,
        price=price,
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
) -> list[JournalEntry]:
    updates: list[JournalEntry] = []
    now = utc_now_iso()
    for entry in entries:
        if entry.status != "open":
            continue
        outcome = _find_outcome(entry, token=token, environment=environment, price=price)
        entry.last_checked_utc = now
        if not outcome:
            updates.append(entry)
            continue
        reason, timestamp, exit_price, bars_checked = outcome
        entry.status = "closed"
        entry.outcome = reason
        entry.outcome_timestamp = timestamp
        entry.exit_price = exit_price
        entry.bars_checked = bars_checked
        updates.append(entry)
    return entries


def unresolved_entries(entries: list[JournalEntry]) -> list[JournalEntry]:
    return [entry for entry in entries if entry.status == "open"]


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
    period_entries = [entry for entry in entries if datetime.fromisoformat(entry.dispatched_at_utc.replace("Z", "+00:00")) >= since_utc]
    resolved = [entry for entry in period_entries if entry.status == "closed"]
    open_count = sum(1 for entry in period_entries if entry.status == "open")
    tp_hits = sum(1 for entry in resolved if entry.outcome == "tp_hit")
    sl_hits = sum(1 for entry in resolved if entry.outcome == "sl_hit")
    holds = [entry.hold_hours() for entry in resolved]
    hold_values = [value for value in holds if value is not None]
    avg_hold = mean(hold_values) if hold_values else None
    avg_hold_text = f"{avg_hold:.1f}h" if avg_hold is not None else "n/a"
    return (
        f"{period_label} report\n"
        f"Signals sent: {len(period_entries)}\n"
        f"Still open: {open_count}\n"
        f"TP hit: {tp_hits}\n"
        f"SL hit: {sl_hits}\n"
        f"Average hold time: {avg_hold_text}"
    )


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
