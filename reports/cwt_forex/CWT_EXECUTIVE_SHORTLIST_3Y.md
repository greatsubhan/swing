# CWT Executive Shortlist (3Y)

Date range: `2023-01-01` to `2026-04-01`

Locked benchmark:

- `H1` bias
- minimum timeframe by asset class
- `Scenario 1 + Scenario 2`
- fixed `1:1`
- ZigZag/Cambist approximation `12 / 5 / 3`
- ladder `0.07 / 0.20 / 0.45 / 1.00`
- per-asset daily cap `$1,000`
- portfolio daily cap `$5,000`
- overall brake `$95,000`

## Core

These are the strongest current CWT production candidates.

| Symbol | Batch | TF | Ending Balance $ | Net PnL $ | Return % | Win Rate | PF | Max DD $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `NAS100_USD` | indices | `5m` | `176,362.69` | `76,362.69` | `76.36%` | `56.11%` | `1.41` | `6,588.69` |
| `USD_JPY` | major_fx | `5m` | `164,045.80` | `64,045.80` | `64.05%` | `54.52%` | `1.31` | `9,325.55` |
| `SPX500_USD` | indices | `5m` | `156,030.92` | `56,030.92` | `56.03%` | `54.65%` | `1.29` | `6,830.30` |
| `NZD_USD` | major_fx | `5m` | `155,461.63` | `55,461.63` | `55.46%` | `52.82%` | `1.27` | `7,827.21` |
| `AUD_USD` | major_fx | `5m` | `149,125.13` | `49,125.13` | `49.13%` | `52.61%` | `1.24` | `6,170.00` |
| `UK100_GBP` | indices | `5m` | `148,399.56` | `48,399.56` | `48.40%` | `54.64%` | `1.29` | `6,865.32` |
| `EUR_USD` | major_fx | `5m` | `145,926.93` | `45,926.93` | `45.93%` | `52.66%` | `1.22` | `7,529.38` |
| `GBP_JPY` | minor_cross_fx | `15m` | `132,682.76` | `32,682.76` | `32.68%` | `52.03%` | `1.33` | `4,869.53` |

## Watch

These are positive enough to monitor, but weaker or less clean than the core set.

| Symbol | Batch | TF | Ending Balance $ | Net PnL $ | Return % | Win Rate | PF | Max DD $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `JP225_USD` | indices | `5m` | `159,140.47` | `59,140.47` | `59.14%` | `54.53%` | `1.33` | `13,412.60` |
| `FR40_EUR` | indices | `5m` | `129,935.20` | `29,935.20` | `29.94%` | `52.06%` | `1.22` | `7,452.97` |
| `GBP_USD` | major_fx | `5m` | `136,003.44` | `36,003.44` | `36.00%` | `51.11%` | `1.17` | `7,600.58` |
| `US30_USD` | indices | `5m` | `127,549.24` | `27,549.24` | `27.55%` | `53.10%` | `1.13` | `14,496.17` |
| `USD_CHF` | major_fx | `5m` | `125,167.03` | `25,167.03` | `25.17%` | `51.35%` | `1.11` | `15,417.27` |
| `GBP_NZD` | minor_cross_fx | `15m` | `122,521.24` | `22,521.24` | `22.52%` | `52.43%` | `1.22` | `13,436.85` |
| `NZD_JPY` | minor_cross_fx | `15m` | `121,796.81` | `21,796.81` | `21.80%` | `52.86%` | `1.21` | `10,633.23` |
| `GBP_AUD` | minor_cross_fx | `15m` | `116,650.78` | `16,650.78` | `16.65%` | `49.02%` | `1.15` | `8,796.93` |
| `GBP_CAD` | minor_cross_fx | `15m` | `114,144.79` | `14,144.79` | `14.14%` | `51.29%` | `1.13` | `13,435.50` |
| `XAG_USD` | commodities | `15m` | `113,032.48` | `13,032.48` | `13.03%` | `50.36%` | `1.12` | `12,716.66` |
| `AUD_JPY` | minor_cross_fx | `15m` | `110,789.68` | `10,789.68` | `10.79%` | `53.01%` | `1.10` | `12,556.80` |
| `BCO_USD` | commodities | `15m` | `109,065.71` | `9,065.71` | `9.07%` | `49.78%` | `1.09` | `15,200.20` |

## Exclude

These should stay out of the first production CWT bot.

- `USD_CAD`
- `XAU_USD`
- `WTICO_USD`
- `EUR_GBP`
- `EUR_CHF`
- `EUR_JPY`
- `EUR_AUD`
- `EUR_CAD`
- `NZD_CAD`
- `AUD_CHF`
- `AUD_CAD`
- `AUD_NZD`
- `NZD_CHF`
- `GBP_CHF`
- `CAD_CHF`

## Recommended First Bot Basket

Start narrow:

- `NAS100_USD`
- `SPX500_USD`
- `UK100_GBP`
- `USD_JPY`
- `NZD_USD`
- `AUD_USD`
- `EUR_USD`
- `GBP_JPY`

Optional second wave after live validation:

- `FR40_EUR`
- `GBP_USD`
- `US30_USD`
- `USD_CHF`
- `GBP_NZD`
- `NZD_JPY`
- `XAG_USD`
- `BCO_USD`
