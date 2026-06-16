# swing-pr1

`swing-pr1` is a multi-strategy trading signal workspace centered on a shared Discord-first runtime. The repository combines:

- a reusable orchestration layer in [signal_platform](/C:/Users/Seeker/Documents/swing-pr1/signal_platform)
- several strategy-specific bots and research modules
- Discord webhook delivery for outbound alerts
- a lightweight inbound Discord command bot for `boards`, `strategy`, `status`, `recent`, `scan`, and `help`
- journaling, outcome tracking, missed-alert recovery, startup automation, and research tooling

This repo mixes production-style signal delivery with ongoing research. Some strategies are live-facing boards; others remain research-only.

## Project Purpose

The project exists to let multiple strategy boards share one operational runtime without duplicating:

- scheduling
- data loading conventions
- Discord dispatch
- duplicate suppression
- signal journaling
- outcome tracking
- recovery after downtime
- health logging and status reporting

## Tech Stack

Primary stack:

- Python
- PowerShell for Windows launchers and watchdogs
- OANDA market data for live route scans
- Discord webhooks for outbound delivery
- `discord.py` for the inbound command bot
- JSON-based route configuration

Important supporting packages are defined in [requirements.txt](/C:/Users/Seeker/Documents/swing-pr1/requirements.txt).

## Main Components

| Area | Purpose |
|---|---|
| [signal_platform](/C:/Users/Seeker/Documents/swing-pr1/signal_platform) | Shared runtime, route config loader, dispatchers, journaling, command bot |
| [little_rzy_bot](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot) | Measured Drift and Little RZY signal engine, backtesting, and research configs |
| [strategy_two_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot) | Trend Current managed-basket logic |
| [strategy_four_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_four_bot) | Cambist With Trend live scanner |
| [strategy_five_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_five_bot) | Secular Bull SIP monthly allocation board |
| [parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot) | Separate paper-forward research and alerting codebase |
| [config](/C:/Users/Seeker/Documents/swing-pr1/config) | Route configs, research configs, and market constraints |
| [scripts](/C:/Users/Seeker/Documents/swing-pr1/scripts) | PowerShell launchers, watchdogs, startup helpers, and scan wrappers |
| [docs](/C:/Users/Seeker/Documents/swing-pr1/docs) | Architecture, strategy, operations, and research documentation |
| [platform_output](/C:/Users/Seeker/Documents/swing-pr1/platform_output) | Per-route live state, journals, health snapshots, and cycle logs |
| [reports](/C:/Users/Seeker/Documents/swing-pr1/reports) | Research and backtest outputs |

## Live Boards

| Route ID | Strategy Name | Role | Cadence | Default watchlist | Status |
|---|---|---|---|---|---|
| `little_rzy` | Measured Drift | Tactical 4h continuation board | `H4` | `primary-4h` | Live route |
| `little_rzy_1h` | Measured Drift 1H | Lower-timeframe research route | `H1` | `research-1h` | Disabled by default |
| `strategy_two` | Trend Current | Managed basket board | `H4` | `core-4h` | Live route |
| `strategy_four` | Cambist With Trend | Tactical continuation board | `M5/M15` with `H1` bias | `core-mixed` | Live route |
| `strategy_five` | Secular Bull SIP | Monthly allocation board | `D` with monthly logic | `full-classic` | Live route |

## Quick Start

### 1. Install dependencies

```powershell
cd C:\Users\Seeker\Documents\swing-pr1
python -m pip install -r requirements.txt
```

### 2. Create `.env`

Copy [`.env.example`](/C:/Users/Seeker/Documents/swing-pr1/.env.example) to `.env` and populate the values you need.

Minimum operational variables:

```env
OANDA_API_TOKEN=your-oanda-api-token
DISCORD_WEBHOOK_URL_LITTLE_RZY=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_URL_STRATEGY_TWO=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_URL_CWT=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_URL_SIP=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=your-discord-bot-token
```

Optional or route-specific:

```env
DISCORD_WEBHOOK_URL_LITTLE_RZY_1H=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_URL=generic-fallback-webhook
```

### 3. Start the shared signal platform

```powershell
python -m signal_platform --env-file .env serve --config config/platform.example.json --poll-seconds 30
```

Windows launcher:

