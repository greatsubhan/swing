 n# swing-pr1 Professional Code Review

**Date:** 2026-06-13
**Scope:** Architecture, Code Quality, Trading Logic, Risk Management, ML Pipeline, Testing

---

## Executive Summary

This is a multi-strategy swing trading signal platform with a shared Discord-first runtime. The project has a solid foundation: modular strategy design, shared dispatch infrastructure, journaling, and ML-based signal scoring. However, critical gaps exist in risk management, production hardening, and testing that expose the system to unnecessary financial loss.

**Top findings by impact:**

| Priority | Issue | Financial Impact |
|----------|-------|-----------------|
| CRITICAL | No drawdown protection or circuit breaker | Unlimited loss potential |
| CRITICAL | No dynamic position sizing | Over-exposure per trade |
| CRITICAL | Silent error swallowing masks API failures | Signals lost, trades missed |
| HIGH | No trailing stops or time-based exits | Profits left on the table |
| HIGH | ML pipeline overfits on small samples | Bad signals scored as good |
| HIGH | 460-line god function in runtime | Unmaintainable risk logic |
| MEDIUM | No Python logging anywhere | Invisible failures in production |
| MEDIUM | O(n^2) pivot scanning | Slow scans on larger watchlists |
| MEDIUM | Only 14 tests for 40+ source files | No safety net for changes |

---

## PART 1: CRITICAL QUICK WINS (Do Tonight)

These are changes that directly reduce financial loss risk with minimal refactoring.

### 1.1 Add a Circuit Breaker to run_route()

**File:** `signal_platform/runtime.py`
**Problem:** The `run_route()` function (460 lines) has no mechanism to stop trading after consecutive losses or daily loss thresholds are breached.
**Impact:** If a strategy enters a bad regime, it continues dispatching signals without limit.

**Fix:** Add a `risk_guard` check at the top of `run_route()` that reads the journal, counts today's P&L, and refuses to dispatch new signals if the daily loss limit is hit.

**Implementation sketch:**

```python
def _check_daily_risk_guard(journal_path: str, route_cfg: dict) -> dict:
    """Check if daily loss limit has been breached."""
    risk_cfg = route_cfg.get("risk", {})
    max_daily_loss_pct = risk_cfg.get("max_daily_loss_pct", 5.0)
    max_daily_trades = risk_cfg.get("max_daily_trades", 10)

    # Load journal, count today's closed trades
    # Calculate cumulative P&L
    # Return {"halted": bool, "reason": str, "daily_pnl": float}
```

### 1.2 Fix Silent Error Swallowing

**Files:** `signal_platform/journal.py`, `signal_platform/signal_scoring.py`, `signal_platform/runtime.py`
**Problem:** Broad `except Exception` blocks silently catch errors and store them in dicts or strings without logging. API failures, data corruption, and market data gaps are invisible to operators.

**Evidence:**
- `journal.py` line 319: bare `except Exception` stores error in `raw_signal` field
- `signal_scoring.py` line 65: catches all exceptions, appends `str(exc)` to score dict
- `runtime.py`: multiple broad catches that write to health snapshots but never call `logging.error()`

**Fix:** Replace every bare `except Exception` with `logging.exception("Context message")` at minimum. Add a structured logging module.

### 1.3 Add Structured Logging

**Problem:** The entire platform has zero `logging.info()` or `logging.error()` calls. All diagnostics go to JSON files that require manual inspection. During long-running `serve` mode, operators have no visibility.

**Fix:** Add a shared logging setup:

```python
# signal_platform/logging_config.py
import logging
import sys

def setup_logging(level="INFO", log_file=None):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)
```

Call `setup_logging()` from `__main__.py` at startup. Then replace all print-based diagnostics with `logger.info()` / `logger.error()` / `logger.warning()`.

---

## PART 2: RISK MANAGEMENT IMPROVEMENTS (Make More Money, Lose Less)

### 2.1 Missing Drawdown Protection

