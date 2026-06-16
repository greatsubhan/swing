# Multi-Strategy Platform

This document describes the shared runtime that powers the live boards in `swing-pr1`.

## Purpose

The platform exists so new strategies do not need to rebuild:

- scheduling
- route configuration
- Discord dispatch
- duplicate suppression
- journaling
- outcome tracking
- recovery after downtime
- health snapshots and cycle logs

The core idea is simple:

- many strategies
- one runtime
- one route model
- one Discord delivery layer

## Core Files

| File | Responsibility |
|---|---|
| [signal_platform/__main__.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/__main__.py) | CLI entrypoint |
| [signal_platform/runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py) | Route execution, dispatch, health snapshots, and summaries |
| [signal_platform/registry.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/registry.py) | Registered strategy adapters |
| [signal_platform/strategies.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/strategies.py) | Strategy plugin interface and scan request model |
| [signal_platform/models.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/models.py) | Shared signal and journal data models |
| [signal_platform/reinforcement.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/reinforcement.py) | Structure tracking, root-signal detection, and reinforcement updates |
| [signal_platform/dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py) | Discord payload formatting and webhook sending |
| [signal_platform/journal.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/journal.py) | Signal journals, outcome refresh, stats snapshots, and report summaries |
| [signal_platform/command_content.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/command_content.py) | Inbound command bot content and status and recent views |
| [signal_platform/discord_command_bot.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/discord_command_bot.py) | Lightweight inbound Discord command bot |

## Registered Routes

| Strategy ID | Name | Managed events? | Notes |
|---|---|---:|---|
| `little_rzy` | Measured Drift | No | Tactical 4h route |
| `little_rzy_1h` | Measured Drift 1H | No | Research-only 1h route |
| `strategy_two` | Trend Current | Yes | Basket lifecycle board |
| `strategy_four` | Cambist With Trend | No | Tactical CWT route |
| `strategy_five` | Secular Bull SIP | Yes | Monthly allocation and review board |

## Route Configuration Model

Routes are defined in [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json).

Each route config controls:

- strategy selection
- watchlist
- timeframe
- dispatch mode
- output paths
- journaling and reporting paths
- catch-up behavior
- health and log file locations

Common route fields:

- `strategy_id`
- `enabled`
- `watchlist`
- `granularity`
- `higher_timeframe`
- `interval_minutes`
- `dispatch`
- `discord_webhook_url`
- `output_dir`
- `state_file`
- `journal_file`
- `report_state_file`
- `catch_up_hours`
- `max_backfill_outcomes_per_run`
- `max_catch_up_entries_per_run`
- `health_log_file`
- `health_snapshot_file`
- `reinforcement_state_file`
- `reinforcement_log_file`
- `extra.signal_reinforcement.*`

## Data Sources and External Integrations

Main external integrations:

- OANDA for tactical live route market data
- Discord webhooks for outbound message delivery
- Discord bot token and gateway connection for inbound text commands

Important distinction:

- outbound strategy alerts are webhook-based
- inbound user commands go through the lightweight command bot

## Runtime Lifecycle

When the runtime executes a route, the flow is:

1. Load the route config.
2. Resolve the route adapter from the registry.
3. Refresh the route journal if the strategy is tactical.
4. Run the scanner through the route adapter.
5. Normalize scanner output into `PlatformSignal` objects.
6. Compare signals against `sent_state.json`.
7. Optionally collapse duplicate same-structure signals into:
   - one root signal
   - reinforcement updates
8. Recover unnotified outcomes from the journal.
9. Recover recent missed entries inside the catch-up window.
10. Dispatch outcomes first, then fresh entries, then recovered entries.
11. Append newly dispatched tradable signals to the journal.
12. Write `platform_run_summary.json`.
13. Write `health_snapshot.json` and append `route_cycle_log.csv`.

## Reinforcement Layer

The platform now supports a structure-aware reinforcement layer for tactical routes.

Current production use:

- `strategy_four` / CWT

Behavior:

- first signal in a structure stays tradable
- later same-structure signals become reinforcement updates
- reinforcements can still be sent to Discord
- only root signals are journaled as trades

Persistent files:

- `reinforcement_state.json`
- `reinforcement_decisions.jsonl`

Data model impact:

- `PlatformSignal` now carries:
  - `is_tradable`
  - `structure_id`
  - `root_signal_id`
  - `reinforcement_count`
  - `strength_score`
- `JournalEntry` stores root-structure references for tradable signals

See:

- [SIGNAL_REINFORCEMENT_SYSTEM.md](/C:/Users/Seeker/Documents/swing-pr1/docs/SIGNAL_REINFORCEMENT_SYSTEM.md)

## Scanner Integration