- [RUN_signal_platform.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform.bat)

### 4. Start the Discord command bot

```powershell
python -m signal_platform --env-file .env command-bot --config config/platform.example.json
```

Windows launcher:

- [RUN_signal_platform_command_bot.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform_command_bot.bat)

### 5. Use the watchdog and desktop launcher

To check and start both the main runner and the command bot:

- [Start All Bots.cmd](/C:/Users/Seeker/Documents/swing-pr1/Start%20All%20Bots.cmd)
- [scripts/ensure_signal_platform.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/ensure_signal_platform.ps1)

## Architecture Summary

At a high level, the shared runtime works like this:

1. A configured route wakes up on schedule.
2. The route adapter calls the underlying strategy scanner.
3. The scanner reads current market data from OANDA or another local provider.
4. Signals are normalized into `PlatformSignal` records.
5. The runtime filters duplicates against the route state file.
6. The route journal is refreshed to detect TP, SL, and break-even closures.
7. Pending outcomes are posted before new entries.
8. Fresh signals and short-window recovered signals are dispatched to Discord.
9. Summary files, health snapshots, journals, and logs are written to [platform_output](/C:/Users/Seeker/Documents/swing-pr1/platform_output).

The repo also contains a separate standalone runtime in [parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot). It has its own backtesting, replay, live scan, and paper-forward flow and is not part of the root `signal_platform` registry.

## Data Providers and Alert Flow

### Market data

- Tactical live routes primarily use OANDA.
- `little_rzy_bot` research can also run through its own research and backtest inputs.
- `parabolic-exhaustion-bot` has its own local historical and OANDA-oriented stack.

### Outbound delivery

- Webhook posts are formatted in [signal_platform/dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py)
- Route summaries, health snapshots, and state files are written locally after each cycle

### Inbound interaction

- The Discord command bot reads platform config and route health snapshots
- It does not place orders or manage trades
- It surfaces board information, status, recent activity, and safe scans

Core runtime files:

- [signal_platform/__main__.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/__main__.py)
- [signal_platform/runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py)
- [signal_platform/dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py)
- [signal_platform/journal.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/journal.py)
- [signal_platform/registry.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/registry.py)
- [signal_platform/models.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/models.py)
- [signal_platform/discord_command_bot.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/discord_command_bot.py)
- [signal_platform/command_content.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/command_content.py)

## Strategy Boards and Bots

### Measured Drift (`little_rzy`)

- Tactical `H4` continuation board
- Strongest as the mature baseline system in this repo
- Also has a research-only `H1` variant with session and volatility filters

### Trend Current (`strategy_two`)

- Managed basket strategy
- Uses basket lifecycle events such as new basket, add, stop move, and basket exit
- Quieter by design than the tactical boards

### Cambist With Trend (`strategy_four`)

- Lower-timeframe continuation board
- Uses `H1` bias and executes on `M5` and `M15`
- Supports recovery posting for missed recent entries and missed outcomes

### Secular Bull SIP (`strategy_five`)

- Monthly macro allocation board
- Long-only, trend-filtered monthly adds
- Posts managed monthly allocation and review events rather than fast trade alerts

### Parabolic Exhaustion Bot

- Separate project under [parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot)
- Not wired into `signal_platform`
- Maintains its own research, live scan, and paper-forward workflow

## CLI Usage

### `signal_platform`

| Command | Purpose |
|---|---|
| `list-strategies` | Show registered route IDs |
| `scan` | One strategy analysis scan with no route state side effects |
| `scan-route` | One configured route run with dispatch, journaling, and recovery behavior |
| `run-config` | Run all enabled routes once |
| `serve` | Poll enabled routes continuously |
| `command-bot` | Run the inbound Discord command bot |
| `test-discord` | Send a strategy-styled preview message to a webhook |

Examples:

```powershell
python -m signal_platform --env-file .env list-strategies
python -m signal_platform --env-file .env run-config --config config/platform.example.json
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four --dispatch none --catch-up-hours 6
python -m signal_platform --env-file .env test-discord --strategy strategy_four
```

### Standalone `little_rzy_bot`

`little_rzy_bot` remains the standalone research and scan CLI for Measured Drift.

Examples:

```powershell
python -m little_rzy_bot --scan --watchlist primary-4h --granularity H4 --oanda-env practice --out backtest_output
python -m little_rzy_bot research --config config/research/research.little_rzy_4h.json
python -m little_rzy_bot research --config config/research/research.little_rzy_1h.json
```

## Discord Command Bot Flow

The command bot is a separate inbound listener. It complements outbound webhook alerts rather than replacing them.

Supported text commands:

- `boards`
- `strategy`
- `strategy cwt`
- `status`
- `status trend`
- `recent`
- `recent measured`
- `scan`
- `scan cwt`
- `help`

Notes:

- `scan` is safe by default and does not dispatch trade alerts
- `recent` reads the latest journaled signal or outcome, or the latest managed event
- `status` reads route health snapshots written by the live runtime
- Discord requires **Message Content Intent** to be enabled for plain text commands to work

## Scan Modes

There are two important scan styles:

### Strategy-only analysis scan

Use `signal_platform scan` when you want an analysis pass without route-state side effects.

### Route scan

Use `signal_platform scan-route` when you want a one-shot operational pass that:

- evaluates the configured route
- applies duplicate suppression
- refreshes the signal journal
- posts pending outcomes
- recovers recent missed entries inside the route catch-up window
- updates route state files

The repo also includes Windows wrappers for one-shot scans:

- [RUN_little_rzy_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_little_rzy_scan.bat)
- [RUN_strategy_two_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_two_scan.bat)
- [RUN_strategy_four_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_four_scan.bat)
- [RUN_strategy_five_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_strategy_five_scan.bat)
- [RUN_nas100_parabolic_scan.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_nas100_parabolic_scan.bat)

## Journaling, Outcome Tracking, and Recovery

For tactical boards, the runtime maintains a journal with open and closed signal records. That powers:

- TP, SL, and break-even outcome updates
- realized-R reporting
- weekly and monthly report cards
- catch-up recovery after short downtime windows

Recovery behavior today:

- all closed journal entries with `outcome_notified = false` are recoverable
- recent missed entries can be recovered inside the route's `catch_up_hours` window
- each route writes a `health_snapshot.json` and `route_cycle_log.csv` so quiet boards can be explained quickly

## Configuration System

Important config files:

| File | Purpose |
|---|---|
| [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json) | Main multi-route platform config |
| [config/README.md](/C:/Users/Seeker/Documents/swing-pr1/config/README.md) | Config index |
| [config/research](/C:/Users/Seeker/Documents/swing-pr1/config/research) | Reproducible research configs |
| [config/constraints](/C:/Users/Seeker/Documents/swing-pr1/config/constraints) | Market constraints used by strategy research |

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

## Startup Automation, Launchers, and Watchdogs

Current deployment style is desktop-first:

- Windows launchers
- PowerShell watchdogs
- startup-folder automation

Important operator entrypoints:

- [RUN_signal_platform.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform.bat)
- [RUN_signal_platform_command_bot.bat](/C:/Users/Seeker/Documents/swing-pr1/RUN_signal_platform_command_bot.bat)
- [Start All Bots.cmd](/C:/Users/Seeker/Documents/swing-pr1/Start%20All%20Bots.cmd)
- [scripts/ensure_signal_platform.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/ensure_signal_platform.ps1)
- [scripts/install_signal_platform_startup.ps1](/C:/Users/Seeker/Documents/swing-pr1/scripts/install_signal_platform_startup.ps1)

There is no VPS-first deployment baked in yet, but the runtime is structured so it can be moved later if needed.

## Logging, Health Snapshots, and Output Folders

### Runtime outputs

Per-route operational files usually live under [platform_output](/C:/Users/Seeker/Documents/swing-pr1/platform_output):

- `platform_run_summary.json`
- `signals.json`
- `scan_results.json`
- `signal_journal.json`
- `sent_state.json`
- `report_state.json`
- `health_snapshot.json`
- `route_cycle_log.csv`

### Logs

Top-level runtime logs live in [logs](/C:/Users/Seeker/Documents/swing-pr1/logs):

- `signal_platform.log`
- `signal_platform_command_bot.log`

## Setup and Installation Notes

Recommended install routine:

1. Install [requirements.txt](/C:/Users/Seeker/Documents/swing-pr1/requirements.txt).
2. Copy [`.env.example`](/C:/Users/Seeker/Documents/swing-pr1/.env.example) to `.env`.
3. Populate OANDA and Discord credentials.
4. Validate config paths in [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json).
5. Run a silent `scan-route --dispatch none` before relying on live posting.

## Testing and Verification Workflow

The repo contains both unit-style and integration-style tests under [tests](/C:/Users/Seeker/Documents/swing-pr1/tests).

Useful checks:

```powershell
python -m compileall signal_platform little_rzy_bot strategy_two_bot strategy_four_bot strategy_five_bot tests
python -m pytest tests -q
python -m signal_platform --env-file .env list-strategies
python -m signal_platform --env-file .env test-discord --strategy strategy_four
python -m signal_platform --env-file .env scan-route --config config/platform.example.json --strategy strategy_four --dispatch none
```

## Troubleshooting

| Problem | What to check |
|---|---|
| No signals at all | Check the runner is alive, then inspect the route's `health_snapshot.json` and `platform_run_summary.json` |
| Bot not posting to Discord | Verify the route webhook in `.env`, then check [logs/signal_platform.log](/C:/Users/Seeker/Documents/swing-pr1/logs/signal_platform.log) |
| Command bot not replying | Check `DISCORD_BOT_TOKEN`, server invite, channel permissions, and Message Content Intent |
| Quiet board | Look at `quiet_reason`, `fresh_signals`, `recovered_entries_sent`, and `pending_unnotified_outcomes_count` in the route health snapshot |
| Stale route behavior | Confirm the route is still running and review recent `route_cycle_log.csv` entries |
| Duplicate-looking suppression | Check the route's `sent_state.json` and `suppressed_duplicates` count |

## Known Limitations

- Strategy quality is not uniform across all research branches; some strategies remain experimental.
- `little_rzy_1h` is research-only and disabled by default.
- The command bot is lightweight and text-command oriented; it is not a full Discord app with slash commands.
- The parabolic exhaustion bot is still a separate codebase with its own packaging and output conventions.
- Many reports under [reports](/C:/Users/Seeker/Documents/swing-pr1/reports) are research artifacts and should not be mistaken for live production claims.

## TODOs and Future Improvements

- Fold more route-specific ops guidance into structured docs as the bot suite grows.
- Keep the route config examples aligned with the actual enabled production boards.
- Decide whether the parabolic project should remain separate long term or graduate into the shared platform.
- Improve deployment automation if the project moves from desktop-first operation to a hosted environment.

## Documentation Map

Start here for deeper documentation:

- [docs/README.md](/C:/Users/Seeker/Documents/swing-pr1/docs/README.md)
- [docs/platform/ARCHITECTURE.md](/C:/Users/Seeker/Documents/swing-pr1/docs/platform/ARCHITECTURE.md)
- [docs/platform/OPERATIONS_AND_RECOVERY.md](/C:/Users/Seeker/Documents/swing-pr1/docs/platform/OPERATIONS_AND_RECOVERY.md)
- [docs/platform/COMMAND_BOT.md](/C:/Users/Seeker/Documents/swing-pr1/docs/platform/COMMAND_BOT.md)
- [docs/platform/MULTI_STRATEGY_PLATFORM.md](/C:/Users/Seeker/Documents/swing-pr1/docs/platform/MULTI_STRATEGY_PLATFORM.md)
- [docs/platform/LAUNCH_PREP.md](/C:/Users/Seeker/Documents/swing-pr1/docs/platform/LAUNCH_PREP.md)
- [docs/strategies/BOARDS_OVERVIEW.md](/C:/Users/Seeker/Documents/swing-pr1/docs/strategies/BOARDS_OVERVIEW.md)
- [docs/strategies/README.md](/C:/Users/Seeker/Documents/swing-pr1/docs/strategies/README.md)
- [CHANGELOG.md](/C:/Users/Seeker/Documents/swing-pr1/CHANGELOG.md)

## Git and Contribution Notes

This repository contains live-route code, research code, and generated research outputs. Before opening a commit or pull request:

- review `git status`
- stage only the files intended for the commit
- avoid committing `.env` or secrets
- avoid mixing documentation-only changes with strategy logic unless the purpose of the commit is explicit