**Problem:** There is zero systematic drawdown protection. No route has daily loss limits, weekly loss limits, maximum concurrent trades, or maximum risk per period.

**What to add to `config/platform.example.json`:**

```json
{
  "risk": {
    "max_daily_loss_pct": 2.0,
    "max_weekly_loss_pct": 5.0,
    "max_concurrent_trades": 6,
    "max_risk_per_trade_pct": 1.0,
    "max_correlated_trades": 3,
    "cooldown_after_consecutive_losses": 3,
    "cooldown_minutes": 60
  }
}
```

### 2.2 No Dynamic Position Sizing

**Problem:** The platform generates signals with entry, stop-loss, and target prices but never calculates position size based on account equity and risk per trade. Signals are dispatched to Discord without knowing how large a position the trader should take.

**Fix:** Add a `position_sizer` module:

```python
# signal_platform/position_sizing.py

def calculate_position_size(
    account_equity: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    instrument: str,
    pip_value: float = 0.0001,
) -> dict:
    """Kelly-inspired position sizing based on risk per trade."""
    risk_amount = account_equity * (risk_per_trade_pct / 100.0)
    stop_distance = abs(entry_price - stop_loss_price)
    if stop_distance == 0:
        return {"units": 0, "reason": "zero stop distance"}

    units = risk_amount / stop_distance
    return {
        "units": round(units),
        "risk_amount": risk_amount,
        "stop_distance_pips": stop_distance / pip_value,
    }
```

Integrate into the signal dispatch flow so Discord messages include recommended position size.

### 2.3 No Trailing Stop or Time-Based Exit

**Problem:** Stop-losses are placed at structure levels with ATR padding, but once set they never move. There is no trailing stop to lock in profits, and no time-based exit to close stale positions.

**Where stop-losses are set:**
- `little_rzy_bot/structure_detection.py` lines 131-134 and 216-219: `stop = pullback_high/low +/- (atr_stop_padding * ATR)`

**What to add:**
- Trailing stop that moves to breakeven after 1R profit
- Chandelier exit option: stop trails at highest high minus ATR multiplier
- Time-based exit: close signals older than `max_hold_bars` without hitting target

### 2.4 Stop-Loss is Too Generous on Some Setups

**Problem:** The ATR padding multiplier for stop-losses is configurable but defaults to values that can produce very wide stops relative to the entry. Combined with the measured move target, this creates asymmetric risk-reward where losses are larger than intended.

**Evidence from `little_rzy_bot/config.py`:**
- `atr_stop_padding` defaults vary by config
- `min_rr` filters low R:R setups but the actual R:R depends on geometry, not volatility-adjusted stops

**Fix:** Add a volatility-adjusted stop that tightens in low-volatility regimes and widens in high-volatility regimes, rather than using a fixed ATR multiplier.

---

## PART 3: ARCHITECTURE & CODE QUALITY

### 3.1 God Function: runtime.py::run_route()

**File:** `signal_platform/runtime.py` lines 460-812 (460+ lines)
**Problem:** This single function handles journal enrichment, reinforcement, signal filtering, Discord dispatch (outcomes + fresh signals + recovered signals), weekly/monthly reports, journal saving, health snapshots, and ML training. It is impossible to test in isolation.

**Refactoring plan:**
1. Extract `_enrich_signals()` - journal enrichment and reinforcement
2. Extract `_dispatch_outcomes()` - outcome posting
3. Extract `_dispatch_fresh_signals()` - new signal posting
4. Extract `_dispatch_recovered_signals()` - catch-up posting
5. Extract `_generate_periodic_reports()` - weekly/monthly reports
6. Extract `_save_state_and_health()` - state persistence
7. Extract `_train_ml_models()` - ML training trigger

### 3.2 Missing Type Imports

**File:** `signal_platform/runtime.py` line 209
**Problem:** Uses `strategy: Any` but `Any` is never imported from `typing`. This will cause a `NameError` at runtime when `_send_discord_signal_with_ml` is called.

### 3.3 O(n^2) Pivot Scanning

