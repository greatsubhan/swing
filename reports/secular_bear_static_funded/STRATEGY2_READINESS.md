# Trend Current Readiness

## Summary

Trend Current is now strong enough to be treated as a real strategy #2 candidate, but only in its current narrowed form:

- version: `Alligator + 4h + trailing exit`
- account model: static-funded
- total basket risk cap: `1%`
- one asset at a time

This is not yet a "trade everything" system. It is a selective trend-pullback engine.

## Benchmark Context

This report is based on:

- results file: [static_funded_results.json](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bear_static_funded/static_funded_results.json)
- date range: `2020-01-01` to `2026-04-01`

## Best Current 4h Results

| Symbol | Category | Net PnL | Return % | Trades | Win Rate | Avg R | PF | Realized RR | Max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `USD_CHF` | forex | `+$55,051.83` | `55.05%` | `89` | `58.43%` | `0.509` | `3.22` | `2.218` | `-$9,780.62` |
| `ETH_USD` | crypto | `+$42,511.20` | `42.51%` | `64` | `51.56%` | `0.603` | `2.91` | `2.856` | `-$7,711.31` |
| `AUD_CHF` | forex | `+$31,975.31` | `31.98%` | `61` | `62.30%` | `0.471` | `3.22` | `2.028` | `-$7,155.33` |
| `LTC_USD` | crypto | `+$28,062.63` | `28.06%` | `80` | `52.50%` | `0.310` | `2.36` | `2.030` | `-$6,324.57` |
| `EUR_GBP` | forex | `+$26,529.89` | `26.53%` | `85` | `60.00%` | `0.298` | `2.71` | `1.729` | `-$5,507.68` |
| `EUR_USD` | forex | `+$24,975.66` | `24.98%` | `79` | `55.70%` | `0.304` | `2.45` | `1.900` | `-$7,445.92` |
| `XAG_USD` | metal | `+$23,627.40` | `23.63%` | `45` | `66.67%` | `0.511` | `4.13` | `2.041` | `-$7,456.24` |
| `USD_CAD` | forex | `+$21,173.18` | `21.17%` | `64` | `50.00%` | `0.306` | `2.35` | `2.365` | `-$8,596.67` |
| `GBP_USD` | forex | `+$20,085.90` | `20.09%` | `73` | `54.79%` | `0.251` | `2.27` | `1.613` | `-$10,244.70` |

## Keep / Watch / Skip

### Keep

These are the strongest strategy #2 candidates right now:

- `USD_CHF`
- `ETH_USD`
- `AUD_CHF`
- `LTC_USD`
- `EUR_GBP`
- `EUR_USD`
- `XAG_USD`
- `USD_CAD`
- `GBP_USD`

Why:

- strong dollar outcomes
- healthy profit factors
- attractive realized reward-to-risk
- acceptable behavior under the static-funded framing

### Watch

These are positive enough to keep in research, but weaker than the main shortlist:

- `BCO_USD`
- `AUD_USD`
- `BTC_USD`
- `NZD_USD`
- `WTICO_USD`
- `EUR_JPY`
- `USD_JPY`
- `NAS100_USD`
- `XAU_USD`

Why:

- positive, but less efficient
- lower PF than the main group
- good enough for a watchlist, not yet good enough for a tight production basket

### Skip

These should not be part of strategy #2 right now:

- `BCH_USD`
- `US30_USD`
- `UK100_GBP`
- `SPX500_USD`
- `ESPIX_EUR`
- `FR40_EUR`
- `GBP_JPY`
- `JP225_USD`

Why:

- weak or negative PnL
- weaker PF
- less attractive capital efficiency

## 4h vs 1d

The strategy is clearly stronger on `4h` than on `1d`.

`1d` still has some good names:

- `ETH_USD`
- `USD_CHF`
- `EUR_USD`
- `AUD_CHF`
- `BTC_USD`

But `1d` should be treated as a confirmation / secondary benchmark, not the lead production timeframe.

## What This Means For Strategy #2

Recommendation:

- yes, this is worth continuing as strategy #2
- yes, it has enough edge to justify formalization
- no, it should not yet be turned into a broad multi-asset live bot

The right next move is:

1. Lock the rules in the formal strategy spec.
2. Narrow to the keep list.
3. Run a one-asset rotation simulation on only the keep list.
4. If that holds up, integrate only the shortlisted assets into the signal platform.

## Practical Recommendation

If we had to prototype strategy #2 now, I would start with this production candidate basket:

- `USD_CHF`
- `ETH_USD`
- `AUD_CHF`
- `LTC_USD`
- `EUR_GBP`
- `EUR_USD`
- `XAG_USD`
- `USD_CAD`

And I would keep these on the bench:

- `GBP_USD`
- `BCO_USD`
- `WTICO_USD`
- `BTC_USD`
- `XAU_USD`
