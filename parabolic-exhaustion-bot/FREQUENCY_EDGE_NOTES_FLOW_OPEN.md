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

- No current setup gets close to the `1–2 trades/day` goal. The best setups are still well below daily frequency.

- As frequency rises in the current dataset, quality does not improve enough to justify a daily-trade target. The higher-frequency rows remain far below `1 trade/day`, and loosening filters mostly adds low-quality or zero-edge trades rather than scalable flow.

## NAS100

- NAS100 does not currently clear the quality bar, which would be a strong warning against live use.

## Other Indices

- No non-NAS100 index setup clears the current quality bar. `SPX500_USD` is inactive, and `UK100_GBP`/`US30_USD` remain too sparse or too weak.

## Metals

- Metals do not currently clear the quality bar. With current logic they should be treated as non-viable for live alerts.

## Conclusion

- NAS100 should remain the only serious candidate at this stage.
- Even NAS100 behaves like a low-frequency edge rather than a `1–2 trades/day` system.
- The current strategy should be treated as a selective, low-frequency setup. If daily trade flow is a hard requirement, it likely needs a second setup rather than forcing this one to trade more often.

Highest-frequency rows in the current review:
- `NAS100_USD` / `flow_open_0930_fast_off`: `0.152` trades/day, profit factor `0.69`, avg R `-0.15`.
- `NAS100_USD` / `flow_open_1000_fast_off`: `0.146` trades/day, profit factor `0.48`, avg R `-0.23`.
- `NAS100_USD` / `flow_open_0935_fast_off`: `0.136` trades/day, profit factor `0.71`, avg R `-0.16`.
- `US30_USD` / `flow_open_0930_fast_off`: `0.118` trades/day, profit factor `0.78`, avg R `-0.15`.
- `US30_USD` / `flow_open_0935_fast_off`: `0.116` trades/day, profit factor `0.82`, avg R `-0.12`.
