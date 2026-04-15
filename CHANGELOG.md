# Changelog

This changelog summarizes the major phases of work visible in the repository and
its current structure. It is intentionally grouped by capability area rather
than pretending to reconstruct a perfect historical release process.

## Current Documentation Pass

- Expanded the top-level project README to better document architecture,
  operations, setup, scans, journaling, and troubleshooting
- Expanded the docs index and added dedicated documentation for:
  - platform architecture
  - operations and recovery
  - the Discord command bot
  - the live boards and strategy surfaces
- Added a repo-level changelog summarizing the major visible capability phases

## Discord and Presentation Layer

- Added richer Discord alert formatting for tactical boards, outcomes, reviews,
  and SIP events
- Added a lightweight inbound Discord command bot
- Added command-bot content for:
  - `boards`
  - `strategy`
  - `status`
  - `recent`
  - `scan`
  - `help`
- Added strategy-specific preview payloads for Discord test messages

## Reliability, Recovery, and Monitoring

- Added route journaling and outcome tracking
- Added TP / SL / break-even notification recovery for missed closures
- Added recent missed-entry catch-up windows for tactical boards
- Added per-route:
  - `platform_run_summary.json`
  - `health_snapshot.json`
  - `route_cycle_log.csv`
- Improved route observability so quiet boards can be distinguished from broken
  routes

## Multi-Strategy Platform

- Added the shared `signal_platform` runtime
- Added strategy registry and adapter model
- Added config-driven routing through `config/platform.example.json`
- Added platform CLI commands:
  - `serve`
  - `run-config`
  - `scan`
  - `scan-route`
  - `list-strategies`
  - `command-bot`
  - `test-discord`

## Strategy Additions and Evolution

### Measured Drift / Little RZY

- Built the original Little RZY signal bot baseline
- Added standalone CLI scan and backtesting workflow
- Hardened the 4h implementation
- Added explicit backtest costs and research config support
- Added a research-only 1h variant with:
  - HTF bias
  - session filters
  - volatility gating

### Trend Current

- Added Trend Current as `strategy_two`
- Enabled managed basket lifecycle events
- Added basket state integration into the platform

### Cambist With Trend (CWT)

- Added CWT as `strategy_four`
- Built mixed-asset watchlists and route integration
- Added live-route journaling and outcome handling
- Fixed stale-cache behavior and improved recovery of missed notifications

### Secular Bull SIP

- Added SIP as `strategy_five`
- Implemented monthly allocation and review events
- Added trend-filtered monthly adds
- Added Discord delivery through the shared platform

### Parabolic Exhaustion

- Added a separate paper-forward strategy project under
  `parabolic-exhaustion-bot`
- Added live scan and paper-forward launch helpers at the suite root

## Research and Backtesting Expansion

- Added extensive research scripts under `research/`
- Added research reports under `reports/`
- Added strategy-specific backtest passes for:
  - Measured Drift variants
  - CWT
  - Secular Bull SIP
  - Secular Bear
  - Advanced Engulfing
- Added research config folders under `config/research`
- Added market constraint definitions under `config/constraints`

## Windows Operations and Startup

- Added PowerShell launch scripts for the platform and command bot
- Added watchdog logic to ensure the main runner and command bot are alive
- Added desktop launcher integration via `Start All Bots.cmd`
- Added startup-install helper script for Windows login/startup behavior

## Tests and Verification

- Added targeted tests for:
  - command bot content
  - signal platform recovery logic
  - scan-route behavior
  - dispatcher formatting
  - Little RZY hardening flows

## Notes

- Some strategy and research branches remain experimental.
- The repo contains a mixture of production-style runtime code, research
  artifacts, and generated outputs.
- Future changelog updates should ideally be maintained incrementally per
  documentation or feature change set.
