# Flow Strategy Notes

Strategy B is a new intraday VWAP pullback continuation model run on NAS100_USD and US30_USD.

## NAS100_USD

- `flow_wider_targets_off`: trades/day `0.113`, profit factor `2.18`, avg R `0.13`, max drawdown `-5.83 R`, robustness `4.53`.
- `flow_session_push_on`: trades/day `0.798`, profit factor `1.07`, avg R `-0.00`, max drawdown `-25.10 R`, robustness `4.86`.
- `flow_faster_off`: trades/day `0.382`, profit factor `1.01`, avg R `0.01`, max drawdown `-15.08 R`, robustness `4.31`.

## US30_USD

- `flow_faster_off`: trades/day `0.378`, profit factor `1.06`, avg R `0.02`, max drawdown `-12.07 R`, robustness `4.30`.
- `flow_faster_on`: trades/day `0.225`, profit factor `1.39`, avg R `0.04`, max drawdown `-10.17 R`, robustness `3.92`.
- `flow_wider_targets_off`: trades/day `0.103`, profit factor `0.72`, avg R `-0.01`, max drawdown `-4.65 R`, robustness `2.22`.

## Frequency Goal

- `NAS100_USD` / `flow_session_push_off` meets the frequency goal at `1.45` trades/day.
- `US30_USD` / `flow_session_push_off` meets the frequency goal at `1.53` trades/day.

## Edge And Robustness

- `NAS100_USD` / `flow_wider_targets_off` clears the quality bar with profit factor `2.18` and robustness `4.53`.

## Forward-Test Readiness

- Candidate live setups found: `1`.
- Setups that clear both quality and frequency: `0`.
- Strategy B is promising enough for forward testing only if at least one setup clears both the quality bar and the practical frequency target after this batch.
- If no row clears both, it should stay in research rather than being promoted into the live bot.
