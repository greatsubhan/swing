# CWT First Pass

## Scope

This is the first backtest pass for `CWT / Cambist With Trend`.

It uses:

- higher-timeframe bias: `H1`
- execution timeframe: `M5` and `M15`
- markets: `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `USD_CAD`, `NZD_USD`, `USD_CHF`
- date range: `2025-01-01` to `2026-04-01`

## What Was Tested

The backtest only includes the lecture-confirmed core:

- `Williams Alligator`
- `Heiken Ashi`
- an MT5-style ZigZag approximation of `Cambist` using:
  - `Depth = 12`
  - `Deviation = 5`
  - `Backstep = 3`
- Scenario 1
- Scenario 2

Two exit models were tested:

1. fixed `1R`
2. `Jaw` trailing stop

## Important Assumptions

This is still a first-pass research model, not a final locked production strategy.

The biggest assumptions are:

- `H1` bias is approximated with higher-timeframe Alligator state
- `Cambist` is approximated as projected swing-high / swing-low structure
- entries are executed on the next bar open
- Scenario 3 is excluded

## Best Initial Findings

### Best stable-looking results

- `USD_JPY 5m rr1`: `1124` trades, `55.87%` win rate, `avg_r 0.124`, `PF 1.31`
- `USD_JPY 5m jaw_trail`: `1444` trades, `24.65%`, `avg_r 0.125`, `PF 1.54`
- `NZD_USD 5m jaw_trail`: `1385` trades, `26.71%`, `avg_r 0.097`, `PF 1.42`
- `EUR_USD 5m jaw_trail`: `1410` trades, `23.33%`, `avg_r 0.071`, `PF 1.29`
- `USD_CAD 5m rr1`: `1064` trades, `52.44%`, `avg_r 0.068`, `PF 1.16`
- `NZD_USD 5m rr1`: `1065` trades, `53.43%`, `avg_r 0.069`, `PF 1.16`

### Outliers to treat carefully

Two `5m jaw_trail` runs printed unusually large `R` results:

- `USD_CAD 5m jaw_trail`
- `USD_CHF 5m jaw_trail`

Those are saved in the summary file, but should be treated as provisional until we validate whether the extremely tight structural stop distances produced unrealistic reward multiples for the approximate Cambist model.

## Read So Far

The strongest early pattern is:

- `M5` is stronger than `M15`
- `Jaw` trailing produces lower win rate but often better expectancy on the better names
- `1R` exit produces more intuitive win rates and still works on several pairs

At this stage, the best candidates are:

- `USD_JPY 5m rr1`
- `USD_JPY 5m jaw_trail`
- `EUR_USD 5m jaw_trail`
- `NZD_USD 5m rr1`
- `NZD_USD 5m jaw_trail`
- `USD_CAD 5m rr1`

`M15` currently looks weaker than `M5` in this first pass.

## What Is Next

Before treating CWT as a live-bot candidate, the next high-value steps are:

1. test the PDF risk ladder versus the lecture-note risk ladder
2. add a stricter bias model if `Strategy-1` rules become available
3. test whether Scenario 3 improves or degrades the edge
4. compare this first-pass CWT result against Trend Current and Measured Drift on a normalized account model
