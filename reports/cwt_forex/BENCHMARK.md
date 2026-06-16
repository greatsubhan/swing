# CWT Benchmark

## Locked Research Baseline

The current kept benchmark version of CWT is:

- `H1` bias
- `M5` execution
- `Scenario 1 + Scenario 2`
- fixed `1:1` exit
- Cambist approximated with MT5-style ZigZag:
  - `Depth = 12`
  - `Deviation = 5`
  - `Backstep = 3`
- funded-style ladder:
  - `0.07 / 0.20 / 0.45 / 1.00`
- guardrails:
  - per-asset daily cap `-$1,000`
  - portfolio daily cap `-$5,000`
  - overall brake below `$95,000`

## Benchmark Result

From [funded_ladder_sim_alt_0.07_0.20_0.45_1.00.json](/C:/Users/Seeker/Documents/swing-pr1/reports/cwt_forex/funded_ladder_sim_alt_0.07_0.20_0.45_1.00.json):

- ending balance: `$178,563.73`
- net pnl: `+$78,563.73`
- return: `+78.56%`
- trades taken: `3323`
- win rate: `53.48%`
- profit factor: `1.25`
- max drawdown: `-$10,275.86`

## Why This Version Was Kept

- the earlier ladder was too heavy for the `-$1,000` per-asset daily cap
- this lighter ladder reduced skipped trades sharply
- all four focus symbols contributed positively
- the result held up under the funded-style constraints better than the earlier ladder

## Important Caveat

This is still a research benchmark, not a final live-bot strategy.

Remaining caution points:

- Cambist is still an MT5-style approximation, not the exact original indicator code
- the comparison with Trend Current and Measured Drift is informative, but not perfectly apples-to-apples
- the current benchmark is a combined portfolio test, while the other strategy benchmark files are mostly per-asset funded-style runs
