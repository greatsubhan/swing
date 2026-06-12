# Frequency Edge Notes

Quality bar used in this review:
- `profit_factor >= 1.5`
- `avg_R_per_trade > 0`
- `gross_R > 0`
- `abs(max_drawdown_R) <= gross_R`
- at least `4` total trades
- positive year ratio >= `0.25`

Frequency assumptions:
- `approx_trades_per_day = trades_per_year / 252`
- `meets_frequency_goal` is true only for approximately `1.0` to `2.0` trades/day

- Setups that currently meet the `1–2 trades/day` goal:
  - `NAS100_USD` / `flow_session_push_off` at about `1.45` trades/day.
  - `US30_USD` / `flow_session_push_off` at about `1.53` trades/day.

- As frequency rises in the current dataset, quality does not improve enough to justify a daily-trade target. The higher-frequency rows remain far below `1 trade/day`, and loosening filters mostly adds low-quality or zero-edge trades rather than scalable flow.

## NAS100

- `flow_wider_targets_off`: about `0.113` trades/day, profit factor `2.18`, average `0.13 R`, robustness `4.53`.

## Other Indices

- No non-NAS100 index setup clears the current quality bar. `SPX500_USD` is inactive, and `UK100_GBP`/`US30_USD` remain too sparse or too weak.

## Metals

- Metals do not currently clear the quality bar. With current logic they should be treated as non-viable for live alerts.

## Conclusion

- NAS100 should remain the only serious candidate at this stage.
- Even NAS100 behaves like a low-frequency edge rather than a `1–2 trades/day` system.
- The current strategy should be treated as a selective, low-frequency setup. If daily trade flow is a hard requirement, it likely needs a second setup rather than forcing this one to trade more often.

Highest-frequency rows in the current review:
- `US30_USD` / `flow_session_push_off`: `1.533` trades/day, profit factor `0.83`, avg R `-0.06`.
- `US30_USD` / `flow_session_push_on`: `0.933` trades/day, profit factor `0.90`, avg R `-0.06`.
- `NAS100_USD` / `flow_session_push_on`: `0.798` trades/day, profit factor `1.07`, avg R `-0.00`.
- `US30_USD` / `flow_faster_off`: `0.378` trades/day, profit factor `1.06`, avg R `0.02`.
- `US30_USD` / `flow_faster_on`: `0.225` trades/day, profit factor `1.39`, avg R `0.04`.
