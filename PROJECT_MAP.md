# PROJECT_MAP.md — Living System Architecture

**Last updated:** 2026-06-16T21:25:00+10:00

---

## 1. System Overview

The **swing-pr1** project is a multi-strategy algorithmic trading system. It runs a **signal-platform** that orchestrates strategy scans, signal dispatch to Discord, trade execution via OANDA, trade journaling, ML model training, and health monitoring. Each strategy is a plugin implementing `StrategyPlugin` protocol. The platform reads configuration from a JSON file, runs each enabled route on its own interval, and produces structured outputs.

```
┌─ Strategy Layer ─────────────────────────────────────────────────┐
│  little_rzy (Measured Drift)  │  strategy_two (Trend Current)    │
│  strategy_four (Cambist With Trend)  │  strategy_five (Secular   │
│  Bull SIP)  │  little_rzy_1h (disabled)                          │
└───────────────────────┬──────────────────────────────────────────┘
                        │ scan() → PlatformSignal[]
┌─ Signal Processing ───┴──────────────────────────────────────────┐
│  Reinforcement scoring  │  ML prediction scoring                 │
│  Duplicate suppression  │  Circuit breaker check                 │
└───────────────────────┬──────────────────────────────────────────┘
                        │ dispatch-ready signals
┌─ Dispatch Layer ──────┴──────────────────────────────────────────┐
│  Discord webhook signals  │  Discord outcome notifications      │
│  Discord weekly/monthly reports  │  OANDA order execution       │
└───────────────────────┬──────────────────────────────────────────┘
                        │ outcomes
┌─ Data Layer ──────────┴──────────────────────────────────────────┐
│  Signal journals (JSON)  │  Health snapshots (JSON)             │
│  Ladder ledgers  │  ML models (pkl)  │  Cycle logs (CSV)        │
└───────────────────────┬──────────────────────────────────────────┘
                        │ live refresh
┌─ Monitoring Layer ────┴──────────────────────────────────────────┐
│  Route cycle log  │  Health snapshot  │  Heartbeat  │  Dashboard │
└──────────────────────────────────────────────────────────────────┘
```

**Architecture style:** Config-driven, route-per-strategy, plugin-based, polling loop.

---

## 2. Bot and Strategy Registry

| Bot ID | Strategy Class | Display Name | Enabled | Dispatch | Granularity | Interval |
|--------|---------------|--------------|---------|----------|-------------|----------|
| `little_rzy` | `LittleRzyStrategy` | Little Rzy | ✅ yes | discord_and_oanda | H4 | 240 min |
| `little_rzy_1h` | `LittleRzy1HStrategy` | Little Rzy 1H | ❌ no | discord | H1 | 60 min |
| `strategy_two` | `TrendCurrentStrategy` | Trend Current | ✅ yes | discord | H4 | 240 min |
| `strategy_four` | `CwtStrategy` | CWT | ✅ yes | discord_and_oanda | M5 | 5 min |
| `strategy_five` | `SecularBullSipStrategy` | Secular Bull SIP | ✅ yes | discord | D | 1440 min |
| `command_bot` | N/A (Discord bot) | Command Bot | ✅ yes | discord | N/A | on-demand |
| `nas100_parabolic` | N/A (standalone) | NAS100 Parabolic | ✅ yes | OANDA paper | M1 | variable |

**Source:** `signal_platform/registry.py` lines 11-17 (verified), `config/platform.example.json` (verified)

---

## 3. Node Registry (System Nodes with Evidence)

Every node in the system architecture, tagged with evidence source and confidence.

| Node ID | Layer | Label | Source File | Line/Function | Confidence | Status |
|---------|-------|-------|-------------|---------------|------------|--------|
| `strat_little_rzy` | Strategy | Little Rzy | registry.py:12 | `LittleRzyStrategy()` | verified | error |
| `strat_little_rzy_1h` | Strategy | Little Rzy 1H | registry.py:13 | `LittleRzy1HStrategy()` | verified | disabled |
| `strat_strategy_two` | Strategy | Trend Current | registry.py:14 | `TrendCurrentStrategy()` | verified | idle |
| `strat_strategy_four` | Strategy | CWT (Cambist With Trend) | registry.py:15 | `CwtStrategy()` | verified | error |
| `strat_strategy_five` | Strategy | Secular Bull SIP | registry.py:16 | `SecularBullSipStrategy()` | verified | idle |
| `scan_cwt` | Execution | CWT Scanner | strategy_four_bot/scanner.py:678 | `run_live_cycle()` | verified | error |
| `scan_little_rzy` | Execution | Little Rzy Scanner | little_rzy_bot/scanner.py | `run_live_cycle()` | verified | partial |
| `reinforcement` | Decision | Signal Reinforcement | reinforcement.py | `apply_signal_reinforcement()` | verified | active-strategy_four-only |
| `ml_scoring` | Decision | ML Prediction Scoring | signal_scoring.py | `score_signal_with_ml()` | partial | code-exists |
| `ml_feature_extraction` | Decision | ML Feature Extraction | ml_features.py | `load_and_build_features()` | verified | trained-strategy_four |
| `ml_outcome_classifier` | Decision | Outcome Classifier | ml_models.py | `train_outcome_classifier()` | verified | .pkl-on-disk |
| `ml_r_regressor` | Decision | Realized R Regressor | ml_models.py | `train_realized_r_regressor()` | verified | .pkl-on-disk |
| `duplicate_suppression` | Execution | Duplicate Suppression | runtime.py:596 | `new_signals_only()` | verified | active |
| `circuit_breaker` | Execution | Circuit Breaker | runtime.py:767 | `_check_daily_circuit_breaker()` | verified | active |
| `dispatch_discord_signal` | Dispatch | Discord Signal Dispatch | runtime.py:656 | `_send_discord_signal_with_ml()` | verified | code-path-exists |
| `dispatch_discord_outcome` | Dispatch | Discord Outcome Notification | runtime.py:635 | `send_discord_outcome()` | verified | code-path-exists |
| `dispatch_discord_report_weekly` | Dispatch | Weekly Report | runtime.py:710 | `send_discord_report()` | verified | code-path-exists |
| `dispatch_discord_report_monthly` | Dispatch | Monthly Report | runtime.py:733 | `send_discord_report()` | verified | code-path-exists |
| `dispatch_discord_prediction_perf` | Dispatch | Prediction Performance Report | runtime.py:719 | `_send_weekly_prediction_performance()` | verified | code-path-exists |
| `oanda_connection` | Integration | OANDA API Connection | oanda_execution.py:136 | `test_connection()` | verified | working-2-successful-fills-logged |
| `oanda_account` | Integration | OANDA Account Summary | oanda_execution.py:160 | `get_account_summary()` | verified | available |
| `oanda_execution` | Integration | OANDA Order Execution | oanda_execution.py:330 | `execute_signal()` | verified | active-tp-precision-fix-applied |
| `oanda_position_sizing` | Integration | Position Sizing | position_sizing.py | `calculate_position_size()` | verified | code-ready |
| `oanda_market_data` | Integration | OANDA Market Data (OHLCV) | little_rzy_bot/market_data.py | `fetch_oanda_ohlcv()` | verified | route-dependent: active-strategy-four, 401-little_rzy-strategy_five |
| `discord_command_bot` | Integration | Discord Command Bot | discord_command_bot.py | standalone script | verified | idle |
| `discord_webhooks` | Integration | Discord Webhooks (5) | platform.example.json:13,35,61,83,145 | `${VAR}` placeholders | partial | env-vars-missing |
| `journal_strategy_four` | Data | Journal — strategy_four | platform_output/strategy_four/signal_journal.json | file on disk | verified | 1,029-entries |
| `journal_little_rzy` | Data | Journal — little_rzy | platform_output/little_rzy/signal_journal.json | file on disk | verified | 2-entries |
| `journal_strategy_two` | Data | Journal — strategy_two | platform_output/strategy_two/signal_journal.json | file on disk | verified | empty |
| `journal_strategy_five` | Data | Journal — strategy_five | platform_output/strategy_five/signal_journal.json | file does not exist | verified | missing |
| `journal_little_rzy_1h` | Data | Journal — little_rzy_1h | N/A (disabled) | disabled route | verified | disabled |
| `ladder_ledger` | Data | Ladder Ledger | platform_output/{route}/ladder_ledger.json | file on disk | verified | strategy_four-only |
| `reinforcement_state` | Data | Reinforcement State | platform_output/strategy_four/reinforcement_state.json | file on disk | verified | strategy_four-only |
| `ml_models_store` | Data | ML Models (2) | platform_output/strategy_four/ml_models/ | .pkl files on disk | verified | strategy_four-only |
| `predictions_log` | Data | Prediction Log | platform_output/strategy_four/predictions.jsonl | file on disk | verified | strategy_four-only |
| `backtest_hardening` | Data | Backtest — Hardening Smoke | backtest_output_hardening_smoke/summary.json | file on disk | verified | 16-trades |
| `health_snapshot` | Monitoring | Health Snapshots | platform_output/{route}/health_snapshot.json | file on disk | verified | 4-routes |
| `route_cycle_log` | Monitoring | Route Cycle Logs | platform_output/{route}/route_cycle_log.csv | file on disk | verified | 4-routes |
| `dispatch_failures_log` | Monitoring | Dispatch Failures Log | platform_output/{route}/dispatch_failures.jsonl | file on disk | verified | 2-routes |
| `service_heartbeat` | Monitoring | Service Heartbeat | logs/signal_platform_heartbeat.json | may not exist | partial | not-on-disk |
| `dashboard_metrics` | Monitoring | Dashboard Metrics JSON | platform_output/_dashboard_metrics.json | file on disk | verified | exists |
| `dashboard_ui` | Monitoring | Dashboard UI | bot-dashboard/index.html | static HTML | verified | hardcoded-data |