**File:** `little_rzy_bot/signal_engine.py`
**Problem:** `_compute_trend_states` has O(n * total_pivots) complexity. The inner list comprehension `[p for p in ph if p[0] <= i - right_bars]` re-scans all pivots for every bar.

**Fix:** Use a pointer/iterator that advances through the sorted pivot list, reducing to O(n + pivots).

### 3.4 Module Structure Recommendation

Current structure is good but could be cleaner:

```
Current:                         Recommended:
signal_platform/                 signal_platform/
  __main__.py                      __main__.py
  runtime.py                       runtime.py (orchestrator only)
  journal.py                       risk/
  models.py                          guard.py (circuit breaker)
  strategies.py                      sizing.py (position sizing)
  cwt_strategy.py                    exposure.py (correlation, limits)
  little_rzy_strategy.py           strategy/
  secular_bull_sip_strategy.py       base.py (abstract strategy)
  trend_current_strategy.py          cwt.py
  signal_scoring.py                  measured_drift.py
  ml_features.py                     secular_bull_sip.py
  ml_inference.py                    trend_current.py
  ml_models.py                     ml/
  reinforcement.py                   features.py
  metrics.py                         inference.py
  dispatchers.py                     models.py
  discord_command_bot.py           execution/
  command_content.py                 dispatchers.py
  prediction_tracking.py             journal.py
  env.py                             sizing.py
  registry.py                      ops/
  runtime.py                         logging.py
                                     health.py
                                   config/
                                     env.py
                                     registry.py
```

---

## PART 4: ML PIPELINE ISSUES

### 4.1 Overfitting Risk

**Problem:** The ML pipeline trains on as few as 20 closed trades. With 8+ features and 20 samples, overfitting is virtually guaranteed.

**Evidence from `signal_platform/ml_features.py`:**
- Features include: quality_score, quality_grade, level_distance, fwm_score, confirmation_strength, trend_alignment, structure_confluence, pips_to_entry, risk_pips, reward_pips, time_of_day, day_of_week, prev_win_ratio, prev_avg_r, prev_trades_count, asset_class, scenario
- That is 15+ features on 20 samples

**Fix:**
1. Increase minimum training samples to 100
2. Use feature selection or PCA to reduce dimensionality
3. Add regularization parameter tuning via cross-validation
4. Use walk-forward validation instead of simple train/test split

### 4.2 Stale Model Cache

**File:** `signal_platform/signal_scoring.py`
**Problem:** `lru_cache` on `_load_model_predictor()` means once a model is loaded from disk, it is never refreshed even if the model file is retrained and updated on disk.

**Fix:** Either invalidate the cache after training, or check model file modification time before using cached predictor.

### 4.3 No Model Performance Monitoring

**Problem:** There is no tracking of whether ML predictions are actually improving trade selection. If the model degrades over time, the system has no way to detect it.

**Fix:** Add a `model_performance_log` that tracks prediction accuracy over rolling windows and triggers retraining alerts when accuracy drops below a threshold.

---

## PART 5: TESTING GAPS

### 5.1 Current State

14 test files covering approximately:
- CWT FWM hybrid (3 tests)
- CWT improved rules backtest (2 tests)
- CWT SL forensics (2 tests)
- Little RZY hardening (3 tests)
- Command content (5 tests)
- Dispatchers (4 tests)
- Ladder (3 tests)
- Metrics (2 tests)
- ML (13 tests)
- Recovery (9 tests)
- Signal platform models (6 tests)

### 5.2 Critical Untested Paths

| Path | Risk |
|------|------|
| Stop-loss / take-profit calculation | Trades execute at wrong levels |
| Position sizing | Over/under exposure |
| Signal filtering / duplicate suppression | Duplicate or missed signals |
| Route scheduling and polling | Bot goes silent |
| Journal outcome detection | P&L tracking incorrect |
| Circuit breaker / drawdown guard | Trades continue after loss limit |
| Market data edge cases (weekends, gaps, halts) | Signals on bad data |
| Multi-route correlation | Correlated losses |
| Recovery after downtime | Missed signals not recovered |

