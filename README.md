# Little RZY Signal Bot v1 (Signal + Backtest Only)

This repository provides a **developer-ready, backtest-safe signal provider** for a formalized Little RZY continuation strategy.
It does **not** connect to brokers and does **not** execute trades.

## 1) Strategy translation summary
- Continuation-only strategy: trade with higher-timeframe trend.
- Detect impulse leg, then controlled pullback.
- Build pullback trendline from confirmed pivots.
- Compute measured-move target from anchor-to-trendline distance.
- Trigger on continuation break (prior-bar break default).
- Validate structure-based stop, minimum RR, freshness, and non-duplicate conditions.
- Use Bollinger Bands as context + scoring (not primary trigger).

## 2) Explicit rules/specification
### Trend detection
- Trend = bullish when:
  - EMA slow slope > `min_ma_slope`
  - ADX >= `min_adx`
  - Last pivot highs show HH sequence and lows show HL sequence (`min_hhhl_count`)
- Trend = bearish inverse. Otherwise sideways (no setups).

### Impulse definition
- Impulse magnitude >= `min_impulse_atr * ATR`.
- Impulse duration between `min_impulse_bars` and `max_impulse_bars`.

### Pullback definition
- Pullback retrace between `pullback_min_retrace` and `pullback_max_retrace`.
- Pullback age <= `max_setup_age_bars`.

### Little RZY structure
- **Short**:
  1. Anchor low = latest confirmed pivot low before evaluation bar.
  2. Pullback high = latest confirmed pivot high after impulse.
  3. Trendline from pullback pivot high to current pullback high.
  4. Measured distance = trendline(at anchor index) - anchor low.
  5. Target = anchor low - measured distance.
- **Long**: exact inverse.

### Trendline logic
- Line from two confirmed points `(i1, p1)` and `(i2, p2)`.
- Equation: `y = m*x + b`.
- Slope constraint:
  - Short pullback trendline must slope down (`m < 0`) and within `trendline_max_abs_slope`.
  - Long pullback trendline must slope up (`m > 0`) and within limit.

### Entry / Stop / Target
- Default entry trigger:
  - Short: break of prior bar low.
  - Long: break of prior bar high.
- Stop:
  - Structure extreme plus ATR padding (`atr_stop_padding * ATR`).
- Target:
  - Measured move projection (primary `target_1`).
- RR filter:
  - `risk_reward >= min_rr`.

### Bollinger context
- BB params: `bb_length=20`, `bb_stddev=2.0` (configurable).
- Favorable short context: pullback near upper/mid zone.
- Favorable long context: pullback near lower/mid zone.
- Extension tags: normal / moderately_stretched.

### Trend maturity
- Maturity bucket = count of previously triggered same-side setups in trend run.
- Used as a scoring penalty for late-stage setups.

### Invalid conditions
- Sideways regime.
- Insufficient impulse or pullback depth.
- Bad trendline slope.
- Poor RR.
- Stale setup.
- Duplicate setup key `(anchor_index, side)`.

### Signal lifecycle states
- `candidate_detected -> validated -> triggered -> active -> closed|expired|invalidated`.

### Edge cases / failure modes
- Flat ATR or sparse data -> no setup.
- Ambiguous intrabar stop/target touch -> deterministic policy via `stop_priority_when_both_hit`.
- Missing HTF confirmation columns -> trend defaults to stricter filters.

## 3) Assumptions used
- Confirmed pivots only (no repainting by default).
- Entry timestamp uses signal bar and fill starts next bar in backtest.
- Costs modeled as configurable fee + slippage in bps.
- No partial TP in v1 (extension-ready).
- Continuation setups prioritized; reversals only tagged as warnings.

## 4) Core detection algorithm
1. Load OHLCV.
2. Compute ATR, BB, EMA slope, ADX.
3. Compute confirmed pivot highs/lows.
4. For each bar: classify trend.
5. Build Little RZY candidate.
6. Validate trendline, measured move, stop, RR, freshness.
7. Trigger if entry condition hit.
8. Score 0-100 and emit structured signal JSON.
9. Track uniqueness and maturity counters.

## 5) Backtesting design
- Bar-by-bar simulation.
- No lookahead in pivot use (right-bar confirmation applied).
- Entry at/after signal; exits evaluated each bar.
- Deterministic stop/target ordering config.
- Expiration bounded by setup-age windows.
- Trade log + aggregate metrics + bucketed diagnostics.