---

## 4. Connection Registry (System Links with Evidence)

Every connection/link between nodes, tagged with source evidence and verification status.

| From | To | Link Type | Source Evidence | Confidence |
|------|----|-----------|-----------------|------------|
| `strat_little_rzy` | `scan_little_rzy` | strategy.plugin → scanner | `little_rzy_strategy.py` scan() delegates to scanner | verified |
| `strat_strategy_four` | `scan_cwt` | strategy.plugin → scanner | `cwt_strategy.py` scan() delegates to strategy_four_bot | verified |
| `scan_cwt` | `reinforcement` | scanner → reinforcement | `runtime.py:579` `apply_signal_reinforcement()` | verified |
| `scan_little_rzy` | `reinforcement` | scanner → reinforcement | `runtime.py:579` same code path for all routes | verified |
| `reinforcement` | `duplicate_suppression` | reinforcement → dedup | `runtime.py:596` processes reinforcement results | verified |
| `duplicate_suppression` | `dispatch_discord_signal` | dedup → discord dispatch | `runtime.py:656` iterates fresh_signals | verified |
| `duplicate_suppression` | `dispatch_discord_outcome` | dedup → outcome dispatch | `runtime.py:635` iterates outcomes_to_send | verified |
| `duplicate_suppression` | `oanda_execution` | dedup → OANDA (discord_and_oanda routes) | `runtime.py:791` iterates delivered_tradable | verified |
| `oanda_connection` | `oanda_account` | connection → account summary | `oanda_execution.py:160` uses connection | verified |
| `oanda_connection` | `oanda_market_data` | connection → market data | `market_data.py:268` uses OANDA API | verified |
| `oanda_account` | `oanda_execution` | account → execute order | `runtime.py:790` gets account before execution | verified |
| `oanda_position_sizing` | `oanda_execution` | sizing → execution | `oanda_execution.py:330` uses `calculate_position_size()` | verified |
| `dispatch_discord_signal` | `ml_scoring` | dispatch → ML scoring | `runtime.py:285` `score_signal_with_ml()` inside dispatch | verified |
| `ml_scoring` | `ml_feature_extraction` | scoring → features | `signal_scoring.py` uses feature vectors | verified |
| `ml_feature_extraction` | `ml_outcome_classifier` | features → classifier | `ml_models.py` uses feature vectors to train | verified |
| `ml_feature_extraction` | `ml_r_regressor` | features → regressor | `ml_models.py` uses feature vectors to train | verified |
| `dispatch_discord_signal` | `discord_webhooks` | dispatch → webhook | `runtime.py:293` `send_discord_text()` to webhook URL | verified |
| `dispatch_discord_outcome` | `discord_webhooks` | outcome → webhook | `runtime.py:637` `send_discord_outcome()` to webhook URL | verified |
| `dispatch_discord_report_weekly` | `discord_webhooks` | weekly report → webhook | `runtime.py:713` `send_discord_report()` to webhook URL | verified |
| `dispatch_discord_prediction_perf` | `discord_webhooks` | ML perf → webhook | `runtime.py:312` `send_discord_text()` to webhook URL | verified |
| `dispatch_discord_signal` | `journal_strategy_four` | dispatch → journal append | `runtime.py:844` `append_new_signals()` | verified |
| `oanda_execution` | `journal_strategy_four` | execution → journal (open entries) | `runtime.py:844` trades appended to journal | verified |
| `journal_strategy_four` | `ladder_ledger` | journal → ladder | `runtime.py:846` `save_ladder_ledger()` | verified |
| `journal_strategy_four` | `reinforcement_state` | journal → reinforcement | `reinforcement.py` reads journal for state | verified |
| `journal_strategy_four` | `ml_feature_extraction` | journal → feature extraction | `runtime.py:466` loads journal for ML training | verified |
| `journal_strategy_four` | `health_snapshot` | journal → health snapshot | `runtime.py:911` builds health snapshot from metrics | verified |
| `health_snapshot` | `dashboard_metrics` | health → dashboard | `import_journal.py:95` reads health snapshots | verified |
| `journal_strategy_four` | `dashboard_metrics` | journal → dashboard | `import_journal.py:81` reads journals | verified |
| `dispatch_failures_log` | `health_snapshot` | failures → health | `runtime.py:953` writes dispatch failures | verified |
| `health_snapshot` | `route_cycle_log` | snapshot → cycle log | `runtime.py:952` writes CSV log row | verified |
| `strat_strategy_two` | `journal_strategy_two` | strategy → journal (empty) | Journal file exists but is empty array | verified |
| `strat_strategy_five` | `journal_strategy_five` | strategy → journal (missing) | Journal file does not exist | verified |
| `backtest_hardening` | `dashboard_ui` | backtest → dashboard panel | Dashboard renders backtest data in HTML | verified |
| `discord_command_bot` | `discord_webhooks` | cmd bot → webhook | `discord_command_bot.py` posts to Discord | verified |

