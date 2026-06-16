# Platform Architecture

## Overview

`swing-pr1` is a multi-bot trading signal workspace built around two runtime styles:

| Runtime style | Current components | Purpose |
|---|---|---|
| Shared platform | `signal_platform`, `strategy_two_bot`, `strategy_four_bot`, `strategy_five_bot`, `little_rzy` routes | Run multiple Discord boards from one config-driven service loop |
| Standalone subproject | `parabolic-exhaustion-bot` | Separate research, replay, and paper-forward project with its own configs and outputs |

The shared platform is the main orchestration layer for the Discord boards that run from the repo root.

## Main Components

### `signal_platform/`

This is the orchestrator for the root-level Discord boards.

Important modules:

| Module | Responsibility |
|---|---|
| [__main__.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/__main__.py) | CLI entrypoint for `serve`, `scan`, `scan-route`, `run-config`, `command-bot`, `list-strategies`, and `test-discord` |
| [registry.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/registry.py) | Registers all strategy adapters available to the platform |
| [strategies.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/strategies.py) | Shared `StrategyScanRequest` contract and plugin protocol |
| [runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py) | Config loading, route execution, serve loop, one-shot route execution, health logging, and recovery handling |
| [dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py) | Discord webhook payload formatting and outbound delivery |
| [journal.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/journal.py) | Signal journal persistence, outcome tracking, reporting snapshots, and recovery helpers |
| [discord_command_bot.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/discord_command_bot.py) | Inbound Discord command bot for status, help, recent, and scan workflows |
| [command_content.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/command_content.py) | Rich text and embed content for the Discord command bot |

### Strategy adapters

The shared platform does not implement market logic directly. Each route delegates scanning to a strategy adapter.

| Adapter | Backing bot module | Board |
|---|---|---|
| [little_rzy_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/little_rzy_strategy.py) | `little_rzy_bot` | Measured Drift |
| [trend_current_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/trend_current_strategy.py) | `strategy_two_bot` | Trend Current |
| [cwt_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/cwt_strategy.py) | `strategy_four_bot` | Cambist With Trend |
| [secular_bull_sip_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/secular_bull_sip_strategy.py) | `strategy_five_bot` | Secular Bull SIP |

### Strategy bot folders

These folders contain strategy-specific scan logic and watchlists:

| Folder | Primary files | Role |
|---|---|---|
| [little_rzy_bot](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot) | `__main__.py`, `scanner.py`, `signal_engine.py`, `profiles.py`, `watchlists.py` | Standalone backtest, research, and live scan engine for Measured Drift |
| [strategy_two_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot) | `scanner.py`, `watchlists.py` | Stateful basket-management scanner for Trend Current |
| [strategy_four_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_four_bot) | `scanner.py`, `watchlists.py` | Lower-timeframe CWT scanner with ladder sizing |
| [strategy_five_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_five_bot) | `scanner.py`, `watchlists.py` | Monthly SIP allocation and review board |

### Standalone subproject

[parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot) is intentionally separate from `signal_platform`.

It has its own:

- config system
- vectorized backtests
- replay engine
- live paper-forward runner
- one-shot scan mode
- Discord alerting and forward-test review

Use its own README as the source of truth for that project's internal design.

## Runtime Modes

### `serve`

`signal_platform serve` is the continuous orchestrator mode:

1. load `.env`
2. load route config from [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json)
3. wake up on a polling interval
4. run any routes that are due
5. dispatch fresh signals and recovered items
6. update state, journals, summaries, and health files

### `scan`

`signal_platform scan` is strategy-only:

- runs one strategy adapter directly
- does not behave like a configured Discord route
- useful for research, manual checks, and debugging

### `scan-route`

`signal_platform scan-route` is the bot-style one-shot command:

- loads one configured route
- applies route config defaults
- performs recovery logic
- updates state and output files
- optionally dispatches to Discord

This is the closest single-run equivalent to the normal serve loop.

### `command-bot`

`signal_platform command-bot` runs the inbound Discord assistant. It does not replace the webhook boards; it gives operators a conversational interface for:

- viewing boards
- checking board health
- reading recent activity
- running silent one-shot scans

## Data Flow

### Shared platform routes

```text
OANDA API
  -> strategy scanner
  -> strategy adapter
  -> PlatformSignal objects
  -> dedupe against sent setup IDs
  -> optional journal enrichment
  -> Discord webhook delivery
  -> state, journal, report, and health files
```

### Parabolic subproject

```text
OANDA API or local historical files
  -> parabolic live, replay, and vectorized layers
  -> standalone state machine
  -> Discord publisher
  -> forward-test logs and review outputs
```

## Configuration Model

The root project is driven by:

| File | Role |
|---|---|
| [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json) | Route schedule, watchlists, webhooks, recovery limits, and output paths |
| [config/research](/C:/Users/Seeker/Documents/swing-pr1/config/research) | Research and backtest configs for Measured Drift |
| [config/constraints](/C:/Users/Seeker/Documents/swing-pr1/config/constraints) | Strategy-specific market constraints |
| [\.env.example](/C:/Users/Seeker/Documents/swing-pr1/.env.example) | Required environment variable template |

Key route-level controls in `config/platform.example.json`:

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

## Dependencies

The root suite currently installs from [requirements.txt](/C:/Users/Seeker/Documents/swing-pr1/requirements.txt):

- `numpy`
- `pandas`
- `yfinance`
- `discord.py`

Additional internal behavior depends on the project's own Python packages under the repo root.

## Known Boundaries

- `signal_platform` is the operational center for the root Discord boards.
- `parabolic-exhaustion-bot` is not yet folded into the shared route registry.
- Root-level docs and launchers should make that separation explicit so operators do not confuse the two runtimes.
