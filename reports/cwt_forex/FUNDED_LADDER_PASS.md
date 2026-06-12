# CWT Funded Ladder Pass

## Configuration

- starting balance: `$100,000`
- symbols:
  - `USD_JPY`
  - `EUR_USD`
  - `NZD_USD`
  - `USD_CAD`
- timeframe: `M5`
- bias: `H1`
- scenarios: `Scenario 1 + Scenario 2`
- exit: fixed `1:1`
- ladder: `0.15 / 0.30 / 0.60 / 1.20`
- per-asset daily cap: `-$1,000`
- total portfolio daily cap: `-$5,000`
- overall brake: stop taking new risk if equity falls below `$95,000`

## Result

- ending balance: `$102,703.77`
- net pnl: `+$2,703.77`
- return: `+2.70%`
- trades taken: `99`
- win rate: `51.52%`
- profit factor: `1.25`
- max drawdown: `-$2,400.00`

## What Happened

The strategy stayed profitable under the funded-style guardrails, but the guardrails were very restrictive.

- trades skipped by per-asset daily cap: `4245`
- trades skipped by portfolio daily cap: `0`
- trades skipped by overall brake: `0`

So the asset-level daily cap was the dominant limiter.

## Important Finding

The `1.20%` ladder step was effectively blocked by the `-$1,000` per-asset daily cap.

Risk steps actually used:

- `0.15%`
- `0.30%`
- `0.60%`

That means the practical funded-account ladder is currently behaving more like:

- `0.15 / 0.30 / 0.60`

with `1.20` present in theory but not really available in practice under this rule set.

## Per-Symbol Contribution

- `NZD_USD`: `+$2,009.24`
- `USD_CAD`: `+$1,045.63`
- `USD_JPY`: `+$698.91`
- `EUR_USD`: `-$1,050.00`

## Keep / Discard Read

Keep, but with the right interpretation:

- the strategy still has edge under the funded-style rules
- the funded-style caps compress it heavily
- the current best view is that this is a viable but constrained version of CWT

Practical takeaway:

- yes, this version survives
- no, it is not explosive under the funded-style caps
- the `1.20%` step should not be treated as meaningfully usable under the current `1%` per-asset daily rule
