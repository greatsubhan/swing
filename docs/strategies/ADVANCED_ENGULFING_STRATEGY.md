# Advanced Engulfing Trend Pullback Strategy

## Status

This is the first formalized draft of the strategy defined in chat on April 6, 2026.

It is separate from:

- `Measured Drift`
- `Trend Current`
- `Cambist With Trend`
- `Secular Bull SIP`

This draft is intentionally backtestable. Where the lecture-style wording was still discretionary, the rules below lock one specific interpretation for Phase 1 testing.

## Core Idea

Trade with the trend after a clean structure break and a controlled pullback.

The system combines:

- trend filter via `EMA(50)`
- structure via `higher high` or `lower low`
- pullback via opposite-color candles
- momentum re-entry via an `Advanced Engulfing Candle`
- fixed `1R` target

## Long Rules

### Trend Filter

1. Close must be above `EMA(50)`.
2. Optional quality filter:
   - `EMA(50)` slope positive

Phase 1 default:
- rule `1` is active
- rule `2` is recorded as optional and can be toggled later

### Structure

3. Price must have made a `Higher High`.

Phase 1 definition:
- use confirmed fractal swing highs with `2` bars left and `2` bars right
- a valid `Higher High` exists when:
  - latest confirmed swing high `>` previous confirmed swing high

### Pullback

4. After the higher high, price must pull back with at least `2` consecutive bearish candles.
5. Pullback must not break the prior confirmed swing low that existed before the higher high.

Optional pullback depth filter for later testing:
- pullback depth between `0.3` and `0.7` of the impulse

Phase 1 default:
- depth filter is off

### Entry Trigger

6. Entry candle must be a bullish `Advanced Engulfing Candle`.
7. Entry candle must occur:
   - at the pullback swing low
   - or immediately after the pullback swing low
8. Entry candle must not close above the highest body of the higher-high swing candle.

## Short Rules

Mirror version of the long setup:

1. Close below `EMA(50)`
2. Optional negative `EMA(50)` slope
3. Latest confirmed swing low `<` previous confirmed swing low
4. Pullback has at least `2` consecutive bullish candles
5. Pullback must not break the prior confirmed swing high
6. Entry candle is bearish `Advanced Engulfing`
7. Entry candle at or immediately after the pullback swing high
8. Entry candle must not close below the lowest body of the lower-low swing candle

## Advanced Engulfing Definition

### Bullish

All must be true:

1. Current candle closes above open
2. Current body engulfs previous candle body
3. Current close is above previous candle high
4. Candle range is at least:
   - `1.2 * ATR(14)`
   - or larger than the average range of the last `5` candles
5. Strong close near the high:
   - `(close - low) / (high - low) >= 0.7`

### Bearish

Mirror version:

1. Current candle closes below open
2. Current body engulfs previous candle body
3. Current close is below previous candle low
4. Range expansion requirement
5. Strong close near the low:
   - `(high - close) / (high - low) >= 0.7`

## Stop Logic

Base formula:

```text
stop_buffer = ATR(14) + extra_buffer
```

Where:

- if `ATR < 40` then `extra_buffer = 5`
- if `40 <= ATR < 50` then `extra_buffer = 10`
- if `50 <= ATR <= 200` then `extra_buffer = 20`

Phase 1 implementation:

- long stop = `pullback swing low - stop_buffer`
- short stop = `pullback swing high + stop_buffer`

## Target

Phase 1 target:

- fixed `1:1`

Future expansion lane:

- `TP1 = 1R`
- `TP2 = 2R`
- break-even after `1R`

## Swing Logic

Phase 1 definition:

- use fractal pivots
- swing high:
  - high is greater than highs of previous `2` bars and next `2` bars
- swing low:
  - low is lower than lows of previous `2` bars and next `2` bars

This is chosen because it is clean, deterministic, and easy to mirror long/short.

## Invalid Conditions

Phase 1 enforced:

- invalid stop placement
- no confirmed higher high / lower low
- pullback breaks prior swing anchor
- no valid advanced engulfing candle
- entry candle too late relative to pullback swing point

Phase 1 not yet enforced:

- sideways ATR filter
- pullback depth `0.3 to 0.7`
- session filter

## Phase 1 Backtest Defaults

Current batch universe:

- load the machine-readable universe from `config/advanced_engulfing_market_constraints.json`
- run each symbol at its listed minimum timeframe
- allow higher-timeframe variants later as a second pass

Initial seed set that was tested before the wider universe batch:

- `BTC_USD`
- `ETH_USD`
- `NAS100_USD`

Initial seed timeframes:

- `15m`
- `1h`

Date range:

- `2025-01-01` to `2026-04-01`

## Why This Draft Is Good Enough To Test

- the trend rule is precise
- the structure rule is precise
- the engulfing trigger is precise
- the stop rule is precise
- the target rule is precise

That makes it strong enough for a first-pass backtest, while still leaving room for later optional filters.
