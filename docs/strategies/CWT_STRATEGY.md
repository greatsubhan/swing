# CWT / Cambist With Trend (Draft Spec)

## Status

This is a draft strategy specification built from:

- [12Week2ForexCWT.pdf](/C:/Users/Seeker/Downloads/12Week2ForexCWT.pdf)
- the pasted lecture notes from the user

It is not locked yet. The goal of this file is to separate:

- lecture-confirmed rules
- likely interpretations for a first backtest
- unresolved gaps that still need clarification before the strategy is treated as final

Update after the funded-style ladder pass:

- the strategy logic is now strong enough to freeze a practical benchmark version
- some details are still implementation approximations, especially the exact Cambist code
- but the benchmark version below is now the preferred research baseline

## Current Benchmark Version

The current benchmark version for CWT is:

- higher-timeframe bias: `H1`
- execution timeframe: `M5`
- scenarios: `Scenario 1 + Scenario 2`
- exit: fixed `1:1`
- Cambist approximation:
  - MT5-style ZigZag
  - `Depth = 12`
  - `Deviation = 5`
  - `Backstep = 3`
- recovery ladder:
  - `0.07 / 0.20 / 0.45 / 1.00`
- funded-style guardrails:
  - starting balance: `$100,000`
  - per-asset daily stop cap: `-$1,000`
  - portfolio daily cap: `-$5,000`
  - overall brake below `$95,000`

Why this version is the current benchmark:

- it is more realistic under the user's actual guardrails than the earlier `0.15 / 0.30 / 0.60 / 1.20` ladder
- it allows many more valid trades before the daily asset cap blocks them
- it is the cleanest profitable version that still behaves sensibly under funded-style constraints

## Live Delivery Update: Signal Reinforcement

The live CWT board now uses a reinforcement layer on top of the raw scanner.

Why:

- CWT can produce clusters of same-direction confirmations on the same symbol
- those confirmations are useful information
- but they should not be treated as separate tradable entries while the original idea is still active

Current live behavior:

- first valid setup in a structure = **root signal**
- later same-structure setups = **reinforcement updates**
- reinforcements do not create new journal trades
- reinforcements can still be posted to Discord as non-tradable confidence updates

The scanner itself is unchanged. The reinforcement decision happens in the shared signal platform after raw CWT signals are produced.

See:

- [SIGNAL_REINFORCEMENT_SYSTEM.md](/C:/Users/Seeker/Documents/swing-pr1/docs/SIGNAL_REINFORCEMENT_SYSTEM.md)

## Overview

CWT stands for `Cambist With Trend`.

The lecture framing is:

- make a directional bias on a higher timeframe
- move to a lower timeframe for execution
- use `Williams Alligator` plus `Cambist`
- trade in the direction of the higher-timeframe bias
- use structured stop-loss placement
- use a progressive risk ladder after losses

This is a continuation strategy, not a reversal strategy.

## Lecture-Confirmed Components

### Indicators

The lecture explicitly uses:

- `Williams Alligator`
- `Heiken Ashi` candles
- `Cambist`

From the user's screenshots and notes, `Cambist` appears to be a structure layer built on top of ZigZag-style swing confirmation rather than a simple momentum oscillator.

The PDF confirms the Bill Williams Alligator construction:

- `Jaw` = blue line = 13-period smoothed moving average, shifted 8 bars
- `Teeth` = red line = 8-period smoothed moving average, shifted 5 bars
- `Lips` = green line = 5-period smoothed moving average, shifted 3 bars

### Cambist visual logic

Based on the user's screenshots and description, the practical Cambist interpretation is:

- a ZigZag-style structure mapper confirms swing highs and swing lows
- confirmed swing highs are marked with `blue dots`
- confirmed swing lows are marked with `red dots`
- those dots project horizontally forward until invalidated by a new confirmed structural state

So the dots are not just static historical markers. They act as active structural levels.

In practice:

- blue dots often behave like active resistance in bearish continuation phases
- red dots often behave like active support in bullish continuation phases

This is the most important new insight from the screenshots because it explains why the stop rules in the lecture refer to colored dots rather than arbitrary price levels.

### ZigZag parameters

The user later supplied the standard MT5 ZigZag defaults:

- `Depth = 12`
- `Deviation = 5`
- `Backstep = 3`

These are now the preferred first-pass parameters for approximating Cambist in research.

Important nuance:

- ZigZag repaints its most recent leg
- the last swing is not truly final until enough bars pass to confirm it

That behavior is consistent with the user's observation that the projected dots keep extending until structure is confirmed or replaced.

### Timeframes

From the user notes, the intended flow is:

- higher-timeframe bias: `H1`
- execution timeframe: `M5` or `M15`