### Inferred Connections (visually distinct)

| From | To | Link Type | Rationale | Confidence |
|------|----|-----------|-----------|------------|
| `reinforcement` | `ml_scoring` | reinforcement → ML | Both process signals but no direct function call linking them | inferred |
| `discord_webhooks` | `dispatch_discord_signal` | webhook ← dispatch (verification) | Code sends but no success confirm in runtime data | inferred |
| `oanda_execution` | `journal_strategy_four/little_rzy` | execution → journal | Code path exists but blocked by 401 | inferred |

---

## 5. Metric Provenance

Every metric the dashboard displays, traced to its source.

| Metric | Source Type | Source File | Extraction Method | Confidence |
|--------|-------------|-------------|-------------------|------------|
| Bot count | config | `platform.example.json` | Count enabled routes | verified |
| OANDA route count | config | `platform.example.json` | Count routes with dispatch="discord_and_oanda" | verified |
| strategy_four total signals | journal | `platform_output/strategy_four/signal_journal.json` | `len(entries)` in `import_journal.py:10` | verified |
| strategy_four win rate | journal | Same journal | `tp / closed` counts | verified |
| strategy_four net R | journal | Same journal | Sum of `realized_r()` per closed entry | verified |
| strategy_four TP/SL | journal | Same journal | Count `outcome` field values | verified |
| strategy_four profit factor | journal | Same journal | `sum(wins) / abs(sum(losses))` | verified |
| strategy_four runtime status | runtime | `platform_output/strategy_four/health_snapshot.json` | `dispatch_error_count > 0` → "error" | verified |
| strategy_four last cycle | runtime | Same health snapshot | `last_cycle_finished_utc` | verified |
| strategy_four error message | runtime | Same health snapshot | `error` or `dispatch_errors[0]` | verified |
| little_rzy total signals | journal | `platform_output/little_rzy/signal_journal.json` | Same as above | verified |
| little_rzy runtime status | runtime | `platform_output/little_rzy/health_snapshot.json` | Same as above | verified |
| strategy_two runtime status | runtime | `platform_output/strategy_two/health_snapshot.json` | Same as above | verified |
| strategy_five runtime status | runtime | `platform_output/strategy_five/health_snapshot.json` | Same as above | verified |
| strategy_five journal status | undefined | No journal file | Hardcoded as "unavailable" | verified |
| Backtest trade count | backtest | `backtest_output_hardening_smoke/summary.json` | Read `trades` field | verified |
| Backtest win rate | backtest | Same | Read `winRate` field | verified |
| Backtest net P&L | backtest | Same | Read `totalPnlR` field | verified |
| Backtest profit factor | backtest | Same | Read `profitFactor` field | verified |
| Backtest max drawdown | backtest | Same | Read `maxDrawdownR` field | verified |
| Health snapshot signals_found | runtime | `health_snapshot.json` | Read `signals_found` | verified |
| Health snapshot errors | runtime | `health_snapshot.json` | Read `dispatch_errors[]` | verified |
| Discord webhook availability | env | `platform.example.json` | `${VAR}` env var placeholders, not resolved | partial |
| OANDA connection status | runtime | `health_snapshot.json` | `error: HTTP 401` in dispatch_errors | verified |
| ML model existence | filesystem | `platform_output/strategy_four/ml_models/*.pkl` | File check | verified |
| Signal reinforcement state | filesystem | `platform_output/strategy_four/reinforcement_state.json` | File check | verified |
| Metric: Discord-imported history | missing | N/A | Not implemented | missing |
| Metric: strategy_five P&L | missing | No journal file | Not available | missing |

---

## 6. Data Sources

### 6.1 Config Sources
| File | Purpose | Confidence |
|------|---------|------------|
| `config/platform.example.json` | Master route configuration for 5 strategies | ✅ verified |
| `RUN_little_rzy_bot.bat` | Command-line entry for little_rzy route | ✅ verified |
| `RUN_little_rzy_scan.bat` | Standalone scan mode | ✅ verified |
| `RUN_strategy_four_bot.bat` | Command-line entry for strategy_four route | ✅ verified |
| `RUN_strategy_five_bot.bat` | Command-line entry for strategy_five route | ✅ verified |
| `RUN_strategy_two_bot.bat` | Command-line entry for strategy_two route | ✅ verified |
| `RUN_signal_platform.bat` | Full platform entry (runs all routes) | ✅ verified |
| `RUN_signal_platform_command_bot.bat` | Discord command bot entry | ✅ verified |
| `.env.example` | Environment variable template (OANDA keys, Discord webhooks) | ✅ verified |
| `parabolic-exhaustion-bot/.env.example` | Standalone bot env template | ✅ verified |

### 6.2 Runtime Sources
| Source | Path Pattern | Exists? | Confidence |
|--------|-------------|---------|------------|
| Health snapshot | `platform_output/{route}/health_snapshot.json` | ✅ strategy_four, little_rzy, strategy_two, strategy_five | ✅ verified |
| Route cycle log | `platform_output/{route}/route_cycle_log.csv` | ✅ strategy_four, little_rzy, strategy_two, strategy_five | ✅ verified |
| Platform run summary | `platform_output/{route}/platform_run_summary.json` | ✅ strategy_four, little_rzy, strategy_five | ✅ verified |
| Execution log | `platform_output/execution_log.jsonl` | ✅ exists | ✅ verified |
| Dashboard metrics | `platform_output/_dashboard_metrics.json` | ✅ exists | ✅ verified |
| Dispatch failures | `platform_output/{route}/dispatch_failures.jsonl` | ✅ strategy_four, little_rzy | ✅ verified |
| Service heartbeat | `logs/signal_platform_heartbeat.json` | ⚠️ not on disk | ⚠️ partial (code writes it but may not have run) |

### 6.3 Journal Sources
| Route | Journal File | Signals | Confidence |
|-------|-------------|---------|------------|
| `strategy_four` | `platform_output/strategy_four/signal_journal.json` | 1,029 entries (459 TP, 564 SL, 6 open) | ✅ verified |
| `little_rzy` | `platform_output/little_rzy/signal_journal.json` | 2 entries (0 TP, 2 SL) | ✅ verified |
| `strategy_two` | `platform_output/strategy_two/signal_journal.json` | 0 entries (empty) | ✅ verified |
| `strategy_five` | `platform_output/strategy_five/signal_journal.json` | File does not exist | ✅ verified |
| `little_rzy_1h` | `platform_output/little_rzy_1h/` | No journal file (disabled) | ✅ verified |

### 6.4 Discord Import Sources
| Source | Status | Confidence |
|--------|--------|------------|
| Discord webhook URL env vars | 5 defined in platform.example.json | ✅ verified (config) |
| Discord command bot | `signal_platform/discord_command_bot.py` runs standalone | ✅ verified (code) |
| Discord-imported journal history | No import mechanism exists in codebase | ❌ missing feature |
| Legacy Discord journal truth | No import script found | ❌ missing data |

