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

- No current setup gets close to the `1-2 trades/day` goal. The best setups are still well below daily frequency.

- As frequency rises in the current dataset, quality does not improve enough to justify a daily-trade target. The higher-frequency rows remain far below `1 trade/day`, and loosening filters mostly adds low-quality or zero-edge trades rather than scalable flow.

## NAS100

- `idx_looser_ext_off`: about `0.005` trades/day, profit factor `3.78`, average `0.80 R`, robustness `0.40`.
- `idx_looser_ext_on`: about `0.005` trades/day, profit factor `3.78`, average `0.80 R`, robustness `0.40`.
- `idx_ps07_baseline_off`: about `0.005` trades/day, profit factor `3.78`, average `0.80 R`, robustness `0.40`.

## Other Indices

- No non-NAS100 index setup clears the current quality bar. `SPX500_USD` is inactive, and `UK100_GBP`/`US30_USD` remain too sparse or too weak.

## Metals

- Metals do not currently clear the quality bar. With current logic they should be treated as non-viable for live alerts.

## Conclusion

- NAS100 should remain the only serious candidate at this stage.
- Even NAS100 behaves like a low-frequency edge rather than a `1-2 trades/day` system.
- The current strategy should be treated as a selective, low-frequency setup. If daily trade flow is a hard requirement, it likely needs a second setup rather than forcing this one to trade more often.

Highest-frequency rows in the current review:
- `XAU_USD` / `met_balanced_off`: `0.016` trades/day, profit factor `0.06`, avg R `-0.68`.
- `XAU_USD` / `met_smaller_target_off`: `0.016` trades/day, profit factor `0.04`, avg R `-0.70`.
- `XAU_USD` / `met_buffered_off`: `0.013` trades/day, profit factor `0.05`, avg R `-0.65`.
- `XAU_USD` / `met_balanced_on`: `0.013` trades/day, profit factor `0.07`, avg R `-0.62`.
- `XAU_USD` / `met_smaller_target_on`: `0.013` trades/day, profit factor `0.05`, avg R `-0.65`.
