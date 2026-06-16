# Research Learnings

This file captures the main strategy lessons from the full backtesting and refinement process.

## What Changed

### 1. Structure detection was tightened

Why:

- the original implementation was too loose
- it could accept weak pullbacks and stale setups
- it was not matching the written Little RZY description closely enough

What changed:

- pullback freshness rules were tightened
- trendline handling was made stricter
- invalid conditions around broken structures were improved

Impact:

- fewer low-quality setups
- more believable backtests
- stronger alignment with the actual strategy description

### 2. The backtester was made more realistic

Why:

- optimistic fills can create fake edge
- dropping unresolved trades makes results look better than reality

What changed:

- fills were moved to a more realistic next-bar style flow
- unresolved trades were handled explicitly
- stop and target behavior became more deterministic

Impact:

- lower but more trustworthy results
- better real-world comparability

### 3. The stop model was changed to hybrid

Why:

- the written strategy uses both structure invalidation and a more practical stop concept
- the first version was too rigid

What changed:

- emergency stop stays beyond the swing extreme
- trendline invalidation is treated separately
- close-beyond-trendline logic is recognized as a structure failure event

Impact:

- improved behavior in some markets, especially `EUR_USD`
- better alignment with the stated discretionary rules

### 4. Universal filters did not hold up

Tested:

- global higher-timeframe confirmation
- global rejection-candle requirement
- global early-maturity cap

Result:

- not kept as defaults

Why:

- they improved some cases but hurt too many others
- the strategy clearly behaves differently by market family

### 5. Market-specific profiles worked

This was the first strong overall improvement after the backtest cleanup.

Why:

- energy, metals, and indices behave differently
- one shared config was forcing the same behavior onto markets with different pullback and stop dynamics

Result:

- family-level average performance improved
- strong markets improved without breaking weaker ones further

### 6. ATR tightening worked selectively

This was the latest confirmed improvement.

Important conclusion:

- tighter ATR stops are not a global win
- they do help in some symbols, especially indices
- they should be applied symbol by symbol, not as one rule for everything

Kept final ATR padding:

- `WTICO_USD`: `0.15`
- `BCO_USD`: `0.15`
- `XAG_USD`: `0.15`
- `XAU_USD`: `0.25`
- `UK100_GBP`: `0.05`
- `NAS100_USD`: `0.05`

Compared against the older family profile layer on the strongest 4h basket:

- mean `avg_r` improved from `0.536` to `0.646`
- mean win rate improved slightly from `36.27%` to `36.33%`

The biggest gains were:

- `UK100_GBP`: `0.862R -> 1.025R`
- `NAS100_USD`: `1.720R -> 2.184R`
- `XAG_USD`: `0.145R -> 0.178R`

## What Timeframes Worked

Best focus:

- `4h`

Mixed and secondary:

- `30m` for selective research only
- `1h` for selective research only

Weak or too sparse:

- `5m`
- `1d`
- `1w`

Main lesson:

- the strategy is not a great lower-timeframe universal scanner
- it behaves more like a cleaner swing continuation model on `4h`

## What Assets Worked Best

Current best list:

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`
- `UK100_GBP`
- `NAS100_USD`
- `XAU_USD`

Best balanced candidates:

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`

High-upside but lower-sample candidates:

- `UK100_GBP`
- `NAS100_USD`

Weaker families:

- most forex pairs
- most crypto pairs tested on `4h`

## Current View Of The Strategy

The strategy is good enough to move into a live signal phase if it is treated as:

- signal-only
- `4h`
- market-specific
- profile-driven

It is not yet ready to be trusted as:

- a universal multi-market strategy
- a fully automated broker execution bot

## Remaining Risks

- sample size is still low for some of the strongest-looking index cases
- the strategy still has discretionary roots that may not be fully encoded
- signal quality still depends on the chosen market basket
- gold remains positive overall, but materially weaker than silver and energy

## Recommended Next Step

Use the current profile layer and run the `primary-4h` watchlist as a live signal bot before moving to broker automation.