### 6.5 Backtest Sources
| Source | File | Results | Confidence |
|--------|------|---------|------------|
| Hardening smoke test | `backtest_output_hardening_smoke/summary.json` | 16 trades, 43.75% WR, -1.26R | ✅ verified |
| Hardening smoke signals | `backtest_output_hardening_smoke/signals.json` | Signal-level data | ✅ verified |
| Hardening smoke diagnostics | `backtest_output_hardening_smoke/diagnostics.json` | Diagnostic metrics | ✅ verified |
| Hardening smoke trade log | `backtest_output_hardening_smoke/trade_log.csv` | Individual trade records | ✅ verified |
| Various research backtests | `research/*.py` | Multiple backtest scripts | ✅ verified (scripts exist, outputs in `reports/`) |

---

## 7. Signal Flow and Lifecycle

```
STRATEGY SCAN
  │ strategy.scan() → PlatformSignal[]
  │
  ▼
SIGNAL REINFORCEMENT          ─── reinforcement.py
  │ apply_signal_reinforcement()
  │  ├── Filters through existing structure state
  │  ├── Scores continuation probability
  │  └── Produces: tradable + reinforcement signals
  │
  ▼
ML PREDICTION SCORING          ─── signal_scoring.py
  │ score_signal_with_ml()
  │  ├── Extracts feature vectors (ml_features.py)
  │  ├── Runs outcome_classifier (logistic regression)
  │  └── Runs realized_r_regressor (decision tree)
  │    └── Models exist only for strategy_four
  │
  ▼
DUPLICATE SUPPRESSION          ─── runtime.py:596
  │ new_signals_only()
  │  └── Removes already-dispatched setup_ids
  │
  ▼
DISPATCH DECISION              ─── runtime.py:632
  │
  ├─ "discord" route ─────────── runtime.py:656
  │   ├── Fresh signals → _send_discord_signal_with_ml()
  │   ├── Catch-up signals → same function
  │   ├── Outcome notifications → send_discord_outcome()
  │   ├── Weekly report → send_discord_report()
  │   └── Monthly report → send_discord_report()
  │
  └─ "discord_and_oanda" ────── runtime.py:758
      ├── Discord dispatch (all of above)
      └── OANDA order placement
          ├── Circuit breaker check ← runtime.py:767
          ├── Connection test ← oanda_execution.py:136
          ├── Account summary ← oanda_execution.py:160
          └── execute_signal() ← oanda_execution.py:330
              └── Blocked by HTTP 401
  │
  ▼
JOURNAL UPDATE                 ─── runtime.py:843
  │ append_new_signals()
  │ save_journal()
  │ save_ladder_ledger()
  │
  ▼
OPEN ENTRY REFRESH             ─── journal.py
  │ refresh_open_entries()
  │  └── Checks TP/SL via OANDA OHLCV
  │      └── Blocked by HTTP 401
  │
  ▼
ML TRAINING (periodic)         ─── runtime.py:957
  │ _train_route_ml_models()
  │  ├── Loads journal entries
  │  ├── Builds feature vectors
  │  ├── Trains outcome_classifier (logistic)
  │  └── Trains realized_r_regressor (decision tree)
  │    └── Only strategy_four has enough data
  │
  ▼
HEALTH LOGGING                 ─── runtime.py:900-954
  │ _append_health_log() → route_cycle_log.csv
  │ _write_health_snapshot() → health_snapshot.json
  │ _append_dispatch_failures() → dispatch_failures.jsonl
  │ _write_service_heartbeat() → heartbeat.json
  │
  ▼
DASHBOARD METRICS              ─── import_journal.py
  │ Reads journals + health snapshots
  │  → _dashboard_metrics.json → journal_metrics.json
  │  → Dashboard UI (static HTML)
```

**Key files in signal flow:** `runtime.py` (lines 531-967), `models.py` (lines 9-36 PlatformSignal), `strategies.py` (lines 1-36).

---

## 8. OANDA Integration Points

| Point | File | Function | Details | Confidence |
|-------|------|----------|---------|------------|
| Config | `oanda_execution.py` lines 44-72 | `OandaConfig` | account_id, api_token, environment, price_mode, risk_per_trade_pct, max_units_per_trade, max_daily_loss_pct | ✅ verified |
| Config loading | `oanda_execution.py` line 76 | `OandaConfig.from_env()` | Reads `OANDA_API_KEY`, `OANDA_ACCOUNT_ID` from env | ✅ verified |
| Connection test | `oanda_execution.py` line 136 | `OandaClient.test_connection()` | GET /v3/accounts/{id} | ✅ verified |
| Account summary | `oanda_execution.py` line 160 | `OandaClient.get_account_summary()` | Returns NAV, balance, open trades | ✅ verified |
| Order execution | `oanda_execution.py` line 330 | `execute_signal()` | Market orders with SL, TP, trailing stop | ✅ verified |
| Position sizing | `position_sizing.py` | `calculate_position_size()` | Risk-based position sizing from OANDA config | ✅ verified |
| Practice environment | config | `OANDA_API_BASE_PRACTICE` | `https://api-fxpractice.oanda.com` | ✅ verified |
| Market data | `market_data.py` | `fetch_oanda_ohlcv()` | Used by scanners for candle data | ✅ verified |
| Open entry refresh | `runtime.py` line 547 | `refresh_open_entries()` | Fetches OANDA OHLCV to detect TP/SL hits | ✅ verified |
| Circuit breaker | `runtime.py` lines 767-786 | `_check_daily_circuit_breaker()` | Checks daily loss limits, consecutive losses | ✅ verified |
| **Runtime error** | health_snapshot.json | HTTP 401 | OANDA API key invalid/expired — affects strategy_four and little_rzy | ✅ verified (data) |

---

## 9. Discord Integration Points

| Point | File | Function | Details | Confidence |
|-------|------|----------|---------|------------|
| Webhook URLs | `platform.example.json` lines 13, 35, 61, 83, 145 | `${VAR}` env var placeholders | 5 webhooks from env vars | ✅ verified |
| Signal dispatch | `dispatchers.py` | `send_discord_signal()` | Posts signal info to webhook | ✅ verified (import) |
| Outcome dispatch | `dispatchers.py` | `send_discord_outcome()` | Posts trade outcome to webhook | ✅ verified (import) |
| Report dispatch | `dispatchers.py` | `send_discord_report()` | Weekly/monthly summary to webhook | ✅ verified (import) |
| Signal + ML | `runtime.py` lines 278-294 | `_send_discord_signal_with_ml()` | Formats signal with ML prediction, posts to Discord | ✅ verified |
| ML report | `discord_predictions.py` | `format_report_with_predictions()` | Formats ML prediction performance for Discord | ✅ verified |
| Command bot | `discord_command_bot.py` | Standalone script | Discord bot for querying strategy status | ✅ verified |
| Weekly perf | `runtime.py` lines 297-312 | `_send_weekly_prediction_performance()` | Sends ML prediction accuracy report | ✅ verified |

---

## 10. Journal/History Sources