### 5.3 Recommended Test Strategy

```
tests/
  unit/
    test_position_sizing.py
    test_risk_guard.py
    test_stop_loss_calculation.py
    test_signal_filtering.py
    test_journal_outcome_detection.py
  integration/
    test_route_cycle.py
    test_recovery_flow.py
    test_ml_pipeline.py
  backtest/
    test_walk_forward.py
    test_overfitting_detection.py
```

---

## PART 6: PRODUCTION DEPLOYMENT ISSUES

### 6.1 Desktop-First Deployment

**Problem:** The system runs as Windows batch files and PowerShell scripts on a desktop. No VPS deployment, no Docker, no process supervision.

**Impact:** If the desktop sleeps, the bot stops. No automatic restart on crash. No health monitoring.

**Fix:** Add Docker support and systemd service for Linux deployment. Already partially started in `deploy/systemd.signal-platform.service.example`.

### 6.2 No API Rate Limiting

**Problem:** OANDA API calls are made without rate limiting. If the polling interval is too short or multiple routes hit the API simultaneously, rate limits could be triggered.

**Fix:** Add a shared rate limiter for all OANDA API calls.

### 6.3 No Data Validation

**Problem:** Market data from OANDA is used without validation for missing bars, stale prices, or weekend gaps. A signal generated on stale data could have an invalid entry price.

---

## PART 7: PRIORITIZED ACTION PLAN

### Immediate (This Week)

1. ✅ Add `logging` module throughout the codebase
2. ✅ Fix silent error swallowing (add `logging.exception()` to all bare excepts)
3. ~~Fix the `Any` import bug in `runtime.py`~~ — Not a runtime bug; `from __future__ import annotations` makes annotations strings
4. ✅ Add daily risk guard / circuit breaker to `run_route()`
5. ✅ Add position sizing to signal dispatch

### Short-Term (This Month)

6. ✅ Add trailing stop and time-based exit logic
7. ✅ Increase ML minimum training samples to 100
8. ✅ Add model cache invalidation
9. Refactor `run_route()` into smaller functions
10. Add comprehensive unit tests for risk logic
11. Add API rate limiting for OANDA calls
12. Add market data validation

### Medium-Term (Next Quarter)

13. Restructure module layout (risk/, strategy/, execution/)
14. Add walk-forward validation for ML pipeline
15. Add model performance monitoring
16. Add Docker and VPS deployment support
17. Add correlation monitoring across strategies
18. Implement Sharpe/Sortino ratio tracking

---

## PART 8: PENDING TASKS FROM REVIEW EXECUTION

The following tasks were identified as the next highest-impact improvements after implementing the immediate fixes:

### Code Quality & Maintainability

1. **Refactor `run_route()`** — Split the 460+ line function into focused helpers (scan, dispatch, report, execute, health). This makes the logic testable and reduces the chance of introducing bugs when changing dispatch behavior.

### Testing & Validation

2. **Add unit tests for risk logic** — Test `position_sizing.py`, `_check_daily_circuit_breaker()`, `OandaClient.run_preflight()`, and `_format_price()` with edge cases.
3. **Add market data validation** — Verify bars are not stale, not missing, and not from weekend gaps before generating signals. This prevents trades on invalid data.

### API Reliability

4. **Add API rate limiting** — Implement a shared rate limiter for all OANDA API calls to prevent 429 errors when multiple routes run simultaneously.

### Third-Party Library Integrations

5. **Integrate pyfolio** for professional risk metrics — Add Sharpe ratio, Sortino ratio, Calmar ratio, and max drawdown to health snapshots and weekly reports.
6. **Integrate financial-machine-learning** for robust ML — Use its feature selection, cross-validation, and regularization patterns to replace the current 15-feature / 20-sample setup.

### Architecture & Deployment

