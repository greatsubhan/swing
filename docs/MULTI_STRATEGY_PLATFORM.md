# Multi-Strategy Platform

This repo now includes a reusable signal-platform layer so future strategies can share the same runtime and Discord delivery path.

## Why This Was Added

The bot is no longer being built as a one-off Little RZY project.

The new goal is:

- many strategies
- one shared signal runtime
- one Discord delivery system
- one config-driven routing layer

That keeps strategy logic separate from transport and scheduling.

## New Components

- [signal_platform/__main__.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/__main__.py): platform CLI
- [signal_platform/registry.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/registry.py): strategy registry
- [signal_platform/strategies.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/strategies.py): plugin interface
- [signal_platform/little_rzy_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/little_rzy_strategy.py): first strategy adapter
- [signal_platform/dispatchers.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/dispatchers.py): Discord webhook and dedupe helpers
- [signal_platform/runtime.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/runtime.py): config-driven execution
- [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json): routing example

## What This Enables

- one Discord channel per strategy
- one webhook per strategy route
- strategy-by-strategy watchlists
- deduped alerts across reruns
- clean expansion when the next strategy is coded

## Current Registered Strategy

- `little_rzy`

## How Future Strategies Plug In

Each strategy only needs:

1. a strategy adapter that implements the `scan()` interface
2. registration in the strategy registry
3. a route entry in the platform config

That means future strategies do not need to reimplement:

- Discord posting
- sent-alert dedupe
- runtime config parsing
- scheduler entrypoints

## Commands

List registered strategies:

```bash
python -m signal_platform list-strategies
```

Run a one-off strategy scan:

```bash
python -m signal_platform scan --strategy little_rzy --watchlist primary-4h --granularity H4 --oanda-env practice --out platform_output/little_rzy
```

Run config-driven routes:

```bash
python -m signal_platform run-config --config config/platform.example.json
```

Run the service loop:

```bash
python -m signal_platform serve --config config/platform.example.json --poll-seconds 30
```

Test one immediate cycle:

```bash
python -m signal_platform serve --config config/platform.example.json --poll-seconds 5 --max-cycles 1
```

Send a Discord test alert:

```bash
python -m signal_platform --env-file .env test-discord
```

Dry-run without Discord:

- set `dispatch` to `none`
- keep the same route, watchlist, and output paths
- run the normal `serve` command

Route config fields:

- `interval_minutes`
- `dispatch`
- `discord_webhook_url`
- `output_dir`
- `state_file`

Local secret loading:

- the platform now auto-loads `.env` by default
- you can override it with `--env-file path/to/file`

## Current Recommendation

Keep Little RZY running through the platform layer from here onward, so the next strategies can be added without another architecture rewrite.
