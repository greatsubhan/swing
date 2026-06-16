"""CLI entry point for Discord journal import pipeline.

Usage:
    python scripts/run_discord_import.py --mode backfill
    python scripts/run_discord_import.py --mode incremental
    python scripts/run_discord_import.py --mode reprocess
    python scripts/run_discord_import.py --mode summary
    python scripts/run_discord_import.py --mode offline --input-dir path/to/raw/exports

Environment variables:
    DISCORD_BOT_TOKEN               — Bot token for API access
    DISCORD_IMPORT_CHANNEL_IDS      — Comma-separated channel IDs
    DISCORD_IMPORT_CHANNEL_MAP      — JSON mapping channel_id → strategy_id
    DISCORD_IMPORT_OUTPUT_DIR       — Output directory (default: platform_output)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import os
# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env if present
for line in open('.env').readlines() if os.path.exists('.env') else []:
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())

import os as _os  # ensure os is available after .env load
from signal_platform.discord_importer import run_import, compute_imported_metrics
from signal_platform.discord_journal_models import (
    load_import_state,
    load_imported_entries,
    DiscordImportedEntry,
)
from signal_platform.discord_message_parser import parse_discord_message


def cmd_import(args: argparse.Namespace) -> None:
    """Run import from Discord API or local files."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    channel_ids = None
    if args.channels:
        channel_ids = [c.strip() for c in args.channels.split(",")]

    token = args.token
    output_dir = args.output_dir

    if args.mode == "offline":
        # Import from local JSON files (no Discord API needed)
        _cmd_offline_import(args)
        return

    summaries = run_import(
        channel_ids=channel_ids,
        output_dir=output_dir,
        mode=args.mode,
        token=token,
    )

    # Print summary
    total_fetched = sum(s.messages_fetched for s in summaries)
    total_new = sum(s.new_messages for s in summaries)
    total_parsed = sum(s.events_parsed for s in summaries)
    total_matched = sum(s.outcomes_matched for s in summaries)
    total_unmatched = sum(s.outcomes_unmatched for s in summaries)

    print("\n" + "=" * 60)
    print("DISCORD IMPORT SUMMARY")
    print("=" * 60)
    print(f"Mode:           {args.mode}")
    print(f"Channels:       {len(summaries)}")
    print(f"Messages fetched: {total_fetched}")
    print(f"New messages:   {total_new}")
    print(f"Events parsed:  {total_parsed}")
    print(f"Outcomes matched: {total_matched}")
    print(f"Outcomes unmatched: {total_unmatched}")

    for s in summaries:
        print(f"\n  Channel: {s.route}")
        print(f"    Events by type: {s.events_by_type}")
        print(f"    Confidence: {s.confidence_breakdown}")
        if s.errors:
            print(f"    Errors: {s.errors}")

    print("=" * 60)


def _cmd_offline_import(args: argparse.Namespace) -> None:
    """Import from local JSON files (exported from Discord or saved by the importer)."""
    input_dir = Path(args.input_dir or "discord_exports")
    output_dir = Path(args.output_dir or "platform_output")
    route_id = args.route_id or "unknown"

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Find all JSON files in the input directory
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        sys.exit(1)

    # Parse each file as a message
    entries = []
    archives = []
    for jf in sorted(json_files):
        try:
            data = json.loads(jf.read_text())
            if isinstance(data, list):
                messages = data
            elif isinstance(data, dict) and "messages" in data:
                messages = data["messages"]
            else:
                messages = [data]

            for msg in messages:
                channel_id = msg.get("channel_id", "unknown")
                channel_name = msg.get("channel_name", route_id)
                entry, archive = parse_discord_message(msg, channel_id, channel_name)
                if entry:
                    entries.append(entry)
                archives.append(archive)
        except (json.JSONDecodeError, Exception) as exc:
            print(f"Warning: Could not parse {jf}: {exc}")

    # Run matching
    from signal_platform.discord_outcome_matcher import match_all_outcomes
    matched_entries = match_all_outcomes(entries)

    # Save
    import_path = output_dir / route_id / "discord_import_journal.json"
    archive_path = output_dir / route_id / "discord_raw_archive.jsonl"

    from signal_platform.discord_journal_models import save_imported_entries, append_raw_archive
    save_imported_entries(import_path, matched_entries)
    append_raw_archive(archive_path, archives)

    print(f"\nSaved {len(matched_entries)} entries to {import_path}")
    print(f"Saved {len(archives)} raw messages to {archive_path}")

    # Print breakdown
    events = {}
    for e in matched_entries:
        events[e.event_type] = events.get(e.event_type, 0) + 1
    print(f"Events: {events}")


def cmd_summary(args: argparse.Namespace) -> None:
    """Print current import state and metrics."""
    output_dir = Path(args.output_dir)
    state_path = output_dir / "_discord_import_state.json"
    state = load_import_state(state_path)

    print("\n" + "=" * 60)
    print("DISCORD IMPORT STATE")
    print("=" * 60)
    print(f"Last sync:          {state.last_sync_utc or 'never'}")
    print(f"Total imported IDs:  {state.total_imported_records}")
    print(f"Matched outcomes:    {state.total_matched_outcomes}")
    print(f"Unmatched outcomes:  {state.total_unmatched_outcomes}")

    if state.last_imported_message_id_per_channel:
        print("\nChannel sync state:")
        for ch_id, msg_id in state.last_imported_message_id_per_channel.items():
            print(f"  {ch_id}: last_message_id={msg_id}")

    # Per-route metrics
    print("\nPer-route discord-imported metrics:")
    for route_dir in sorted(output_dir.iterdir()):
        if route_dir.is_dir() and (route_dir / "discord_import_journal.json").exists():
            metrics = compute_imported_metrics(route_dir.name, str(output_dir))
            print(f"\n  {route_dir.name}:")
            print(f"    Total signals:  {metrics['total']}")
            print(f"    Closed:         {metrics['closed']}")
            print(f"    Open:           {metrics['open']}")
            print(f"    TP:             {metrics['tp']}")
            print(f"    SL:             {metrics['sl']}")
            print(f"    Win rate:       {metrics['win_rate']}%")
            print(f"    Net R:          {metrics['net_r']}")
            print(f"    Unmatched:      {metrics['unmatched']}")
            print(f"    Matched:        {metrics['matched_outcomes']}")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discord Journal Import Pipeline",
    )
    parser.add_argument(
        "--mode",
        choices=["backfill", "incremental", "reprocess", "summary", "offline"],
        default="incremental",
        help="Import mode (default: incremental)",
    )
    parser.add_argument(
        "--channels",
        type=str,
        default=None,
        help="Comma-separated Discord channel IDs",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Discord bot token (or set DISCORD_BOT_TOKEN env var)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: DISCORD_IMPORT_OUTPUT_DIR env or platform_output)",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Input directory for offline mode (local JSON exports)",
    )
    parser.add_argument(
        "--route-id",
        type=str,
        default=None,
        help="Strategy route ID for offline mode",
    )

    args = parser.parse_args()
    if not args.output_dir:
        args.output_dir = __import__("os").environ.get("DISCORD_IMPORT_OUTPUT_DIR", "platform_output")

    if args.mode == "summary":
        cmd_summary(args)
    else:
        cmd_import(args)


if __name__ == "__main__":
    main()