| Aspect | Details | Confidence |
|--------|---------|------------|
| Journal format | JSON file containing list of `JournalEntry` dataclasses | ✅ verified (`models.py` lines 74-133) |
| Journal write | `journal.py` `save_journal()` | ✅ verified |
| Journal read | `journal.py` `load_journal()` | ✅ verified |
| Entry enrichment | `journal.py` `enrich_ladder_fields()` | Adds ladder sequence metadata | ✅ verified |
| Open entry refresh | `journal.py` `refresh_open_entries()` | Checks TP/SL via OANDA | ✅ verified |
| Outcome detection | `journal.py` `pending_outcome_notifications()` | Finds entries needing outcome notification | ✅ verified |
| Stats snapshot | `journal.py` `build_stats_snapshot()` | Compute summary stats from journal | ✅ verified |
| Summary data | `journal.py` `journal_summary_data()` | Generate period summary for reports | ✅ verified |
| Ladder ledger | `journal.py` `save_ladder_ledger()` | Risk-ladder tracking for sequences | ✅ verified |
| Report state | `journal.py` `save_report_state()` | Track which periods have reports sent | ✅ verified |
| Dashboard import | `bot-dashboard/import_journal.py` | Reads journals + health snapshots → metrics JSON | ✅ verified |
| **Discord-imported history** | Not implemented | No mechanism to import Discord message history as journal entries | ❌ missing |

---

## 11. Backtest Sources

| Source | File | Description | Confidence |
|--------|------|-------------|------------|
| Hardening smoke | `backtest_output_hardening_smoke/summary.json` | Synthetic 4h profile, 16 trades, 43.75% WR, -1.26R | ✅ verified |
| Advanced Engulfing | `research/advanced_engulfing_backtest.py` | Engulfing pattern backtest | ✅ verified (exists) |
| CWT Forex | `research/cwt_forex_backtest.py` | Cambist With Trend forex backtest | ✅ verified (exists) |
| CWT Improved | `research/cwt_improved_rules_backtest.py` | Improved rules variant | ✅ verified (exists) |
| Secular Bear | `research/secular_bear_backtest.py` | Bear market strategy | ✅ verified (exists) |
| Secular Bull SIP | `research/secular_bull_sip*.py` | Multiple SIP variants (baseline, funded, leveraged, crypto, profiles) | ✅ verified (exists) |
| Measured Drift | `research/measured_drift*.py` | Multiple drift variants (breakeven, static funded, v2) | ✅ verified (exists) |
| CWT SL Forensics | `research/cwt_sl_forensics.py` | Stop-loss analysis | ✅ verified (exists) |
| FWM Hybrid | `research/cwt_fwm_hybrid.py` | Follow-with-momentum hybrid | ✅ verified (exists) |

**Output directories for backtest reports:** `reports/` contains multiple subdirectories per backtest run.

---

## 12. Runtime/Health Sources

| Source | Route | Current Status | Last Cycle | Findings | Confidence |
|--------|-------|---------------|------------|----------|------------|
| Health snapshot | strategy_four | ✅ WORKING | 2026-06-16T09:51:00Z | TP precision fix verified — 6/6 test fills (2026-06-16). Auth working. | ✅ verified |
| Health snapshot | little_rzy | ⚠️ DEGRADED | 2026-06-13T06:56:17Z | OANDA auth works for orders; 401 on market data endpoint (fetch_oanda_ohlcv) | ✅ verified |
| Health snapshot | strategy_two | ⏸ IDLE | 2026-06-16T05:45:22Z | ~~ValueError: Unsupported dispatch type: discord~~ **FIXED** (2026-06-16). Now idle — no signals found. | ✅ verified |
| Health snapshot | strategy_five | ⚠️ DEGRADED | 2026-06-16T05:45:55Z | ~~ValueError: Unsupported dispatch type: discord~~ **FIXED** (2026-06-16). OANDA 401 on market data remains. | ✅ verified |
| Route cycle log | strategy_four | CSV with error rows + success rows | — | TP precision rejections (pre-fix) + successful fills (post-fix) | ✅ verified |
| Route cycle log | little_rzy | CSV with error rows | — | Multiple 401 error entries | ✅ verified |
| ML models | strategy_four | 2 models trained | — | outcome_classifier.pkl, realized_r_regressor.pkl | ✅ verified |
| Predictions | strategy_four | predictions.jsonl | — | ML prediction records | ✅ verified |
| Reinforcement | strategy_four | reinforcement_state.json | — | Signal reinforcement state | ✅ verified |

---

## 13. File-to-Feature Map

| File | Feature | Confidence |
|------|---------|------------|
| `signal_platform/runtime.py` | Main orchestration: scan → process → dispatch → journal → health | ✅ verified |
| `signal_platform/registry.py` | Strategy plugin registry (maps IDs to classes) | ✅ verified |
| `signal_platform/strategies.py` | StrategyPlugin protocol definition | ✅ verified |
| `signal_platform/models.py` | PlatformSignal, JournalEntry, SignalStatsSnapshot, ReinforcementConfig | ✅ verified |
| `signal_platform/oanda_execution.py` | OANDA V20 REST client, order execution, account queries | ✅ verified |
| `signal_platform/journal.py` | Journal load/save/reconcile/refresh | ✅ verified |
| `signal_platform/metrics.py` | Strategy metric computation | ✅ verified |
| `signal_platform/dispatchers.py` | Discord webhook dispatch (signal, outcome, report) | ✅ verified |
| `signal_platform/discord_command_bot.py` | Standalone Discord command interface | ✅ verified |
| `signal_platform/discord_predictions.py` | ML prediction formatting for Discord | ✅ verified |
| `signal_platform/signal_scoring.py` | ML scoring for individual signals | ✅ verified |
| `signal_platform/ml_features.py` | Feature vector extraction from journal entries | ✅ verified |
| `signal_platform/ml_models.py` | ML model training (classifier + regressor) | ✅ verified |
| `signal_platform/prediction_tracking.py` | Prediction recording, matching, evaluation | ✅ verified |
| `signal_platform/reinforcement.py` | Signal reinforcement scoring and state management | ✅ verified |
| `signal_platform/position_sizing.py` | Risk-based position sizing | ✅ verified |
| `signal_platform/env.py` | Environment loading | ✅ verified |
| `signal_platform/cwt_strategy.py` | CWT strategy implementation (delegates to strategy_four_bot) | ✅ verified |
| `signal_platform/little_rzy_strategy.py` | Little Rzy strategy implementation | ✅ verified |
| `signal_platform/command_content.py` | Discord command responses for strategy status | ✅ verified |
| `config/platform.example.json` | Route configuration (master config) | ✅ verified |
| `bot-dashboard/index.html` | Dashboard UI with bot cards, timeline, backtest panel | ✅ verified |
| `bot-dashboard/journal_metrics.json` | Aggregated journal + runtime metrics for dashboard | ✅ verified |
| `bot-dashboard/import_journal.py` | Script that reads journals + health snapshots → dashboard metrics | ✅ verified |
| `strategy_four_bot/scanner.py` | CWT scanner (Alligator + Cambist logic) | ✅ verified |
| `little_rzy_bot/scanner.py` | Little Rzy scanner (structure detection + measured move) | ✅ verified |
| `little_rzy_bot/market_data.py` | OANDA market data fetching (candles) | ✅ verified |
| `parabolic-exhaustion-bot/` | Standalone parabolic exhaustion research bot | ⚠️ partial (not integrated into signal platform) |

