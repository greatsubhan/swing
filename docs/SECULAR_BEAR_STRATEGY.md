# Trend Current (Strategy #2)

## Overview

This strategy is the locked version of strategy #2. During research it was referred to as the secular-bear pullback strategy.

It is:

- directional bias: trend-following continuation
- default side in research: follow the dominant trend, with the current test set favoring persistent downside / relative weakness behavior
- strength source: adding to winners during a sustained trend while keeping total open basket risk capped

The current lead implementation is a rules-based version designed for backtesting, funded-account style evaluation, and live signal delivery through the multi-strategy platform.

## Canonical Test Version

This is the version that currently performs best overall:

- live bot name: `Trend Current`
- regime filter: `Bill Williams / Alligator`
- lead timeframe: `4h`
- secondary comparison timeframe: `1d`
- data range: `2020-01-01` to `2026-04-01`
- account model:
  - starting balance: `$100,000`
  - static daily floor: `$95,000`
  - static overall floor: `$90,000`
  - one asset at a time
  - max total open basket risk on that asset: `1%`

## Market Universe

The current broad test basket includes:

- forex: `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `AUD_CHF`, `USD_CAD`, `USD_CHF`, `NZD_USD`, `EUR_GBP`, `EUR_JPY`, `GBP_JPY`
- indices: `FR40_EUR`, `JP225_USD`, `ESPIX_EUR`, `UK100_GBP`, `NAS100_USD`, `US30_USD`, `SPX500_USD`
- metals: `XAU_USD`, `XAG_USD`
- energy: `WTICO_USD`, `BCO_USD`
- crypto: `BTC_USD`, `ETH_USD`, `LTC_USD`, `BCH_USD`

## Setup Logic

### 1. Trend / regime filter

Use the Bill Williams structure to only trade in the direction of the dominant move.

The implementation checks for a valid directional state using:

- Alligator jaw / teeth / lips ordering
- price location relative to the Alligator structure
- recent directional impulse strength

This acts as the higher-level bias filter. The strategy does not take every pullback; it only acts when the broader structure already points in one direction.

### 2. Pullback requirement

Wait for price to retrace against the dominant move.

In the tested implementation, the pullback is defined mechanically using:

- retracement back toward the trend structure
- local swing formation on the execution timeframe
- ATR normalization so the pullback is not too small to matter

### 3. Entry trigger

Enter when the pullback resolves back in the direction of the dominant trend.

The implemented trigger uses:

- a fresh directional break from the pullback
- confirmation that the trend filter still holds
- next-bar execution in the backtest

### 4. Initial stop loss

The initial stop is fixed and structure-based:

- stop beyond the pullback swing extreme
- ATR padding added on top of that structure level

This keeps the stop attached to the chart structure rather than a random fixed number.

### 5. Add-to-winner logic

Adds are allowed, but only under strict conditions:

- never add to a losing basket
- only one asset can be active at a time
- combined open risk on the full basket cannot exceed `1%` of account equity
- once an active tranche reaches `+1R`, its stop is moved to breakeven
- that freed risk can be reused for a later add on the same asset

This is the key mechanism that made the strategy materially stronger without making it reckless under the user's funded-account rules.

### 6. Exit logic

The current lead version uses a trailing trend-break exit instead of a fixed take-profit.

Why:

- the strategy is strongest when trends extend
- fixed `2R` / `3R` exits left too much money on the table in stronger runs
- the trailing version produced the best blend of money made, win rate, and survivability

### 7. Live bot outcome tracking

The research exit is trailing, but the live signal bot still needs a concrete milestone for TP / SL journaling.

So the current bot tracks:

- stop loss: the same structure-plus-ATR stop used by the strategy
- TP1: a `2R` milestone

That means the live bot's report card is tracking:

- whether TP1 was reached
- whether SL was reached

while the research benchmark still uses the full trailing-exit model.

## Risk Model

### Static funded-account constraints

The currently preferred simulation uses static funded-account thresholds:

- daily breach line: `$95,000`
- overall breach line: `$90,000`
- profits above `$100,000` do not tighten those floors

That means:

- `$100k -> $110k -> $104k` is still valid
- a breach only occurs if equity actually drops below the static floor

### Why this matters

This rule set is materially different from a trailing drawdown model. The static version is much closer to the user's real funded-account constraint and is the correct benchmark for this strategy.

## What Worked

The strongest elements so far are:

- `4h` execution
- Alligator regime filter
- trailing exit
- one-asset focus
- capped basket risk at `1%`
- breakeven stop recycling after `+1R`

## What Did Not Improve The Strategy

These were tested and are not the lead version:

- `1d` as the main execution timeframe
- EMA-led versions as the default benchmark
- overly aggressive leverage assumptions
- comparing raw six-year profits without account constraints

## Current Strategic Read

This strategy is not a universal market scanner. It is strongest when:

- the asset trends cleanly
- pullbacks are well-defined
- the market keeps rewarding continuation rather than mean reversion

At the moment, it looks best on:

- selected forex pairs
- selected crypto
- silver
- some energy names

It is much less convincing on most indices.