## 6) Python project architecture
- `little_rzy_bot/config.py` — central config.
- `little_rzy_bot/data_models.py` — signal/setup/trade/summary schemas.
- `little_rzy_bot/indicators.py` — ATR/BB/EMA/ADX.
- `little_rzy_bot/pivots.py` — confirmed pivot detection.
- `little_rzy_bot/trend_detection.py` — trend state rules.
- `little_rzy_bot/trendline.py` — trendline math.
- `little_rzy_bot/structure_detection.py` — Little RZY candidate building.
- `little_rzy_bot/scoring.py` — weighted quality score.
- `little_rzy_bot/signal_engine.py` — full pipeline + signal emission.
- `little_rzy_bot/backtest_adapter.py` — trade simulation adapter.
- `little_rzy_bot/reporting.py` — summary and sweep table utilities.
- `little_rzy_bot/alerts.py` — concise human alert text.
- `little_rzy_bot/utils.py` — tick rounding helper.

## 7) Python implementation for core modules
Implemented in `little_rzy_bot/*` as typed, modular, reusable functions/classes.

## 8) Example config
Use `EngineConfig()` defaults in `config.py`; override per asset/timeframe.

## 9) Example signal JSON
Generated by `Signal.to_dict()` and matches the requested schema fields.

## 10) Example backtest trade log
Produced via `to_trade_log_df(simulate_signals(...))`.
Fields include symbol, side, times, entry/exit, pnl_r, maturity, score, setup_id.

## 11) Example performance summary
`reporting.summarize(trade_log_df)` returns trades, win rate, avg_r, expectancy,
max drawdown, profit factor, hold time, and grouped breakdowns.

## 12) Tuning/optimization notes
- Prefer broad ranges and walk-forward slices.
- Sweep: `min_impulse_atr`, retrace bounds, RR floor, ADX floor.
- Validate stability across symbol clusters and timeframes.
- Optimize for robustness (median OOS expectancy), not top in-sample score.

## 13) Extension roadmap
### Option 1: Python production scanner
- Add scheduler + multi-symbol data adapters.
- Persist signals/events in DB.
- Expose REST/webhook output.

### Option 2: Pine Script port
- Port deterministic rule subset.
- Replace backtest adapter with TradingView `strategy.*` simulation.
- Handle pivot confirmation explicitly with bar offsets.

### Option 3: Telegram/Discord backend
- Keep engine in Python service.
- Add message templates + dedupe cache + rate limiting.
- Push alerts from emitted signals only.

## 14) Recommendation (next build)
Start with **Option 1 (Python production scanner)** first.
It reuses 100% of core logic, enables rapid validation on many markets, and de-risks later Pine and chat-bot integrations.

## Example usage
```python
import pandas as pd
from little_rzy_bot import EngineConfig, SignalEngine
from little_rzy_bot.backtest_adapter import simulate_signals, to_trade_log_df
from little_rzy_bot.reporting import summarize

# Expected columns: open, high, low, close, volume; DatetimeIndex
ohlcv = pd.read_csv("data/sample_ohlcv.csv", parse_dates=["timestamp"]).set_index("timestamp")

cfg = EngineConfig()
engine = SignalEngine(cfg)
signals = engine.run(ohlcv, symbol="BTCUSDT", asset_class="crypto", timeframe="4h", higher_timeframe="1d")

trades = simulate_signals(ohlcv, signals, cfg)
trade_log = to_trade_log_df(trades)
summary = summarize(trade_log)
```

## Worked examples (logic walk-through)
- **Short example**: bearish trend + impulse down 2.4 ATR, pullback retrace 0.42, prior-bar-low break triggers short, stop above pullback high + ATR padding, measured move target hit after 9 bars.
- **Long example**: bullish trend + impulse up 2.1 ATR, pullback retrace 0.38, prior-bar-high break triggers long, stop below pullback low + ATR padding, target hit after 6 bars.

## Immediate next step: Backtesting now
Run the full backtesting workflow immediately with either synthetic data or your own CSV.

### Quick smoke test (synthetic)
```bash
python -m little_rzy_bot --out backtest_output
```

### Real historical CSV
```bash
python -m little_rzy_bot --csv data/your_ohlcv.csv --timestamp-col timestamp --out backtest_output
```

### Outputs
- `backtest_output/trade_log.csv`
- `backtest_output/summary.json`

### What to inspect first
1. `summary.json` -> expectancy, win rate, max drawdown proxy.
2. `trade_log.csv` -> false positives (low score + poor context).
3. Re-run sweeps for `min_impulse_atr` and `min_rr` to check robustness.