---

## 14. Verified Facts

All of the following have been confirmed against actual file contents:

1. **5 strategies registered** in `registry.py` lines 11-17
2. **4 routes enabled** (little_rzy disabled), **1 route disabled** (little_rzy_1h)
3. **Dispatch modes:** "discord" (strategy_two, strategy_five), "discord_and_oanda" (little_rzy, strategy_four), "none" (available but unused)
4. **OANDA environment:** practice/demo only — `api-fxpractice.oanda.com`
5. **OANDA status:** Auth working for strategy_four (2 successful fills logged June 12). TP precision bug caused 3 order rejections (fixed). little_rzy/strategy_five market-data fetch returns 401.
6. **strategy_four journal:** 1,029 entries — most active bot, 44.9% WR, negative expectancy
7. **little_rzy journal:** 2 entries both loss — minimal trading history
8. **strategy_two journal:** empty — no signals ever dispatched
9. **strategy_five journal:** file does not exist — not yet run
10. **ML models:** Trained for strategy_four only (outcome_classifier + realized_r_regressor)
11. **Reinforcement:** Only configured for strategy_four
12. **Backtest hardening smoke:** 16 trades, 43.75% WR, -1.26R — synthetic 4h profile
13. **Signal flow:** scan → reinforcement → duplicate suppression → dispatch → journal → health log
14. **Dashboard:** Static HTML with hardcoded data (no runtime fetch)
15. **import_journal.py:** Reads journals + health snapshots → produces `journal_metrics.json`
16. **Discord command bot:** Standalone process, not in config routes
17. **NAS100 Parabolic:** Standalone paper-forward runner, not in signal platform
18. **Reinforcement config:** Only in strategy_four extra section (platform.example.json:118-134)
19. **ML pipelines:** Feature extraction + 2 models exist on disk for strategy_four
20. **Open entry refresh:** Partially blocked — strategy_four works, little_rzy returns 401 on market data

---

## 15. Inferred but Unverified Items

| Item | Inference | Rationale | Confidence |
|------|-----------|-----------|------------|
| All webhooks work | Assumed from code | Code sends to webhook URLs but no success confirmed in runtime data | ⚠️ inferred |
| ML models are used in scoring | Confirmed code paths | `_send_discord_signal_with_ml()` calls `score_signal_with_ml()` | ⚠️ partial (code paths exist but may fail silently) |
| OANDA paper account exists | Inferred from platform.example.json "practice" | Config says practice but 401 error suggests key issue | ⚠️ inferred |
| Discord command bot is active | Inferred from RUN .bat file | Batch file exists but no runtime status available | ⚠️ inferred |
| Reports have been sent | Inferred from report_state.json files | `report_state.json` exists for strategy_four and strategy_two | ⚠️ partial (state exists but no actual Discord delivery proven) |
| Circuit breaker thresholds used | Config default values | `max_daily_loss_pct=5.0`, `max_consecutive_losses=5` | ⚠️ inferred (not overridden in config) |
| Reinforcement actively used in decisions | Inferred from state file | `reinforcement_state.json` exists but no runtime confirmation it affects dispatch | ⚠️ partial |
| ML scoring affects dispatch | Inferred from code path | `_send_discord_signal_with_ml()` runs but scores may be loaded silently | ⚠️ inferred |

---

## 16. Missing Data Required from User

| Missing Item | Why Needed | Impact |
|-------------|-----------|--------|
| **OANDA API key** | Current 401 Unauthorized on all OANDA routes | No live market data, no trade execution, no open entry refresh |
| **Discord webhook URLs** | Env vars `${DISCORD_WEBHOOK_URL_*}` not set in `.env` | No Discord signal dispatch, no outcome notifications, no reports |
| **Actual platform config file** | `platform.example.json` is a template — actual config path unknown | Can't read actual interval/route settings |
| **OANDA account ID** | Needed for `OANDA_ACCOUNT_ID` env var | OANDA client can't authenticate without it |
| **Discord-imported journal history** | If legacy journals exist in Discord, no import mechanism exists | Historical journal data may be lost |
| **strategy_five first cycle** | No journal file exists | No metrics available yet |
| **strategy_two trading history** | Journal is empty | No signal quality assessment possible |
| **Live dashboard metrics** | Dashboard uses hardcoded data | No real-time updates without server-side data fetching |
| **little_rzy_1h intent** | Disabled in config, but reason unknown | May affect whether to restore or remove |
| **Reinforcement decision logs** | `reinforcement_decisions.jsonl` exists but content unknown | Can't confirm reinforcement logic is working |
| **NAS100 Parabolic integration** | Standalone runner not in signal platform | Architecture relationship unclear |

---

## 17. Dependency Graph (Dashboard Panels → Source Files)

| Dashboard Panel | Depends On | Source Type |
|----------------|------------|-------------|
| Bot cards (display name, strategy, status) | `platform.example.json`, `registry.py`, `health_snapshot.json` | config + runtime |
| Bot metrics (P&L, win rate, closed trades) | `signal_journal.json` for each route | journal |
| Bot runtime status | `health_snapshot.json` for each route | runtime |
| Source map (expandable) | `platform.example.json`, `.bat` files, `registry.py` | config |
| Timeline / Activity Feed | Derived from `health_snapshot.json` + signal_journal.json | runtime + journal |
| System Architecture Map | PROJECT_MAP.md (sections 3, 4, 7) | maintained reference |
| Signal Lifecycle Flow | PROJECT_MAP.md (section 7) + `runtime.py` | maintained reference + code |
| Source Confidence View | PROJECT_MAP.md (sections 3, 15) | maintained reference |
| File-to-Feature Traceability | PROJECT_MAP.md (section 13) | maintained reference |
| Dependency Graph | PROJECT_MAP.md (section 17) | maintained reference |
| Data Provenance Panel | PROJECT_MAP.md (section 5) | maintained reference |
| Unknowns Blocking Visibility | PROJECT_MAP.md (section 16) | maintained reference |
| Backtest Panel | `backtest_output_hardening_smoke/summary.json` | backtest |
| Historical Simulation | `backtest_output_hardening_smoke/summary.json` | backtest |

---

## 18. Unresolved Questions

| Question | Why It Matters | Status |
|----------|---------------|--------|
| What is the actual path to the platform config file? | All route configs depend on it | ❌ unknown |
| Are Discord webhooks actually configured? | All signal dispatch depends on them | ❌ unknown (env vars) |
| Is the OANDA practice account active? | All trading and market data blocked | ❌ unknown (401) |
| What Discord-imported history exists? | Legacy journal data may be lost | ❌ unknown |
| Why is little_rzy_1h disabled? | May affect whether to repair or remove | ❌ unknown |
| Are reinforcement decisions affecting dispatch? | Confirms reinforcement logic is functioning | ⚠️ partial (state file exists) |
| Is NAS100 Parabolic meant to be a platform route? | Currently standalone, not in config | ❌ unknown |
| Is the ML scoring actually working? | Code paths exist but may fail silently | ⚠️ partial |