7. **Restructure module layout** — Move risk logic, strategy implementations, and execution code into separate subpackages (`risk/`, `strategy/`, `execution/`, `ops/`).
8. **Add Docker and VPS deployment** — Replace desktop batch files with containerized deployment, systemd service, and health monitoring.
9. **Add walk-forward validation** — Validate ML model performance on rolling windows before deploying retrained models.
10. **Add correlation monitoring** — Prevent taking multiple correlated trades at the same time.
11. **Implement Sharpe/Sortino tracking** — Track risk-adjusted returns across routes.

---

*This review was produced by analyzing 60+ source files across signal_platform, little_rzy_bot, config, tests, and research directories. All findings are based on actual code inspection.*

---

## PART 9: EXTERNAL RESEARCH CROSS-CHECK & STRATEGIC UPGRADES

This section cross-checks recent quant-learning research against the current project state and derives concrete planned improvements.

### 9.1 Starting-Point Assessment

The project already goes well beyond a beginner algo-trading setup:

- A working **Python backtester** in `parabolic-exhaustion-bot/` with vectorized research and an event-driven replay engine.
- Custom **risk ladders** (e.g., CWT 0.15 / 0.30 / 0.60 sizing tiers) in the signal platform and research notebooks.
- Live-position experience in **gold, WTI, NAS100, and indices** via OANDA and IBKR integrations.
- A strict **1% per-asset risk rule** implemented in configuration and position sizing logic.

The gap is not basic coding ability; it is the bridge to **production-grade quant models** and the standard open-source tooling found in top quant repos (e.g., `awesome-quant`).

### 9.2 Quant Roadmap Alignment

The research roadmap recommends: Python/time-series refresh → core quant concepts → hands-on with top repos → paper validation. The project sits at the transition between stages 2 and 3.

| Roadmap Stage | Project Status | Next Action |
|---------------|----------------|-------------|
| Python + Pandas/NumPy/TA-Lib refresh | Strong — code is already vectorized and event-driven | Add `TA-Lib` only where it replaces hand-rolled indicators and improves standardization |
| Backtesting, risk metrics, ML for alpha | Partial — custom backtester exists, but risk metrics are ad-hoc and ML overfits | Adopt `pyfolio`/`empyrical` for risk metrics and `financial-machine-learning` patterns for feature selection |
| Hands-on with top repos (`awesome-quant`) | Not started — no imports of `zipline`, `Backtrader`, `QuantLib`, `pyfolio`, or `financial-machine-learning` | Port NAS100 parabolic bot to `zipline` or `Backtrader`; use `QuantLib` for any derivatives work |
| Paper trading + community | Partial — IBKR TWS/OANDA paper flows exist but are not standardized around tearsheets | Produce `pyfolio` tearsheets from paper-trade journals |

### 9.3 Recommended Quant Reading After Hull

The research consensus is that after **John C. Hull — Options, Futures, and Other Derivatives**, the best next step is:

1. **Primary:** *Paul Wilmott Introduces Quantitative Finance* (2nd Edition)
   - Direct Hull → quant-math bridge: PDEs, stochastic calculus, risk-neutral pricing.
   - More intuitive and trader-focused than pure-theory texts; pairs well with `QuantLib`.
2. **Alternative / Parallel:** *The Concepts and Practice of Mathematical Finance* (Mark S. Joshi)
   - Strong on stochastic processes and practical implementation; useful for backtesting and ML alpha work.
3. **Foundations:** *Stochastic Calculus for Finance I* (Steven Shreve)
   - Discrete-to-continuous models and binomial trees to Black-Scholes; rigorous base for high-R:R strategy design.
4. **Math Bridge:** *A Primer for the Mathematics of Financial Engineering* (Dan Stefanica)
   - Calculus/probability refresh with finance applications; quick bridge to coding models in Python.

Avoid jumping straight to advanced texts like Duffie or purely trader-focused books like Natenberg at this stage.

### 9.4 Bill Williams Alligator — Research Reality Check

No academic paper proves the Alligator indicator works. Empirical backtests show it can be profitable, but only under specific conditions.

**Key backtest findings (source: Liberated Stock Trader):**