The platform does not implement the strategy logic itself. Each adapter wraps a scanner from the underlying strategy package.

Examples:

- [signal_platform/little_rzy_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/little_rzy_strategy.py)
  wraps [little_rzy_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/scanner.py)
- [signal_platform/trend_current_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/trend_current_strategy.py)
  wraps [strategy_two_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot/scanner.py)
- [signal_platform/cwt_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/cwt_strategy.py)
  wraps [strategy_four_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_four_bot/scanner.py)
- [signal_platform/secular_bull_sip_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/secular_bull_sip_strategy.py)
  wraps [strategy_five_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_five_bot/scanner.py)

## Discord Delivery

Outbound delivery is webhook-based.

The dispatcher layer currently supports:

- tactical entry, add, stop, and basket-exit cards
- outcome cards
- weekly and monthly report cards
- SIP allocation cards
- SIP review cards
- generic text payloads

Route behavior:

- tactical routes use journals and outcome tracking
- managed-event routes post stateful event cards but do not rely on TP and SL journals in the same way

## Journaling and Outcome Tracking

Tactical routes use a persistent journal file, typically:

- `platform_output/<route>/signal_journal.json`

The journal stores:

- signal identity
- entry, stop, and target values
- status (`open` or `closed`)
- closure outcome (`tp_hit`, `sl_hit`, `break_even`, and similar)
- whether the outcome notification was already sent
- structure references for root signals

This enables:

- TP, SL, and break-even Discord updates
- later performance summaries
- current route stats snapshots
- recovery of missed closure notifications after downtime
- clean trade counts even when reinforcement updates are sent live

## Recovery and Catch-Up Logic

The runtime now supports two important recovery paths.

### Missed outcomes

Any closed journal entry with:

- `status = closed`
- `outcome_notified = false`

is eligible to be posted on the next healthy route cycle.

### Recent missed entries

For tactical routes, recent missed entries can be recovered inside the route's `catch_up_hours` window.

Important boundaries:

- only recent entries are recovered
- old historical floods are not replayed
- duplicate suppression still applies

## Health and Observability

Each route writes:

- `platform_run_summary.json`
- `health_snapshot.json`
- `route_cycle_log.csv`

These files make it easier to distinguish:

- no market setup
- duplicate suppression
- pending missed outcomes
- recent recovered entries
- actual dispatch failures

Useful health fields:

- `signals_found`
- `tradable_signals`
- `reinforcement_signals`
- `fresh_signals`
- `recovered_entries_found`
- `recovered_entries_sent`
- `reinforcements_sent`
- `pending_unnotified_outcomes_count`
- `outcomes_sent`
- `suppressed_duplicates`
- `dispatch_error_count`
- `quiet_reason`
- `last_successful_market_refresh_utc`
- `last_successful_discord_post_utc`

## CLI Commands

Main platform commands:

```powershell
python -m signal_platform --env-file .env list-strategies
python -m signal_platform --env-file .env run-config --config config/platform.example.json
python -m signal_platform --env-file .env serve --config config/platform.example.json --poll-seconds 30
python -m signal_platform --env-file .env scan --strategy little_rzy --watchlist primary-4h --granularity H4 --higher-timeframe 1d --out platform_output/little_rzy_check
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four --dispatch none --catch-up-hours 6
python -m signal_platform --env-file .env command-bot --config config/platform.example.json
python -m signal_platform --env-file .env test-discord --strategy strategy_four
```

## Command Bot

The inbound Discord command bot is intentionally lightweight. It currently supports:

- `boards`
- `strategy`
- `strategy <board>`
- `status`
- `status <board>`
- `recent`
- `recent <board>`
- `scan`
- `scan <board>`
- `help`

What it does well:

- board explainers
- health snapshots
- latest recorded activity
- safe one-shot scans

What it does not do:

- place trades
- manage positions in Discord
- replace the outbound webhook delivery path

## Managed Events vs Tactical Routes

There are two route styles in the platform.

### Tactical routes

Examples:

- `little_rzy`
- `little_rzy_1h`
- `strategy_four`

Characteristics:

- journal-backed
- entry and outcome lifecycle
- TP, SL, and break-even follow-ups
- report cards

### Managed-event routes

Examples:

- `strategy_two`
- `strategy_five`

Characteristics:

- state and event board
- not purely TP and SL driven
- basket lifecycle or monthly allocation and review logic

## Known Limitations

- The platform is Discord-first. It does not include live broker execution.
- Some strategy docs and research artifacts are more mature than others.
- The command bot is not a slash-command application.
- `little_rzy_1h` is available but remains research-only.
- `parabolic-exhaustion-bot` is not yet folded into this shared runtime.