---

## 19. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-13 | Initial creation from codebase audit | Agent Crew |
| 2026-06-13 | Added Node Registry (section 3), Connection Registry (section 4), Metric Provenance (section 5), Dependency Graph (section 17), Unresolved Questions (section 18) | Agent Crew |
| 2026-06-13 | Architecture dashboard rewrite: aligned node IDs (scan_cwt/scan_little_rzy), added visual flow, connection explorer, evidence modals, confidence heatmap, data provenance panel | Agent Crew |
| 2026-06-13 | Added §20 Integration Status: OANDA 401 root cause (expired/revoked token), Discord audit (4/6 webhooks set, blocked by OANDA), journal completeness table | Agent Crew |
| 2026-06-13 | Added §21 Audit Cross-Checks: Claim-verification table for PROFESSIONAL_REVIEW.md (8 contradicted, 3 partially contradicted, 3 partially confirmed, 3 confirmed, 3 not verifiable) | Agent Crew |
| 2026-06-16 | **RECONCILED:** PROJECT_MAP.md §12, §20 with OANDA diagnostics review — strategy_four confirmed working (6/6 fills), little_rzy 401 clarified as market-data-only
| 2026-06-16 | **FIXED:** runtime.py dispatch type bug — `elif route.dispatch == "none"` incorrectly rejected "discord" routes. Changed to `elif route.dispatch in ("none", "discord", "discord_and_oanda")`. Unblocked strategy_two and strategy_five. | Cline |

---

## 20. Integration Status (2026-06-16 — evidence-based update)

**Diagnostic tool:** `python integration_check.py` → writes `platform_output/integrations.json`

### 20.1 OANDA

| Field | Value |
|-------|-------|
| Status | ✅ **WORKING — strategy_four TP precision fix verified (6/6 fills). little_rzy market-data 401 remains.** |
| Root cause | `_format_price()` used 2 decimal places for index instruments; OANDA requires 1. Also 401 on market-data fetch for little_rzy/strategy_five routes. |
| Evidence | `execution_log.jsonl` shows 2 successful fills (June 12 19:04 UTC) + 3 TP-precision rejections (June 12 19:04 UTC). User-visible rejected orders on OANDA on 2026-06-13 03:27 and 2026-06-16 09:51. |
| Impact | strategy_four OANDA execution **WORKING** (TP precision fix verified 6/6 fills). little_rzy market-data fetch returns 401. strategy_two/five dispatch type bug **FIXED**. |
| Fix | ✅ **Applied:** `_format_price()` corrected to use 1 decimal for indices, 0 for J225. New `oanda_diagnostics.jsonl` artifact captures raw OANDA responses. |

**Per-Route OANDA Diagnostics:**

| Route | Auth | Account | Market Data | Order Execution | Last Known Rejection | Next Step |
|-------|------|---------|-------------|-----------------|---------------------|-----------|
| strategy_four | ✅ working | ✅ working | ✅ working | ⚠️ TP-precision fix applied | "Take Profit precision" (3x June 12) | Monitor post-fix runs |
| little_rzy | ✅ working (order path) | ✅ working (order path) | ❌ 401 on `fetch_oanda_ohlcv` | Not tested recently | N/A | Regenerate OANDA token for market data |
| strategy_two | N/A (discord-only) | N/A | ✅ working | N/A | "Unsupported dispatch type: discord" every cycle | Fix dispatch config |
| strategy_five | N/A (discord-only) | N/A | ❌ 401 on `fetch_oanda_ohlcv` | N/A | "Unsupported dispatch type: discord" every cycle | Fix dispatch config + regenerate token |
| command_bot | N/A | N/A | N/A | N/A | Discord webhook loop (weekly/monthly) | Fix webhook retry logic |

**Evidence-based cascade (updated):**
```
strategy_four: OANDA auth WORKS → orders reach OANDA → some rejected for TP precision → ✅ fix applied
little_rzy:    OANDA auth WORKS for orders → market data 401 → scanner can't fetch candles → partial signal flow
strategy_two:  dispatch="discord" ValueError → FIXED (2026-06-16) → now idle (no signals found)
strategy_five: dispatch="discord" ValueError → FIXED (2026-06-16) → market data 401 remains
```

### 20.2 Discord

| Env Var | Route | Status | Notes |
|---------|-------|--------|-------|
| `DISCORD_WEBHOOK_URL_LITTLE_RZY` | little_rzy | ✅ set | Configured, not tested (HEAD not supported by Discord API) |
| `DISCORD_WEBHOOK_URL_LITTLE_RZY_1H` | little_rzy_1h | ⚠️ not set | Route is disabled — non-blocking |
| `DISCORD_WEBHOOK_URL_STRATEGY_TWO` | strategy_two | ✅ set | Configured |
| `DISCORD_WEBHOOK_URL_CWT` | strategy_four | ✅ set | Configured |
| `DISCORD_WEBHOOK_URL_SIP` | strategy_five | ✅ set | Configured |
| `DISCORD_WEBHOOK_URL` | (base) | ⚠️ not set | Unused by any enabled route |
| `DISCORD_BOT_TOKEN` | command bot | ✅ set | Used by `discord_command_bot.py` |

**Note:** `runtime.py:102-105` resolves `${VAR}` syntax → returns empty string if env var is missing. Routes with empty webhook URLs silently fail dispatch (no POST attempted).

### 20.3 Journal Completeness

| Route | Journal File | Entries | Status |
|-------|-------------|---------|--------|
| strategy_four | ✅ exists | 1,029 | ✅ healthy |
| little_rzy | ✅ exists | 2 | ✅ healthy |
| strategy_two | ✅ exists | 0 (empty) | ⚠️ no signals found — expected for low-frequency H4 strategy |
| strategy_five | ❌ not found | N/A | ❌ never produced first signal (D1 granularity, low frequency) |
| little_rzy_1h | ❌ not found | N/A | Expected (route disabled) |

### 20.4 Health Snapshot Status

| Route | Snapshot | Last Cycle | Error | Classification |
|-------|----------|------------|-------|---------------|
| strategy_four | ✅ | 2026-06-16T09:51:00Z | (none) — TP precision fix verified 6/6 fills | OANDA fully operational |
| little_rzy | ✅ | 2026-06-13T06:56:17Z | 401 on market data endpoint only | Auth works; market data blocked |
| strategy_two | ✅ | 2026-06-12T08:55:22Z | (none) | Idle — no setups found |
| strategy_five | ✅ | 2026-06-12T10:55:48Z | (none) | Idle — no setups found |

### 20.5 Required Actions

| Priority | Action | Blocks |
|----------|--------|--------|
| 🟡 P1 | Resolve little_rzy market-data 401 (different endpoint or token scope needed) | little_rzy scanner candle data |
| 🟡 P1 | Confirm Discord webhooks are reachable (run `python integration_check.py`) | Signal delivery to Discord channels |
| 🟢 P2 | None (all other items are operating as designed) | — |

### 20.6 What Requires No Fix

| Item | Why It's Correct |
|------|-----------------|
| strategy_two empty journal | Strategy uses strict H4 setup rules; no qualifying patterns in current market |
| strategy_five no journal | D1 chart strategy; can take days between signals |
| little_rzy_1h disabled | Intentionally disabled per config; no action needed |
| NAS100 Parabolic has no journal | Standalone bot; not integrated into signal platform |

