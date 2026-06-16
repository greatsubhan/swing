# Opening Hour Flow Strategy Notes

Strategy B is a new intraday VWAP pullback continuation model run on NAS100_USD and US30_USD.

## NAS100_USD

- `flow_open_0935_fast_on`: trades/day `0.088`, profit factor `0.81`, avg R `-0.11`, max drawdown `-10.63 R`, robustness `2.15`.
- `flow_open_1000_bal_off`: trades/day `0.016`, profit factor `0.90`, avg R `-0.14`, max drawdown `-5.06 R`, robustness `1.32`.
- `flow_open_0930_fast_off`: trades/day `0.152`, profit factor `0.69`, avg R `-0.15`, max drawdown `-19.57 R`, robustness `1.21`.

## US30_USD

- `flow_open_0935_fast_on`: trades/day `0.084`, profit factor `0.99`, avg R `-0.09`, max drawdown `-10.55 R`, robustness `3.19`.
- `flow_open_0945_fast_on`: trades/day `0.053`, profit factor `1.25`, avg R `-0.03`, max drawdown `-7.01 R`, robustness `1.89`.
- `flow_open_0945_fast_off`: trades/day `0.087`, profit factor `0.84`, avg R `-0.10`, max drawdown `-11.63 R`, robustness `1.07`.

## Frequency Goal

- No current setup lands in the target zone of roughly 1-2 trades per day.
- NAS100 came closest with `flow_open_0930_fast_off` at `0.152` trades/day.
- US30 came closest with `flow_open_0930_fast_off` at `0.118` trades/day.

## Edge And Robustness

- No current setup clears the existing quality bar across profit factor, average R, drawdown discipline, and walk-forward consistency.

## Opening Window Comparison

- Best opening window in this pass: `open_0935_1030` with average profit factor `0.51`, max robustness `3.19`, and `0` quality-bar hits.
- `open_0935_1030`: average profit factor `0.51`, average R `-0.27`, total trades `441`, quality hits `0`, frequency hits `0`.
- `open_0930_1030`: average profit factor `0.47`, average R `-0.28`, total trades `474`, quality hits `0`, frequency hits `0`.
- `open_0945_1030`: average profit factor `0.46`, average R `-0.32`, total trades `293`, quality hits `0`, frequency hits `0`.
- `open_1000_1100`: average profit factor `0.23`, average R `-0.16`, total trades `226`, quality hits `0`, frequency hits `0`.

## Skipping The Open

- Skipping the first 5-15 minutes did not improve the average edge consistently in this batch: delayed windows averaged profit factor `0.40` vs `0.47` and average R `-0.25` vs `-0.28`.

## Forward-Test Readiness

- Candidate live setups found: `0`.
- Setups that clear both quality and frequency: `0`.
- Strategy B is promising enough for forward testing only if at least one setup clears both the quality bar and the practical frequency target after this batch.
- If no row clears both, it should stay in research rather than being promoted into the live bot.