The PDF itself does not restate the exact bias timeframe on the scenario slides, but the lecture notes do, and they are consistent with the strategy description.

### Market constraints

The user later supplied a machine-readable market constraint list for CWT.

That mapping is saved in:

- [cwt_market_constraints.json](/C:/Users/Seeker/Documents/swing-pr1/config/cwt_market_constraints.json)

Current interpretation:

- major FX and major indices can be tested from `5m` upward
- commodities and cross pairs should not be tested below `15m`
- higher timeframes than the minimum are allowed if the setup remains valid

### Core Rule

Only take trades in the direction of the higher-timeframe bias.

That is the central idea repeated in the lecture notes.

## Entry Logic

## Scenario 1: Alligator mouth open

The PDF confirms:

### Buyer version

- Alligator mouth must be open
- Lips, Teeth, and Jaw must be parallel
- Heiken candles must be above Lips
- Stop-loss below Jaw

### Seller version

- Alligator mouth must be open
- Lips, Teeth, and Jaw must be parallel
- Heiken candles must be below Lips
- Stop-loss above Jaw

### First strict interpretation for backtesting

For a first backtest, this can be translated as:

- `H1` bias must be bullish for longs, bearish for shorts
- on `M5` or `M15`, the Alligator ordering must align with the trade direction
- the three lines must be clearly separated and directionally aligned
- Heiken Ashi candles must close on the trend side of Lips
- entry occurs at the close of the qualifying trigger candle, or next bar open

This interpretation is close to the lecture material and is mechanically testable.

## Scenario 2: Price crosses back through Jaw

The PDF confirms:

### Buyer version

- Alligator mouth is open and pointing downwards
- Candle closes above Jawline
- Stop-loss below red dots

### Seller version

- Alligator mouth is open and pointing upwards
- Candle closes below Jawline
- Stop-loss above blue dots

### First strict interpretation for backtesting

This appears to be a continuation re-entry or transition setup:

- higher-timeframe bias still controls direction
- the lower timeframe temporarily moves against the bias
- entry occurs when price closes back across Jaw in the direction of the higher-timeframe idea
- stop is placed beyond Cambist dots

This is backtestable once Cambist dot rules are defined clearly enough in code.

## Scenario 3: Alligator mouth closed

The PDF says:

- Alligator mouth is closed (`sleeping`)
- this scenario will be discussed in upcoming lectures

The user's lecture notes add a more advanced interpretation:

- if bias is bullish and the alligator is sleeping, wait for `2` Heiken candles to close above all three lines
- stop below Cambist red dots
- bearish version is the mirror image

This means:

- the PDF alone does not fully define Scenario 3
- the user's notes likely come from a later explanation or another session

So Scenario 3 should be treated as:

- `supported by notes`
- `not fully confirmed by this PDF alone`

## Stop-Loss Rules

The lecture material gives structural SL placement:

- Scenario 1 long: below Jaw
- Scenario 1 short: above Jaw
- Scenario 2 long: below Cambist red dots
- Scenario 2 short: above Cambist blue dots

Important missing detail:

- there is no explicit padding rule in the deck
- there is no exact definition yet for how far beyond Jaw or the dots the stop should be placed

For a first backtest, a practical mechanical rule would be:

- stop just beyond the structural reference
- optionally with a small spread/ATR buffer

But that buffer would be an assumption, not lecture-confirmed.

### Cambist stop interpretation

With the screenshot context, the lecture's dot-based stop rules can be translated more clearly:

- long trades that use Cambist-based invalidation should place stop beyond the active `red-dot` support projection
- short trades that use Cambist-based invalidation should place stop beyond the active `blue-dot` resistance projection

This means the stop is tied to the currently active structure state, not merely the most recent candle extreme.

## Exit Logic

This is the biggest unresolved area.

From the user's notes:

- Scenario 1 can use `1:1` RR
- or the trend can be ridden by trailing stop below or above Jaw

From the PDF:

- no hard TP rule is stated on the scenario slides
- the risk management slide shows a progression of trade risk after losses, but not a fixed universal exit rule

So the likely valid first backtest variants are:

1. fixed `1:1`
2. trailing stop at Jaw
3. possibly partial at `1:1` and trail the rest

At the moment, `1:1` and `Jaw trail` are the cleanest candidates for testing.

## Risk Management

### Account-level guardrails

The user later clarified the clean account protection rules for CWT:

- starting capital: `$100,000`
- per-asset daily loss cap: `1%` of starting balance
- with `$100,000`, that means `-$1,000` maximum loss per asset per day
- portfolio daily loss cap across the active basket: `5%` of starting balance
- with `$100,000`, that means `-$5,000` maximum planned daily loss across all tracked assets

### Equity protection rule

The user also clarified an important override:

- the `1%` per-asset daily rule always applies
- even if account equity drops below `$100,000`
- the extra `-$5,000` overall guard acts as a hard brake once equity begins dropping under the starting balance

This means the strategy should be modeled with:

- a fixed per-asset daily stop budget
- a fixed portfolio daily stop budget
- and an additional account-protection brake once the account is under water

### What the PDF shows

The PDF's risk ladder says:

| Trade | Risk % | Cumulative if SL hits | Net target |
|---|---:|---:|---:|
| 1st | `0.15%` | `-0.15%` | `0.15%` |
| 2nd | `0.35%` | `-0.45%` | `0.15%` |
| 3rd | `0.70%` | `-1.05%` | `0.15%` |
| 4th | `1.50%` | `-2.25%` | `0.15%` |

### What the user's notes say

The user's notes say:

- 1st trade `0.15%`
- 2nd trade `0.30%`
- 3rd trade `0.60%`
- 4th trade `1.20%`

This is a direct discrepancy.

So the risk ladder is **not yet fully locked**.

For rigorous testing, we should test both versions:

- `PDF ladder`: `0.15 / 0.35 / 0.70 / 1.50`
- `notes ladder`: `0.15 / 0.30 / 0.60 / 1.20`

### How the ladder and guardrails fit together

These are not the same thing:

- the ladder is the per-trade recovery sizing model
- the account guardrails are the outer risk limits

So in a realistic funded-style simulation, the flow should be:

1. size the next trade from the ladder
2. check whether that trade would breach the `1%` per-asset daily limit
3. check whether the day would breach the `5%` total portfolio daily limit
4. if either would be breached, skip the trade

That is the correct way to combine the recovery ladder with the user's account-level constraints.

## What Still Needs Clarification

Before treating CWT as fully locked, these points still need to be pinned down:

1. the exact higher-timeframe bias rule from `Strategy-1`
2. the exact indicator definition and parameters for `Cambist`
3. whether Scenario 3 is officially part of this strategy or from a later extension
4. whether entry is at close, next open, or break of trigger candle
5. whether the default exit is `1:1`, trailing Jaw, or scenario-dependent
6. which risk ladder is the final intended one

The screenshots reduce uncertainty around item `2`, but do not fully eliminate it.

What now seems likely:

- Cambist uses ZigZag-confirmed structure
- dot colors represent the currently active structural side
- horizontal projection represents the active invalidation or continuation level

What is still unknown:

- exact ZigZag parameters
- exact confirmation delay before a dot becomes active
- whether dot color is always mapped directly to swing-high/swing-low polarity or can also encode trade-state transitions

## Recommended First Backtest Version

If we want a disciplined first pass without pretending to know too much, I would test this version first:

- higher-timeframe bias: `H1`
- execution timeframe: `M5`
- direction: only trade with `H1` bias
- Scenario 1 and Scenario 2 only
- entry: next bar open after valid trigger
- stop:
  - Scenario 1 = beyond Jaw
  - Scenario 2 = beyond the currently active projected Cambist dot
- exits:
  - variant A = fixed `1:1`
  - variant B = Jaw trailing stop
- risk ladder:
  - test both the PDF ladder and the user's note ladder

### Structural interpretation for that first pass

To keep the backtest mechanically honest, the Cambist layer should be approximated as:

- use an MT5-style ZigZag approximation with:
  - `Depth = 12`
  - `Deviation = 5`
  - `Backstep = 3`
- mark last confirmed swing high as active blue resistance
- mark last confirmed swing low as active red support
- extend the active level until a newly confirmed swing replaces it

That is not guaranteed to be byte-for-byte identical to the exact MT5 indicator code, but it is now a much closer representation of what the screenshots show than treating Cambist as a generic dot indicator.

That would be a fair first backtest without over-inventing the strategy.

## Recommended Next Account Simulation

Now that the account rules are clearer, the next funded-style CWT simulation should use:

- starting capital: `$100,000`
- risk ladder: `0.15 / 0.30 / 0.60 / 1.20`
- per-asset daily stop cap: `-$1,000`
- total portfolio daily stop cap: `-$5,000`
- the `1%` per-asset rule always enforced
- the `-$5,000` guard acting as the hard brake once equity drops below starting balance

## Bottom Line

This lecture deck is good enough to start a serious CWT backtest, but not good enough to claim we have the final official rule set without assumptions.

The strong parts are:

- the Alligator structure
- the trend-continuation framing
- the two main entry scenarios
- the structural stop placement
- the progressive risk model
- the fact that Cambist appears to be a projected structure-state tool, not just a decorative overlay

The weak parts are:

- exact bias logic
- exact Cambist implementation parameters
- exact exit default
- the mismatch between the PDF and the notes on risk sizing