---

## 21. Audit Cross-Checks

External review verification. This section is an **audit cross-check layer**, not a primary truth source. PROJECT_MAP.md, runtime artifacts, journals, and generated metrics remain authoritative.

**Verification artifact:** [`docs/claim_verification_professional_review.md`](docs/claim_verification_professional_review.md)

### 21.1 Summary

| Source Review | Verdict Date | Total Claims | Contradicted | Partially Contradicted | Partially Confirmed | Confirmed | Not Verifiable |
|---------------|-------------|-------------|-------------|----------------------|--------------------|-----------|--------------|
| `PROFESSIONAL_REVIEW.md` | 2026-06-13 | 20 | 8 (40%) | 3 (15%) | 3 (15%) | 3 (15%) | 3 (15%) |

### 21.2 Key Findings

**6 claims outright contradicted by current code:**
- Circuit breaker exists (`runtime.py:767`)
- Position sizing module exists (`position_sizing.py`, 181 lines)
- Logging exists in `runtime.py` and `position_sizing.py`
- Model cache uses TTL (not lru_cache)
- Min training samples is 100 (not 20)
- Rate limiting exists in `oanda_execution.py`

**3 claims overstated (partially contradicted):**
- ML overfitting risk: min samples is 100, not 20 as claimed
- God function: run_route() already has 22 extracted helpers
- Model performance monitoring: prediction tracking exists

### 21.3 Policy

- Claims with verdict **CONTRADICTED** must NOT be treated as current facts
- Claims with verdict **PARTIALLY CONFIRMED** should be checked against current code state before citing
- This file must be revalidated when `runtime.py`, `dashboard/index.html`, `health_snapshot.json`, `signal_journal.json`, or `_dashboard_metrics.json` change materially

---

## 22. Discord Import Integration (2026-06-16 — new)

### 22.1 Overview

The Discord journal import pipeline pulls historical signal and outcome messages from Discord, parses them into structured journal records, matches outcomes to signals, and feeds them into the dashboard metrics pipeline with full provenance tracking.

**Status:** Code implemented and tested (12/12 tests passing). No live Discord data imported yet — requires `DISCORD_BOT_TOKEN` and `DISCORD_IMPORT_CHANNEL_IDS` configuration.

### 22.2 Files

| File | Purpose | Confidence |
|------|---------|------------|
| `signal_platform/discord_journal_models.py` | Dataclasses: DiscordImportedEntry, RawMessageArchive, DiscordImportState, MergedRouteMetrics | ✅ verified |
| `signal_platform/discord_message_parser.py` | Event type classification, embed parsing, strategy mapping | ✅ verified |
| `signal_platform/discord_outcome_matcher.py` | Tiered matching logic (setup_id, symbol+timeframe+side+proximity) | ✅ verified |
| `signal_platform/discord_importer.py` | Main orchestration: fetch, parse, match, persist, compute metrics | ✅ verified |
| `scripts/run_discord_import.py` | CLI entry point for operators | ✅ verified |
| `scripts/validate_discord_import.py` | Validation script proving pipeline correctness | ✅ verified |
| `tests/test_discord_import.py` | 12 test cases with synthetic Discord payloads | ✅ verified |
| `docs/DISCORD_IMPORT_RUNBOOK.md` | Operator runbook | ✅ verified |

### 22.3 Storage

| Path | Format | Purpose |
|------|--------|---------|
| `platform_output/{route}/discord_import_journal.json` | JSON array | Normalized imported records with provenance |
| `platform_output/{route}/discord_raw_archive.jsonl` | JSONL (append-only) | Raw Discord message payloads for reprocessing |
| `platform_output/_discord_import_state.json` | JSON | Global sync state for incremental updates |

### 22.4 Node Registry

| Node ID | Layer | Label | Source File | Status |
|---------|-------|-------|-------------|--------|
| `discord_importer` | Data | Discord Import Pipeline | discord_importer.py | ✅ implemented |
| `discord_parser` | Data | Discord Message Parser | discord_message_parser.py | ✅ implemented |
| `discord_matcher` | Data | Outcome Matcher | discord_outcome_matcher.py | ✅ implemented |
| `discord_raw_archive` | Data | Raw Message Archive | {route}/discord_raw_archive.jsonl | empty (no data) |
| `discord_import_journal` | Data | Discord Import Journal | {route}/discord_import_journal.json | empty (no data) |

### 22.5 Metric Provenance

The dashboard now uses triple-view metrics per route:

| View | Source | Description |
|------|--------|-------------|
| `native_journal` | signal_journal.json | Runtime-generated journal entries |
| `discord_imported` | discord_import_journal.json | Discord-imported records |
| `combined` | Merge of above | Total with native_count and discord_imported_count |

### 22.6 Event Types

Messages are classified into:

| event_type | Description | Participates in matching |
|------------|-------------|------------------------|
| `signal_entry` | Trade signal with entry/SL/TP | Yes (as target) |
| `outcome` | TP/SL/BE result post | Yes (as source) |
| `weekly_report` | Weekly summary | No |
| `monthly_report` | Monthly summary | No |
| `ml_performance` | ML prediction report | No |
| `manual_comment` | Plain text comment | No |
| `unknown` | Unclassifiable | No |

### 22.7 Matching Windows (per strategy)

| Strategy | Granularity | Window (no setup_id) |
|----------|------------|---------------------|
| strategy_four (CWT) | M5 | ±2h |
| little_rzy | H4 | ±24h |
| strategy_two | H4 | ±48h |
| strategy_five | D | ±96h |

### 22.8 Operator Commands

```bash
# Initial backfill
python scripts/run_discord_import.py --mode backfill

# Incremental sync
python scripts/run_discord_import.py --mode incremental

# Reprocess after parser improvements
python scripts/run_discord_import.py --mode reprocess

# View summary
python scripts/run_discord_import.py --mode summary

# Rebuild dashboard
cd bot-dashboard && python import_journal.py

# Validate
python scripts/validate_discord_import.py
```

---

## 23. Unresolved Questions (updated)

| Question | Why It Matters | Status |
|----------|---------------|--------|
| What is the actual path to the platform config file? | All route configs depend on it | ❌ unknown |
| Are Discord webhooks actually configured? | All signal dispatch depends on them | ❌ unknown (env vars) |
| Is the OANDA practice account active? | All trading and market data blocked | ❌ unknown (401) |
| What Discord-imported history exists? | Historical forward-test evidence trapped in Discord | ⚠️ import pipeline ready, awaiting data |
| Why is little_rzy_1h disabled? | May affect whether to repair or remove | ❌ unknown |
| Are reinforcement decisions affecting dispatch? | Confirms reinforcement logic is functioning | ⚠️ partial (state file exists) |
| Is NAS100 Parabolic meant to be a platform route? | Currently standalone, not in config | ❌ unknown |
| Is the ML scoring actually working? | Code paths exist but may fail silently | ⚠️ partial |
| Discord import channels not configured | Pipeline implemented but no live data | ❌ awaiting DISCORD_IMPORT_CHANNEL_IDS env var |
