# Strategy Selection Notes

Robustness score in `robustness_ranking.csv` is currently:
`(positive_years / years_covered) * log1p(total_trades)`.

## NAS100_USD

- `idx_looser_ext_off`: profit factor `3.78`, total trades `4`, positive years `1/4`, robustness score `0.40`.
- `idx_looser_ext_on`: profit factor `3.78`, total trades `4`, positive years `1/4`, robustness score `0.40`.
- `idx_ps07_baseline_off`: profit factor `3.78`, total trades `4`, positive years `1/4`, robustness score `0.40`.

## Other Indices

- No other index currently looks strong enough for live alerts under the current logic.

## Metals

- Metals do not look viable yet with the current rule set and family-specific search.

## Exclude For Now

- Markets that currently look weakest or too sparse for live alerts: `SPX500_USD, UK100_GBP, US30_USD, WTICO_USD, XAG_USD, XAU_USD`.
- `SPX500_USD` still produces no trades in the tested family grid.
- `US30_USD` remains too sparse to treat as reliable despite one positive configuration.
- `UK100_GBP`, `XAU_USD`, `XAG_USD`, and `WTICO_USD` do not currently show stable positive-year behavior.
