# Launch and Operations Runbook

This file covers the practical operational side of `swing-pr1`: how the bots are started, how to keep them running, and where to look when something feels quiet or broken.

## Operational Modes

There are three common ways to run the project:

### 1. One-shot scan

Best for:

- checking one route now
- forcing a manual recovery pass
- troubleshooting

Examples:

```powershell
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy little_rzy
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four --dispatch none --catch-up-hours 6
```

### 2. Continuous platform runner

Best for:

- keeping all enabled routes alive
- normal Discord alert delivery
- automatic outcome posting

Example:

```powershell
python -m signal_platform --env-file .env serve --config config/platform.example.json --poll-seconds 30
```

### 3. Inbound command bot

Best for:

- getting board explainers
- checking current route health
- running silent scans from Discord

Example:

```powershell
python -m signal_platform --env-file .env command-bot --config config/platform.example.json
```

## Windows Launchers

Top-level launchers:

- [RUN_signal_platform.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform.bat)
- [RUN_signal_platform_command_bot.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform_command_bot.bat)
- [Start All Bots.cmd](/C:/Users/Seeker/Documents/swing-pr1/Start%20All%20Bots.cmd)

The current recommended desktop entrypoint is:

- [Start All Bots.cmd](/C:/Users/Seeker/Documents/swing-pr1/Start%20All%20Bots.cmd)

That path delegates to the watchdog:

- [scripts/ensure_signal_platform.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/ensure_signal_platform.ps1)

## Watchdog Behavior

The watchdog:

- checks whether the main signal platform runner is alive
- checks whether the Discord command bot is alive
- starts them if they are not already running
- skips the command bot cleanly if `DISCORD_BOT_TOKEN` is not set

Useful usage:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ensure_signal_platform.ps1 -StatusOnly
```

## Startup Automation

Current startup helper:

- [scripts/install_signal_platform_startup.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/install_signal_platform_startup.ps1)

The current Windows pattern is:

- start at login via the startup-folder launcher
- use the watchdog to make sure the main runner and command bot are both alive

That gives a practical always-on workflow on a desktop machine without needing a full external deployment stack.

## Main Runner Script

Primary serve wrapper:

- [scripts/run_signal_platform.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/run_signal_platform.ps1)

Important flags:

- `-Config`
- `-EnvFile`
- `-PollSeconds`
- `-LogFile`
- `-MaxCycles`
- `-NoRunImmediately`
- `-DryRun`

Examples:

```powershell
.\scripts\run_signal_platform.ps1 -Config config/platform.example.json -EnvFile .env -PollSeconds 30
.\scripts\run_signal_platform.ps1 -DryRun -MaxCycles 1 -NoRunImmediately
```

## Command Bot Runner Script

Inbound Discord command bot wrapper:

- [scripts/run_signal_platform_command_bot.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/run_signal_platform_command_bot.ps1)

This should be used when:

- the command bot is being run independently
- you want to inspect its own log separately from the main runner

## Logs

Main logs:

- [logs/signal_platform.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform.log)
- [logs/signal_platform_command_bot.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform_command_bot.log)

Use these when:

- the runner exits unexpectedly
- Discord posting looks broken
- the command bot is not responding

## Health Files

Per-route health files live under:

- [platform_output](/C:/Users/Seeker/Documents/swing-pr1/platform_output)

Most useful files:

- `platform_run_summary.json`
- `health_snapshot.json`
- `route_cycle_log.csv`
- `signal_journal.json`
- `signals.json`
- `scan_results.json`

## How to Diagnose a Quiet Board

When a board looks dead, check in this order:

1. Is the main runner alive?
2. Does the route's `health_snapshot.json` exist?
3. What is the route's `quiet_reason`?
4. Did `signals_found` stay at `0`, or were they suppressed?
5. Are there pending outcomes that have not been posted?
6. Did the route recover any recent missed entries?

Interpretation examples:

- `quiet_reason = no_signal`
  - the route ran, but the market did not produce a valid setup
- `quiet_reason = duplicate_suppression`
  - the route found setups already known to the route state
- `dispatch_error_count > 0`
  - something failed during Discord delivery

## Discord Setup Checklist

For webhook routes:

- `DISCORD_WEBHOOK_URL_*` present in `.env`
- matching route enabled in `config/platform.example.json`

For the command bot:

- `DISCORD_BOT_TOKEN` present in `.env`
- bot invited to the correct server
- channel permissions allow:
  - view channel
  - send messages
  - read message history
- Message Content Intent enabled in the Discord developer portal

## Troubleshooting Cases

### No signals at all

Check:

- main runner process
- route health snapshot
- route scan summary
- whether the route is enabled

### One signal posted but no TP or SL follow-up

Check:

- `signal_journal.json`
- whether the signal is still `open`
- `pending_unnotified_outcomes_count`
- whether the route has been cycling since the signal was posted

### Command bot does not reply

Check:

- `DISCORD_BOT_TOKEN`
- invite permissions
- Message Content Intent
- [logs/signal_platform_command_bot.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform_command_bot.log)

### Route looks frozen

Check:

- `last_successful_market_refresh_utc`
- recent rows in `route_cycle_log.csv`
- top-level runner log

## Safe Operational Defaults

Recommended habits:

- use `scan-route --dispatch none` before assuming a live route is broken
- use the watchdog rather than starting many separate PowerShell windows manually
- review `git status` before editing configs on a live machine
- keep strategy logic changes separate from ops and doc changes when possible

## Current Limits

- The project is still desktop-oriented rather than VPS-first.
- There is no broker execution layer.
- Some routes are naturally quiet and should not be treated as dead just because they do not alert frequently.
- The command bot is intentionally lightweight and text-command based.
