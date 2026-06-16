"""Discord journal import pipeline — orchestration module.

Connects to Discord, fetches message history from configured channels,
parses signals and outcomes, matches outcomes to signals, and persists
normalized journal records + raw archive.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .discord_journal_models import (
    DiscordImportState,
    DiscordImportSummary,
    MergedRouteMetrics,
    RawMessageArchive,
    append_raw_archive,
    load_import_state,
    load_imported_entries,
    load_raw_archive_ids,
    save_import_state,
    save_imported_entries,
)
from .discord_message_parser import (
    STRATEGY_ID_TO_NAME,
    STRATEGY_NAME_MAP,
    parse_discord_message,
    parse_discord_messages,
)
from .discord_outcome_matcher import match_all_outcomes

logger = logging.getLogger(__name__)

# --- Channel-to-route mapping ---
# These map Discord channel IDs/names to strategy routes.
# Configured via env var DISCORD_IMPORT_CHANNEL_MAP as JSON:
# {"channel_id_or_name": "strategy_id"} or set individually.
# Fallback: channel name is matched against strategy names.

DEFAULT_CHANNEL_ROUTE_MAP: dict[str, str] = {}


def _load_channel_route_map() -> dict[str, str]:
    """Load channel → strategy_id mapping from environment."""
    raw = os.environ.get("DISCORD_IMPORT_CHANNEL_MAP", "")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            logger.warning("Invalid DISCORD_IMPORT_CHANNEL_MAP JSON, using defaults")
    return dict(DEFAULT_CHANNEL_ROUTE_MAP)


def _infer_route_from_channel_name(channel_name: str) -> str | None:
    """Try to infer strategy_id from channel name."""
    lower = channel_name.lower()
    # Common Discord channel naming patterns
    mappings = {
        "cwt": "strategy_four",
        "strategy-four": "strategy_four",
        "strategy_four": "strategy_four",
        "measured-drift": "little_rzy",
        "little-rzy": "little_rzy",
        "little_rzy": "little_rzy",
        "trend-current": "strategy_two",
        "trend_current": "strategy_two",
        "strategy-two": "strategy_two",
        "strategy_two": "strategy_two",
        "secular-bull": "strategy_five",
        "secular_bull": "strategy_five",
        "strategy-five": "strategy_five",
        "strategy_five": "strategy_five",
        "sip": "strategy_five",
    }
    for pattern, route in mappings.items():
        if pattern in lower:
            return route
    return None


def _fetch_messages_from_discord(
    channel_ids: list[str],
    token: str | None = None,
    after_id: str | None = None,
    limit: int = 10000,
) -> dict[str, list[dict]]:
    """Fetch messages from Discord channels using discord.py REST API.

    This uses the discord HTTP client directly (not the bot event loop)
    so it can be called from a synchronous script.

    Args:
        channel_ids: List of channel ID strings
        token: Discord bot token
        after_id: Message ID to fetch after (for incremental sync)
        limit: Max messages per channel

    Returns:
        Dict mapping channel_id → list of message dicts
    """
    if not token:
        token = os.environ.get("DISCORD_BOT_TOKEN", "")

    if not token:
        logger.error("No Discord bot token available. Set DISCORD_BOT_TOKEN env var.")
        return {}

    results: dict[str, list[dict]] = {}

    try:
        import aiohttp
        import asyncio

        async def _fetch_all():
            """Async fetch from all channels."""
            headers = {
                "Authorization": f"Bot {token}",
                "User-Agent": "SignalPlatformImporter/1.0",
            }
            async with aiohttp.ClientSession() as session:
                for channel_id in channel_ids:
                    messages = []
                    after = after_id
                    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

                    while True:
                        params: dict[str, str | int] = {"limit": min(limit - len(messages), 100)}
                        if after:
                            params["after"] = after

                        async with session.get(url, headers=headers, params=params) as resp:
                            if resp.status == 429:
                                # Rate limited — wait and retry
                                data = await resp.json()
                                retry_after = data.get("retry_after", 1.0)
                                await asyncio.sleep(retry_after + 0.1)
                                continue
                            if resp.status != 200:
                                logger.error(
                                    "Discord API error for channel %s: HTTP %d",
                                    channel_id, resp.status,
                                )
                                break
                            batch = await resp.json()

                        if not batch:
                            break

                        # Discord returns newest first; we want oldest first
                        batch.sort(key=lambda m: int(m.get("id", "0")))
                        messages.extend(batch)
                        after = batch[-1].get("id", "")

                        if len(messages) >= limit:
                            break
                        if len(batch) < 100:
                            # Fewer than requested = no more messages
                            break

                    # Sort by timestamp (oldest first)
                    messages.sort(key=lambda m: m.get("timestamp", ""))
                    results[channel_id] = messages
                    logger.info(
                        "Fetched %d messages from channel %s",
                        len(messages), channel_id,
                    )

        # Run the async fetch
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning("Event loop already running; cannot fetch Discord messages synchronously.")
                logger.info("Use 'run --mode backfill' from a terminal outside the event loop.")
                return results
            loop.run_until_complete(_fetch_all())
        except RuntimeError:
            asyncio.run(_fetch_all())

    except ImportError as exc:
        logger.error(
            "Discord fetch requires aiohttp. Install with: pip install aiohttp\n%s",
            exc,
        )

    return results


def import_from_channel_messages(
    channel_id: str,
    channel_name: str,
    route_id: str,
    messages: list[dict],
    state: DiscordImportState,
    output_dir: str | Path,
) -> tuple[DiscordImportSummary, DiscordImportState]:
    """Parse, match, and persist imported messages for a single channel/route.

    Returns:
        Tuple of (summary, updated_state)
    """
    now = datetime.now(timezone.utc).isoformat()
    summary = DiscordImportSummary(
        started_at_utc=now,
        route=route_id,
    )

    archive_path = Path(output_dir) / f"{route_id}" / "discord_raw_archive.jsonl"
    import_journal_path = Path(output_dir) / f"{route_id}" / "discord_import_journal.json"

    # Load existing imported entries for this route
    existing_entries = load_imported_entries(import_journal_path)
    existing_message_ids = set(state.imported_message_ids)

    # Load raw archive IDs for deduplication
    raw_archive_ids = load_raw_archive_ids(archive_path)

    # Filter out already-imported messages
    new_messages = []
    for msg in messages:
        msg_id = str(msg.get("id", ""))
        if msg_id in raw_archive_ids or msg_id in existing_message_ids:
            summary.messages_already_imported += 1
            continue
        new_messages.append(msg)

    summary.messages_fetched = len(messages)
    summary.new_messages = len(new_messages)

    if not new_messages:
        summary.finished_at_utc = datetime.now(timezone.utc).isoformat()
        return summary, state

    # Parse all new messages
    parsed = parse_discord_messages(new_messages, channel_id, channel_name)

    # Separate entries and archives
    entries = []
    archives = []
    for entry, archive in parsed:
        if entry:
            entries.append(entry)
        archives.append(archive)

    # Match outcomes to signals
    matched_entries = match_all_outcomes(entries)

    # Add imported_at timestamp to all
    for entry in matched_entries:
        entry.imported_at = now

    # Count events by type
    for entry in matched_entries:
        summary.events_by_type[entry.event_type] = summary.events_by_type.get(entry.event_type, 0) + 1
        summary.events_parsed += 1
        conf = entry.confidence
        summary.confidence_breakdown[conf] = summary.confidence_breakdown.get(conf, 0) + 1

    # Count matched/unmatched outcomes
    outcomes = [e for e in matched_entries if e.event_type == "outcome"]
    for outcome in outcomes:
        if outcome.matched_to_setup_id:
            summary.outcomes_matched += 1
        else:
            summary.outcomes_unmatched += 1

    # Merge with existing entries (append new, deduplicate by raw_message_ids)
    existing_msg_ids_seen = set()
    all_msg_ids = set()
    merged = []

    for entry in existing_entries:
        for mid in entry.raw_message_ids:
            if mid not in existing_msg_ids_seen:
                merged.append(entry)
                existing_msg_ids_seen.add(mid)
                all_msg_ids.add(mid)
                break
        else:
            merged.append(entry)

    for entry in matched_entries:
        for mid in entry.raw_message_ids:
            if mid not in all_msg_ids:
                merged.append(entry)
                all_msg_ids.add(mid)
                break

    # Save
    save_imported_entries(import_journal_path, merged)
    append_raw_archive(archive_path, archives)

    # Update state
    last_id = str(messages[-1].get("id", "")) if messages else ""
    if last_id:
        state.last_imported_message_id_per_channel[channel_id] = last_id

    for entry in matched_entries:
        for mid in entry.raw_message_ids:
            state.imported_message_ids.append(mid)

    state.last_sync_utc = datetime.now(timezone.utc).isoformat()
    state.total_imported_records = len(state.imported_message_ids)
    outcomes_all = [e for e in merged if e.event_type == "outcome"]
    state.total_matched_outcomes = sum(1 for e in outcomes_all if e.matched_to_setup_id)
    state.total_unmatched_outcomes = sum(1 for e in outcomes_all if not e.matched_to_setup_id)

    summary.finished_at_utc = datetime.now(timezone.utc).isoformat()
    summary.errors = []

    return summary, state


def run_import(
    channel_ids: list[str] | None = None,
    output_dir: str = "platform_output",
    mode: str = "incremental",
    token: str | None = None,
) -> list[DiscordImportSummary]:
    """Run the Discord import pipeline.

    Args:
        channel_ids: List of Discord channel IDs to import from.
                     If None, reads from DISCORD_IMPORT_CHANNEL_IDS env var.
        output_dir: Root output directory for platform_output
        mode: "backfill" (full), "incremental" (since last sync), "reprocess" (clear + full)
        token: Discord bot token (or read from DISCORD_BOT_TOKEN env var)

    Returns:
        List of import summaries, one per channel
    """
    if not channel_ids:
        raw_ids = os.environ.get("DISCORD_IMPORT_CHANNEL_IDS", "")
        if raw_ids:
            channel_ids = [cid.strip() for cid in raw_ids.split(",") if cid.strip()]

    if not channel_ids:
        logger.warning("No Discord channel IDs configured. Set DISCORD_IMPORT_CHANNEL_IDS env var.")
        return []

    output_path = Path(output_dir)
    state_path = output_path / "_discord_import_state.json"
    state = load_import_state(state_path)

    # Load channel route mapping
    channel_map = _load_channel_route_map()

    # Fetch messages from Discord
    after_id = None
    if mode == "incremental":
        # For incremental, we fetch after the most recent message per channel
        if state.last_imported_message_id_per_channel:
            # Use the minimum of all channel last-ids to avoid missing messages
            # Actually, for incremental, we should use after for each channel individually
            pass

    messages_by_channel = _fetch_messages_from_discord(
        channel_ids,
        token=token,
        after_id=after_id if mode == "incremental" else None,
    )

    summaries = []
    for channel_id in channel_ids:
        # Determine route for this channel
        route_id = channel_map.get(channel_id)
        if not route_id:
            # Try to infer from channel name (would need to fetch channel info)
            route_id = "unknown"

        messages = messages_by_channel.get(channel_id, [])
        if not messages:
            logger.info("No messages for channel %s", channel_id)
            continue

        # If reprocessing, clear the state for this route
        if mode == "reprocess":
            route_journal = output_path / route_id / "discord_import_journal.json"
            route_archive = output_path / route_id / "discord_raw_archive.jsonl"
            if route_journal.exists():
                route_journal.unlink()
            if route_archive.exists():
                route_archive.unlink()
            # Remove from state
            if channel_id in state.last_imported_message_id_per_channel:
                del state.last_imported_message_id_per_channel[channel_id]

        summary, state = import_from_channel_messages(
            channel_id=channel_id,
            channel_name=route_id,
            route_id=route_id,
            messages=messages,
            state=state,
            output_dir=output_dir,
        )
        summaries.append(summary)
        logger.info(
            "Import summary for %s: fetched=%d, new=%d, parsed=%d, matched=%d, unmatched=%d",
            route_id, summary.messages_fetched, summary.new_messages,
            summary.events_parsed, summary.outcomes_matched, summary.outcomes_unmatched,
        )

    # Save global state
    save_import_state(state_path, state)

    return summaries


def compute_imported_metrics(
    route_id: str,
    output_dir: str = "platform_output",
) -> dict[str, Any]:
    """Compute metrics from discord_import_journal.json for a specific route.

    Returns dict matching the discord_imported section of the dashboard metrics.
    """
    from statistics import mean

    import_path = Path(output_dir) / route_id / "discord_import_journal.json"
    entries = load_imported_entries(import_path)

    if not entries:
        return {
            "source": "discord_imported",
            "total": 0,
            "closed": 0,
            "open": 0,
            "tp": 0,
            "sl": 0,
            "be": 0,
            "win_rate": 0.0,
            "net_r": 0.0,
            "avg_r": 0.0,
            "profit_factor": None,
            "symbols": [],
            "unmatched": 0,
            "matched_outcomes": 0,
            "file": str(import_path),
            "last_sync_utc": "",
        }

    # Filter to trade-relevant entries (signal_entry + outcome)
    trade_entries = [e for e in entries if e.event_type in ("signal_entry", "outcome")]
    signals = [e for e in entries if e.event_type == "signal_entry"]
    outcomes = [e for e in entries if e.event_type == "outcome"]

    # Closed = outcomes that are matched
    closed_outcomes = [e for e in outcomes if e.matched_to_setup_id and e.result_status in ("tp", "sl")]
    open_signals = [e for e in signals if e.result_status == "open"]

    tp_count = sum(1 for e in closed_outcomes if e.result_status == "tp")
    sl_count = sum(1 for e in closed_outcomes if e.result_status == "sl")

    # Realized R
    r_vals = []
    for e in closed_outcomes:
        if e.realized_r is not None:
            r_vals.append(e.realized_r)
        elif e.result_status == "tp":
            r_vals.append(e.risk_reward if e.risk_reward else 1.0)
        elif e.result_status == "sl":
            r_vals.append(-1.0)

    net_r = sum(r_vals) if r_vals else 0.0
    avg_r = mean(r_vals) if r_vals else 0.0
    win_rate = (tp_count / len(closed_outcomes) * 100) if closed_outcomes else 0.0

    wins = [r for r in r_vals if r > 0]
    losses = [r for r in r_vals if r < 0]
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None

    symbols = sorted(set(e.symbol for e in entries if e.symbol))

    matched_count = sum(1 for e in outcomes if e.matched_to_setup_id)
    unmatched_count = sum(1 for e in outcomes if not e.matched_to_setup_id)

    # Get last sync from state
    state_path = Path(output_dir) / "_discord_import_state.json"
    state = load_import_state(state_path)
    last_sync = state.last_sync_utc

    return {
        "source": "discord_imported",
        "total": len(trade_entries),
        "closed": len(closed_outcomes),
        "open": len(open_signals),
        "tp": tp_count,
        "sl": sl_count,
        "be": 0,
        "win_rate": round(win_rate, 1),
        "net_r": round(net_r, 2),
        "avg_r": round(avg_r, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "symbols": symbols,
        "unmatched": unmatched_count,
        "matched_outcomes": matched_count,
        "file": str(import_path),
        "last_sync_utc": last_sync,
    }


# Need to import Any for compute_imported_metrics return type
from typing import Any