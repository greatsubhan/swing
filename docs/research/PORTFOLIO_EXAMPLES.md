# Portfolio Examples

This file documents simple what-if portfolio scenarios using the current improved ATR profile layer.

## Important Assumption

The requested risk was described as:

- `0.05%`
- `$500` on a `$100,000` account

Those are not the same number.

- `0.05%` of `$100,000` = `$50`
- `0.5%` of `$100,000` = `$500`

The calculations below use a fixed `$500` risk per trade because that matches the dollar amount requested.

## Portfolio Basket Used

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`
- `XAU_USD`
- `UK100_GBP`
- `NAS100_USD`

Timeframe:

- `4h`

Version:

- current profile layer with symbol-specific ATR settings

## Calendar Year 2025

Period used:

- `2025-01-01 00:00:00 UTC`
- to `2026-01-01 00:00:00 UTC`

Starting equity:

- `$100,000`

Fixed risk per trade:

- `$500`

Result:

- ending equity = `$118,961.55`
- total PnL = `$18,961.55`
- trades = `125`
- win rate = `39.2%`
- average trade = `0.303R`
- max drawdown = `-$4,501.35`

Per-asset contribution:

- `WTICO_USD`: `$4,486.35`
- `BCO_USD`: `$2,991.05`
- `XAG_USD`: `$9,053.80`
- `XAU_USD`: `-$1,900.00`
- `UK100_GBP`: `$4,330.35`
- `NAS100_USD`: `$0.00`

Notes:

- `NAS100_USD` did not trigger a trade in this exact calendar-year slice
- `XAG_USD` was the largest contributor in this period
- `XAU_USD` was the main drag in this period

## Rolling Last 12 Months

Period used:

- `2025-04-01 00:00:00 UTC`
- to `2026-04-01 00:00:00 UTC`

Starting equity:

- `$100,000`

Fixed risk per trade:

- `$500`

Result:

- ending equity = `$122,393.70`
- total PnL = `$22,393.70`
- trades = `118`
- win rate = `42.37%`
- average trade = `0.380R`
- max drawdown = `-$4,260.55`

Per-asset contribution:

- `WTICO_USD`: `$6,042.15`
- `BCO_USD`: `$4,302.90`
- `XAG_USD`: `$9,661.60`
- `XAU_USD`: `-$1,943.30`
- `UK100_GBP`: `$4,330.35`
- `NAS100_USD`: `$0.00`

## Interpretation

The portfolio result is strong enough to justify moving this version into a live signal phase, with two cautions:

- the result depends on sticking to the selected 4h asset basket
- gold is currently a weaker member of the basket than silver and energy

If the next phase needs a stricter production list, the first assets to prioritize are:

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`
- `UK100_GBP`
