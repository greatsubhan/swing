# Parabolic Exhaustion Bot

This project is a separate OANDA-first research and alerting codebase for a
parabolic exhaustion strategy across:

- Gold (`XAU_USD`)
- Silver (`XAG_USD`)
- WTI (`WTICO_USD`)
- NAS100 (`NAS100_USD`)
- UK100 (`UK100_GBP`)
- US30 (`US30_USD`)
- US500 (`SPX500_USD`)

The current implementation now covers the first three phases of the build order:

- typed config loading for OANDA-market research
- provider-agnostic data interfaces with local parquet loading
- daily and intraday feature engineering
- rule-based daily candidate scanning and scoring
- vectorized research backtester with parameter sweeps and CSV exports
- event-driven replay engine with deterministic state transitions
- live stateful alert scanning with replay-parity transitions
- Discord webhook publishing with deduplication and throttling
- unit and integration tests for the foundation, research, replay, and live alert layers

## Layout

```text
parabolic-exhaustion-bot/
|-- config/
|-- data/
|-- src/parabolic_exhaustion/
`-- tests/
```

## Quick Start

```bash
cd C:\Users\Seeker\Documents\swing-pr1\parabolic-exhaustion-bot
python -m pip install -e .[dev]
pytest
```

## Current Scope

Implemented now:

- `parabolic_exhaustion.config`: YAML config models and loaders
- `parabolic_exhaustion.ingestion`: abstract providers and parquet loader
- `parabolic_exhaustion.features.daily`: daily feature engineering
- `parabolic_exhaustion.features.intraday`: intraday feature engineering
- `parabolic_exhaustion.signals.candidates`: daily candidate scanner and scoring
- `parabolic_exhaustion.backtest.vectorized`: vectorized research engine, trade log generation, and exports
- `parabolic_exhaustion.backtest.replay`: event-driven replay engine, transition log generation, and replay diagnostics
- `parabolic_exhaustion.live`: live per-symbol state engine, playback provider, and read-only OANDA polling adapter
- `parabolic_exhaustion.discord_bot`: Discord formatter, publisher, dedupe, rate limiting, and alert logging

Planned next:

- richer reporting and experiment tracking
- CLI or service entrypoints for scheduled live runs
- hardened OANDA operational setup and paper-mode deployment workflow

## Research Outputs

Each vectorized research run exports:

- `candidate_list.csv`
- `signal_table.csv`
- `trade_log.csv`
- `summary_metrics.csv`
- `parameter_comparison.csv`

## Replay Outputs

Each replay run exports:

- `replay_trade_log.csv`
- `state_transition_log.csv`
- `replay_summary_metrics.csv`
- `per_instrument_diagnostics.csv`

## Backtest Summary

Historical validation artifacts from the latest batch run are available in:

- `performance_matrix.csv`
- `BACKTEST_PARAMETER_SETS.md`
- `output/historical_validation/`

Windows used in the current batch:

- Daily and vectorized research used `2020-01-01` through `2026-03-31` for all seven symbols.
- Replay used the available intraday window only, starting `2023-01-02` for every symbol except `UK100_GBP`, which starts `2023-01-03`.
- `M5` replay symbols: `NAS100_USD`, `UK100_GBP`, `US30_USD`, `SPX500_USD`.
- `M15` replay symbols: `XAU_USD`, `XAG_USD`, `WTICO_USD`.

Approximate replay trade frequency from the strongest parameter set per symbol:

- `XAU_USD`: about `0.18` trades/month
- `XAG_USD`: about `0.18` trades/month
- `WTICO_USD`: about `0.21` trades/month
- `NAS100_USD`: about `0.10` trades/month
- `UK100_GBP`: about `0.08` trades/month
- `US30_USD`: about `0.03` trades/month
- `SPX500_USD`: `0.00` trades/month in this batch

Observed robustness in this run:

- No parameter set was robust across the full seven-market basket.
- `ps07_wide_stop_kz_on` was the strongest single configuration on `NAS100_USD`, with replay averaging about `0.80 R` per trade and profit factor about `3.78`.
- `ps01_balanced_kz_on` and `ps02_balanced_kz_off` were the only sets that finished positive on more than one market, but both still had slightly negative basket-level average replay expectancy.

Vectorized vs replay alignment:

- The historical validation path now uses replay-consistent candidate collapse, entry extraction, and execution proxy logic to keep research outputs aligned with the execution model.
- Current batch results show `56/56` rows with matched vectorized and replay trade counts.
- Across the `36` rows that produced trades in both layers, the median absolute PnL gap is now `0.0%`.
- Treat replay as the canonical execution model; the vectorized validation layer is now intentionally tightened to mirror that behavior for parameter comparison work.

## Live Alert Outputs

Each live-monitor run can emit:

- `live_state_transitions.csv`
- `live_trade_log.csv`
- `live_health.csv`
- `discord_alert_log.csv`

Paper forward-test support now also includes:

- `NAS100_PARABOLIC_PAPER` profile in `config/strategy.yaml`
- dedicated Discord webhook routing via `DISCORD_WEBHOOK_URL_NAS100_PARABOLIC_PAPER`
- `forward_test_log_parabolic.csv`
- `python -m parabolic_exhaustion.reporting.forward_test_review_parabolic`

One-shot live scan support now also includes:

- `python -m parabolic_exhaustion.live.scan --profile NAS100_PARABOLIC_PAPER --provider oanda --env-file .env`
- `output/nas100_parabolic_paper/scan_summary.json`

## NAS100 Parabolic Paper Runbook

1. Environment setup

- Copy `.env.example` to `.env`.
- Set `OANDA_API_TOKEN` in `.env`. That is the current env var name used by the live provider.
- `OANDA_ACCOUNT_ID` is optional for this alerts-only runner and is not consumed by the current read-only OANDA live provider.
- Set `DISCORD_WEBHOOK_URL_NAS100_PARABOLIC_PAPER` to the webhook for the dedicated NAS100 paper-forward Discord channel.
- Confirm the selected profile in [config/strategy.yaml](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/config/strategy.yaml) is `NAS100_PARABOLIC_PAPER`.

2. One-off manual run

- From `C:\Users\Seeker\Documents\swing-pr1\parabolic-exhaustion-bot`, start the paper-forward engine with:

```bash
python -m parabolic_exhaustion.live.run --profile NAS100_PARABOLIC_PAPER --provider oanda
```

- This uses the existing NAS100 parabolic paper profile, the read-only OANDA live provider, and the dedicated paper-forward webhook env var.

Optional one-shot scan:

```bash
python -m parabolic_exhaustion.live.scan --profile NAS100_PARABOLIC_PAPER --provider oanda --env-file .env
```

- This performs one current-market evaluation pass, writes `scan_summary.json`, and only alerts from the newest evaluated bar.

3. Verify it is working

- Check [live_health.csv](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/output/nas100_parabolic_paper/live_health.csv) for fresh rows. That confirms the engine is polling and processing bars.
- Check [discord_alert_log.csv](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/output/nas100_parabolic_paper/discord_alert_log.csv) for Discord delivery status codes and messages.
- Check [live_state_transitions.csv](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/output/nas100_parabolic_paper/live_state_transitions.csv) to confirm the parabolic state machine is advancing on NAS100.
- Check [forward_test_log_parabolic.csv](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/output/nas100_parabolic_paper/forward_test_log_parabolic.csv) for new appended rows on `ENTRY_TRIGGERED`, `PARTIAL_TAKEN`, `BREAK_EVEN_PROTECTED`, `ADD_TRIGGERED`, `INVALIDATED`, and `EXITED`.
- Review forward-test performance with:

```bash
python -m parabolic_exhaustion.reporting.forward_test_review_parabolic
```

- That writes [forward_test_review_parabolic.csv](C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/forward_test_review_parabolic.csv). Read it as:
  - `trade_count`: number of closed forward-test trades logged so far
  - `profit_factor`, `average_R`, `max_drawdown_R`: observed paper performance
  - `*_delta_vs_backtest`: how live paper results are tracking versus the configured NAS100 backtest baseline

4. Optional scheduling

- For Windows Task Scheduler, use the project folder as the working directory by wrapping the module call in PowerShell:

```powershell
schtasks /create /tn "NAS100 Parabolic Paper" /sc weekly /d MON,TUE,WED,THU,FRI /st 23:25 /tr "powershell -NoProfile -Command \"Set-Location 'C:\Users\Seeker\Documents\swing-pr1\parabolic-exhaustion-bot'; python -m parabolic_exhaustion.live.run --profile NAS100_PARABOLIC_PAPER --provider oanda\"" /f
```

- Use a schedule that only runs around the US session. If the machine is on Brisbane time, `23:25` is appropriate during New York daylight saving; shift it later when New York moves back to standard time.

Open assumptions that still need confirmation are tracked in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