| Market | Timeframe | 10-Year Net Performance | Win Rate | Reward:Risk |
|--------|-----------|-------------------------|----------|-------------|
| Nasdaq 100 (QQQ) | Weekly | **855.8%** (beat index by 125%) | 72% | 2.25 |
| Nasdaq 100 (QQQ) | Daily | 200.2% | 52% | 2.65 |
| Tesla (TSLA) | 4-hour | 2,762.2% | 50% | 4.46 |
| EUR/USD Forex | Weekly | 99.7% | 37% | 3.66 |

**What works vs. what does not:**

| Factor | Works | Does Not Work |
|--------|-------|---------------|
| Asset type | Stocks and index ETFs | Forex except on weekly timeframes |
| Timeframe | Weekly / daily | Intraday (1–5 min) |
| Market condition | Trending markets (~15–30% of time) | Ranging / sideways markets (~70–85% of time) |

**Implication for this project:** The Alligator’s premise — markets trend only 15–30% of the time — aligns with the existing swing/trend approach. However, adding Alligator-style filters to intraday kill-zone strategies without explicit regime detection would likely degrade performance. Any Alligator integration should be regime-conditioned and backtested separately on weekly/daily vs. intraday timeframes.

### 9.5 Planned Improvements Derived from Research

The following items are added to the existing action plan and cross-referenced against Part 8 where applicable:

1. **Integrate `pyfolio` / `empyrical` for professional risk metrics** (extends Part 8 item 5)
   - Add Sharpe, Sortino, Calmar, max drawdown, and rolling returns to health snapshots and weekly reports.
   - Generate tearsheets from paper-trade journals before going live.

2. **Port NAS100 parabolic bot to `zipline` or `Backtrader`** (new quant-repo milestone)
   - Use the existing event-driven replay engine as a benchmark.
   - Validate realistic slippage, commission modeling, and benchmark comparison.

3. **Adopt `financial-machine-learning` patterns for ML pipeline** (extends Part 8 item 6)
   - Replace the 15-feature / 20-sample setup with feature selection, cross-validation, and regularization patterns from the repo.
   - Apply walk-forward validation and Purged K-Fold where applicable.

4. **Add `TA-Lib` standardization where it reduces hand-rolled indicator risk** (new)
   - Replace custom smoothing / Alligator / fractal implementations only if verified against existing behavior.
   - Keep regime-aware wrappers so indicator behavior remains conditional.

5. **Add `QuantLib` bridge for any derivatives work** (new)
   - Reserve for future options/futures overlays; document pricing-model assumptions before use.

6. **Implement explicit regime filter before adding Alligator-style trend filters** (new)
   - Use ADX, moving-average slope, or volatility regime to enable/disable Alligator logic.
   - Test separately on weekly/daily vs. intraday timeframes.

7. **Fork and explore `awesome-quant`** (new)
   - Audit listed backtesters, risk libraries, and ML packages for fit with the project’s OANDA/IBKR workflow.
   - File evaluation notes in `docs/research/awesome_quant_evaluation.md`.

### 9.6 Updated Action-Plan Tie-In

Items 9.5.1 through 9.5.7 should be treated as medium-term (next quarter) or research-spike tasks. They do not replace the critical risk and hardening priorities in Part 7; they build on them once the platform has logging, circuit breakers, position sizing, and market-data validation in place.

| Priority Bucket | New Research-Driven Items | Pre-requisite |
|-----------------|---------------------------|---------------|
| Medium-term | `pyfolio`/`empyrical` risk metrics | Position sizing, journal P&L accuracy |
| Medium-term | `zipline` / `Backtrader` port of NAS100 bot | Existing event-driven replay engine stable |
| Medium-term | `financial-machine-learning` patterns | Minimum 100 closed trades, walk-forward infra |
| Research spike | `TA-Lib` / Alligator regime filter | Market-data validation and regime-labeling |
| Research spike | `QuantLib` bridge | Derivatives strategy scope defined |
| Research spike | `awesome-quant` audit | Dedicated docs/research time |


