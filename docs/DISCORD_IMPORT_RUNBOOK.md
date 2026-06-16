# Discord Import Runbook

## Overview

The Discord journal import pipeline pulls historical signal and outcome messages from Discord channels, parses them into structured journal records, and integrates them into the dashboard metrics pipeline with full provenance tracking.

## Prerequisites

- Python 3.11+
- `aiohttp` package (for Discord API fetch): `pip install aiohttp`
- Discord bot token with `message_history` permission
- Channel IDs for each strategy's signal channel

## Environment Variables

```bash
# Required
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_IMPORT_CHANNEL_IDS=123456789012345678,987654321098765432

# Optional: map channels to strategy routes
DISCORD_IMPORT_CHANNEL_MAP={"123456789012345678":"strategy_four","987654321098765432":"strategy_two"}

# Optional: output directory (default: platform_output)
DISCORD_IMPORT_OUTPUT_DIR=platform_output
```

## Commands

### Initial Backfill (first run)
```bash
python scripts/run_discord_import.py --mode backfill
```
Fetches ALL historical messages from configured channels.

### Incremental Sync (daily/periodic)
```bash
python scripts/run_discord_import.py --mode incremental
```
Fetches only messages newer than the last imported message ID per channel.

### Reprocess (after parser improvements)
```bash
python scripts/run_discord_import.py --mode reprocess
```
Clears existing import files and reruns full backfill. Uses raw archive for reprocessing.

### Offline Import (from exported JSON files)
```bash
python scripts/run_discord_import.py --mode offline --input-dir path/to/exports --route-id strategy_four
```
Import from local JSON files without Discord API access. The JSON files should contain message dicts in Discord API format.

### View Import Summary
```bash
python scripts/run_discord_import.py --mode summary
```

### Rebuild Dashboard Metrics
```bash
cd bot-dashboard && python import_journal.py
```

### Validate Import
```bash
python scripts/validate_discord_import.py
```

## Output Files

| File | Description |
|------|-------------|
| `platform_output/{route}/discord_import_journal.json` | Normalized imported records with provenance |
| `platform_output/{route}/discord_raw_archive.jsonl` | Raw Discord message payloads (append-only) |
| `platform_output/_discord_import_state.json` | Global sync state for incremental updates |
| `platform_output/_dashboard_metrics.json` | Triple-view metrics (native + discord + combined) |

## Metric Views

Each route's dashboard metrics contain three views:

- **`native_journal`** — Records from `signal_journal.json` (runtime-generated)
- **`discord_imported`** — Records from `discord_import_journal.json` (Discord-imported)
- **`combined`** — Merged totals with `native_count` and `discord_imported_count` fields

## Matching Logic

Outcomes are matched to signals using tiered rules:

1. **Exact setup_id** (highest confidence) — From footer text
2. **Reply/thread relationship** (high confidence) — Discord message references
3. **Symbol + timeframe + direction + time proximity** (high/medium) — Per-strategy windows
4. **Symbol + timeframe + narrow window** (medium) — Quarter of normal window
5. **No match** → marked as `unknown`

Per-strategy matching windows:
- `strategy_four` (M5): ±2h
- `little_rzy` (H4): ±24h
- `strategy_two` (H4): ±48h
- `strategy_five` (D): ±96h

## Troubleshooting

### "No Discord bot token available"
Set `DISCORD_BOT_TOKEN` environment variable.

### "No Discord channel IDs configured"
Set `DISCORD_IMPORT_CHANNEL_IDS` as comma-separated channel IDs.

### Rate limiting (HTTP 429)
The importer handles rate limits automatically by waiting for the `retry_after` period.

### "No new messages" on second run
This is expected — deduplication is working. Only new messages are imported.

### Discord-imported totals don't match dashboard
Rebuild dashboard: `cd bot-dashboard && python import_journal.py`
Then validate: `python scripts/validate_discord_import.py`

## Provenance Rules

Every imported record preserves:
- `imported_from: "discord"` — Fixed source identifier
- `imported_at` — ISO timestamp of import run
- `parser_version` — Parser version used
- `raw_message_ids` — Original Discord message IDs
- `source_channel_id` / `source_channel_name` — Discord channel
- `confidence` — Match confidence level
- `event_type` — Message classification

Discord-imported records are NEVER silently merged with native journal records. The dashboard always distinguishes native, discord-imported, and combined totals.