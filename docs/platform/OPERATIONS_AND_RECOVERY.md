# Operations And Recovery

## Operational Modes

The repo supports three practical operating patterns:

| Mode | Command | Use case |
|---|---|---|
| Continuous serve loop | `python -m signal_platform --env-file .env serve --config config/platform.example.json --poll-seconds 30` | Normal always-on route operation |
| One-shot route scan | `python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four` | Manual route run with real route behavior |
| Silent scan | `python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four --dispatch none` | Health check without live alert posting |

For the standalone parabolic project:

| Mode | Command |
|---|---|
| Paper-forward live runner | `python -m parabolic_exhaustion.live.run --profile NAS100_PARABOLIC_PAPER --provider oanda --env-file .env` |
| One-shot scan | `python -m parabolic_exhaustion.live.scan --profile NAS100_PARABOLIC_PAPER --provider oanda --env-file .env` |

## Startup And Watchdog Behavior

### Shared platform startup

[scripts/ensure_signal_platform.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/ensure_signal_platform.ps1) acts like a Windows watchdog helper:

- checks whether the platform runner is already active
- checks whether the Discord command bot should run
- starts missing processes
- writes status details to the console

It also starts the command bot automatically when `DISCORD_BOT_TOKEN` exists in the selected `.env`.

### Startup installers

[scripts/install_signal_platform_startup.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/install_signal_platform_startup.ps1) installs startup automation by:

- creating a Startup-folder launcher
- attempting to register a scheduled task
- falling back gracefully if scheduled task registration fails

### Desktop launchers

Root launchers provide operator-friendly entrypoints:

- [RUN_signal_platform.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform.bat)
- [RUN_signal_platform_command_bot.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform_command_bot.bat)
- [RUN_little_rzy_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_little_rzy_scan.bat)
- [RUN_strategy_two_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_two_scan.bat)
- [RUN_strategy_four_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_four_scan.bat)
- [RUN_strategy_five_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_five_scan.bat)
- [RUN_nas100_parabolic_paper.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_nas100_parabolic_paper.bat)
- [RUN_nas100_parabolic_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_nas100_parabolic_scan.bat)
- [Start All Bots.cmd](/C:/Users/Seeker/Documents/swing-pr1/Start%20All%20Bots.cmd)

## Recovery Logic

Recovery behavior lives in the shared runtime and journal helpers:

- [runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py)
- [journal.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/journal.py)

### What is recovered

For tactical boards that use journals:

- missed TP/SL/BE-style outcome notifications
- recently missed entry signals inside the configured catch-up window
- dedupe state after restart

### Key controls

Per route:

- `catch_up_hours`
- `max_backfill_outcomes_per_run`
- `max_catch_up_entries_per_run`

### How a route cycle behaves

1. load prior sent setup IDs
2. load existing journal if the route is not `managed_events`
3. refresh open entries and detect newly closed outcomes
4. run the strategy scanner
5. separate fresh signals from recovered signals
6. send pending outcomes first
7. send fresh signals
8. send recovered signals
9. update journal and sent state
10. write run summary and health outputs

This order matters because it keeps Discord messaging coherent after downtime.

## Journaling And Outcome Tracking

The platform uses:

- `sent_state.json` for dedupe
- `signal_journal.json` for tactical signal lifecycle tracking
- `report_state.json` for weekly/monthly reporting gates

`JournalEntry` objects store:

- setup id
- symbol
- timeframe
- side
- entry / stop / target
- dispatch timestamp
- outcome
- outcome timestamp
- bars checked
- raw signal payload

Outcome checks use live market data fetched through the existing OANDA fetch path.

## Health Snapshots And Logs

Per route, the platform can write:

| File | Purpose |
|---|---|
| `platform_run_summary.json` | Summary of one route execution |
| `route_cycle_log.csv` | Historical cycle-by-cycle operational log |
| `health_snapshot.json` | Latest operational health snapshot for status surfaces |

Typical health snapshot fields include:

- `last_successful_market_refresh_utc`
- `last_successful_discord_post_utc`
- `signals_found`
- `fresh_signals`
- `recovered_entries_found`
- `recovered_entries_sent`
- `pending_unnotified_outcomes_count`
- `suppressed_duplicates`
- `dispatch_error_count`
- `quiet_reason`

The Discord command bot reads these files to produce `status` responses.

## Output Folder Conventions

### Shared platform

Outputs live under [platform_output](/C:/Users/Seeker/Documents/swing-pr1/platform_output).

Common route files:

- `scan_results.json`
- `alerts.txt`
- `signals.json` for managed-event boards
- `signal_journal.json`
- `sent_state.json`
- `report_state.json`
- `platform_run_summary.json`
- `route_cycle_log.csv`
- `health_snapshot.json`

### Standalone parabolic project

Outputs live under [parabolic-exhaustion-bot/output](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/output).

Important NAS100 paper-forward files include:

- `live_state_transitions.csv`
- `live_trade_log.csv`
- `live_health.csv`
- `discord_alert_log.csv`
- `forward_test_log_parabolic.csv`
- `scan_summary.json`

## Logging

Main root logs:

- [logs/signal_platform.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform.log)
- [logs/signal_platform_command_bot.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform_command_bot.log)
- [logs/parabolic_paper.log](/C:/Users/Seeker/Documents/swing-pr1/logs/parabolic_paper.log)
- [logs/parabolic_scan.log](/C:/Users/Seeker/Documents/swing-pr1/logs/parabolic_scan.log)

These are append-only operational logs and are the first place to check when a launcher exits unexpectedly.

## Reliability Notes

- The shared platform is restart-friendly because it persists sent setup IDs and journals.
- `scan-route --dispatch none` is the safest operational smoke test.
- The command bot uses a lock so concurrent Discord-triggered scans do not overlap.
- The parabolic one-shot scan seeds context silently so it does not replay old transitions into Discord.

## Limitations

- No root-level broker execution path is documented or enabled here.
- Recovery assumes available OANDA history and functioning webhook delivery.
- The parabolic bot is still operationally separate from `signal_platform`.
