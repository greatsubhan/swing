"""Match Discord outcome messages to signal messages using tiered matching logic.

Tier 1: Exact setup_id match (highest confidence → exact_match)
Tier 2: Reply/thread relationship (high confidence → high)
Tier 3: Symbol + timeframe + direction + time proximity (high/medium confidence)
Tier 4: Symbol + timeframe only + narrow window (medium confidence)
Tier 5: No match → unknown
"""
from __future__ import annotations

from datetime import datetime, timezone

from .discord_journal_models import DiscordImportedEntry
from .discord_message_parser import MATCHING_WINDOW_HOURS, DEFAULT_MATCHING_WINDOW_HOURS


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    if not ts:
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, AttributeError):
        return None


def _time_proximity_hours(a: str | None, b: str | None) -> float | None:
    """Compute hours between two ISO timestamps. Returns None if either is missing."""
    dt_a = _parse_timestamp(a)
    dt_b = _parse_timestamp(b)
    if not dt_a or not dt_b:
        return None
    diff = abs((dt_a - dt_b).total_seconds()) / 3600.0
    return diff


def _get_matching_window_hours(strategy_id: str | None) -> float:
    """Get the matching window in hours for a given strategy."""
    if strategy_id and strategy_id in MATCHING_WINDOW_HOURS:
        return MATCHING_WINDOW_HOURS[strategy_id]
    return DEFAULT_MATCHING_WINDOW_HOURS


def match_outcome_to_signals(
    outcome: DiscordImportedEntry,
    signals: list[DiscordImportedEntry],
) -> tuple[DiscordImportedEntry, str | None, str | None]:
    """Try to match an outcome entry to a signal entry.

    Tries tiers 1-5 in order. Returns the outcome with matching fields populated.

    Args:
        outcome: The outcome entry to match
        signals: All signal_entry entries available for matching

    Returns:
        Tuple of (updated outcome, matched_setup_id_or_None, matching_method_or_None)
    """
    # Filter to only signal entries
    trade_signals = [s for s in signals if s.event_type == "signal_entry"]

    # --- Tier 1: Exact setup_id match (highest confidence) ---
    if outcome.setup_id:
        for signal in trade_signals:
            if signal.setup_id and signal.setup_id == outcome.setup_id:
                return (
                    outcome,
                    signal.setup_id,
                    "setup_id_footer",
                )

    # --- Tier 2: Reply/thread relationship (high confidence) ---
    # This would require raw Discord reference data; the importer handles this
    # at a higher level by checking message references before calling this function.
    # Skip here — handled externally.

    # --- Tier 3: Symbol + timeframe + direction + time proximity ---
    window_hours = _get_matching_window_hours(outcome.strategy_id)
    candidates_tier3 = []
    for signal in trade_signals:
        # All three must match
        if not (outcome.symbol and signal.symbol):
            continue
        if outcome.symbol.upper() != signal.symbol.upper():
            continue
        if outcome.timeframe and signal.timeframe and outcome.timeframe.upper() != signal.timeframe.upper():
            continue
        if outcome.direction and signal.direction and outcome.direction.lower() != signal.direction.lower():
            continue
        # Time proximity check
        proximity = _time_proximity_hours(outcome.result_timestamp, signal.signal_timestamp)
        if proximity is None:
            continue
        if proximity <= window_hours:
            candidates_tier3.append((signal, proximity))

    if candidates_tier3:
        # Pick the closest match
        candidates_tier3.sort(key=lambda x: x[1])
        best = candidates_tier3[0]
        # If there's exactly one candidate within tight proximity, high confidence
        if len(candidates_tier3) == 1 or best[1] <= window_hours * 0.5:
            confidence = "high"
        else:
            confidence = "medium"

        return (
            outcome,
            best[0].setup_id,
            f"symbol+timeframe+side+proximity:{confidence}",
        )

    # --- Tier 4: Symbol + timeframe only (no direction) + narrow window ---
    narrow_window = window_hours * 0.25  # Quarter of normal window
    candidates_tier4 = []
    for signal in trade_signals:
        if not (outcome.symbol and signal.symbol):
            continue
        if outcome.symbol.upper() != signal.symbol.upper():
            continue
        if outcome.timeframe and signal.timeframe and outcome.timeframe.upper() != signal.timeframe.upper():
            continue
        proximity = _time_proximity_hours(outcome.result_timestamp, signal.signal_timestamp)
        if proximity is None:
            continue
        if proximity <= narrow_window:
            candidates_tier4.append((signal, proximity))

    if candidates_tier4:
        candidates_tier4.sort(key=lambda x: x[1])
        best = candidates_tier4[0]
        return (
            outcome,
            best[0].setup_id,
            f"symbol+timeframe+proximity:narrow",
        )

    # --- Tier 5: No match ---
    return (outcome, None, None)


def match_all_outcomes(
    entries: list[DiscordImportedEntry],
) -> list[DiscordImportedEntry]:
    """Match all outcome entries against all signal entries in the list.

    This performs a single-pass matching: signals come first, then outcomes
    are matched against the signal list.

    Args:
        entries: All parsed entries (both signals and outcomes)

    Returns:
        Updated entries with matching fields populated on outcome entries
    """
    signals = [e for e in entries if e.event_type == "signal_entry"]
    outcomes = [e for e in entries if e.event_type == "outcome"]
    others = [e for e in entries if e.event_type not in ("signal_entry", "outcome")]

    matched_outcomes = []
    for outcome in outcomes:
        updated_outcome, matched_id, method = match_outcome_to_signals(outcome, signals)
        updated_outcome.matched_to_setup_id = matched_id
        updated_outcome.matching_method = method
        if matched_id:
            updated_outcome.confidence = "exact_match" if method == "setup_id_footer" else "high"
        else:
            updated_outcome.confidence = "unknown"
            updated_outcome.matching_method = "none"
        matched_outcomes.append(updated_outcome)

    # Return all entries in original order
    return signals + matched_outcomes + others