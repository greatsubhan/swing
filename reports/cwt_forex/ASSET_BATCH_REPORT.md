# CWT Asset Batch Report

Locked configuration:
- H1 bias
- Minimum execution timeframe by asset class
- Scenario 1 + Scenario 2
- Fixed 1:1 exit
- ZigZag/Cambist approximation: 12 / 5 / 3
- Ladder: 0.07 / 0.20 / 0.45 / 1.00
- Per-asset daily cap: $1,000
- Portfolio daily cap: $5,000
- Overall brake: $95,000

Important interpretation:
- Each symbol below is run as its own funded-style simulation from a fresh $100,000 starting balance.
- This makes the keep/skip decision clean per asset for future bot selection.
- Commodity-FX overlaps are not listed separately to avoid double-counting the same symbol.

## Major FX

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| AUD_USD | 5m | 127174.76 | 27174.76 | 27.17 | 32.12 | 53.55% | 1.37 | 0.075 | 1.023 | 4810.00 | 10 | 6 | 846 | 230 | keep |
| USD_JPY | 5m | 126184.78 | 26184.78 | 26.18 | 30.03 | 56.08% | 1.35 | 0.124 | 1.026 | 5164.08 | 10 | 8 | 872 | 252 | keep |
| NZD_USD | 5m | 124405.38 | 24405.38 | 24.41 | 29.48 | 54.11% | 1.33 | 0.082 | 1.016 | 5720.00 | 10 | 8 | 828 | 237 | keep |
| EUR_USD | 5m | 115721.86 | 15721.86 | 15.72 | 18.83 | 52.46% | 1.19 | 0.058 | 1.03 | 7529.38 | 9 | 7 | 835 | 256 | watch |
| USD_CAD | 5m | 112251.72 | 12251.72 | 12.25 | 15.55 | 51.02% | 1.14 | 0.033 | 1.031 | 7334.06 | 8 | 9 | 788 | 276 | watch |
| GBP_USD | 5m | 110186.78 | 10186.78 | 10.19 | 12.67 | 51.74% | 1.12 | 0.045 | 1.028 | 7600.58 | 7 | 8 | 804 | 292 | watch |
| USD_CHF | 5m | 109143.14 | 9143.14 | 9.14 | 11.36 | 51.30% | 1.1 | 0.041 | 1.037 | 15417.27 | 6 | 12 | 805 | 301 | watch |

Batch takeaways:
- Symbols tested: 7
- Positive-return symbols: 7
- PF above 1.0: 7
- Keep candidates: 3
- Mean ending balance: $117866.92
- Mean net PnL: $17866.92
- Mean return: 17.87%
- Mean win rate: 52.89%
- Mean profit factor: 1.23
- Mean max drawdown: $7653.62

## Minor & Cross FX

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CHF_JPY | 15m | 113664.34 | 13664.34 | 13.66 | 35.22 | 51.80% | 1.37 | 0.044 | 1.024 | 3758.69 | 8 | 5 | 388 | 32 | keep |
| GBP_JPY | 15m | 113208.76 | 13208.76 | 13.21 | 33.19 | 49.25% | 1.32 | 0.001 | 1.033 | 4869.53 | 8 | 6 | 398 | 30 | watch |
| GBP_NZD | 15m | 110811.85 | 10811.85 | 10.81 | 27.30 | 54.04% | 1.3 | 0.072 | 0.997 | 3720.00 | 8 | 6 | 396 | 28 | keep |
| NZD_JPY | 15m | 109561.08 | 9561.08 | 9.56 | 23.15 | 53.51% | 1.24 | 0.078 | 1.03 | 3720.00 | 11 | 7 | 413 | 20 | keep |
| EUR_AUD | 15m | 107225.13 | 7225.13 | 7.23 | 18.67 | 52.71% | 1.19 | 0.075 | 1.056 | 10519.76 | 15 | 9 | 387 | 32 | watch |
| GBP_AUD | 15m | 106747.08 | 6747.08 | 6.75 | 17.26 | 52.17% | 1.18 | 0.063 | 1.053 | 4720.00 | 11 | 7 | 391 | 22 | watch |
| EUR_JPY | 15m | 106344.50 | 6344.50 | 6.34 | 16.92 | 54.40% | 1.17 | 0.072 | 0.98 | 4364.03 | 9 | 5 | 375 | 25 | watch |
| EUR_CAD | 15m | 105946.62 | 5946.62 | 5.95 | 15.77 | 50.66% | 1.15 | 0.028 | 1.036 | 5740.43 | 10 | 7 | 377 | 35 | watch |
| EUR_NZD | 15m | 104546.66 | 4546.66 | 4.55 | 11.63 | 51.92% | 1.1 | 0.051 | 1.034 | 5954.58 | 8 | 8 | 391 | 38 | watch |
| CAD_JPY | 15m | 103292.18 | 3292.18 | 3.29 | 8.17 | 50.62% | 1.07 | 0.020 | 1.018 | 7667.37 | 11 | 10 | 403 | 37 | watch |
| NZD_CAD | 15m | 94913.86 | -5086.14 | -5.09 | -23.77 | 49.53% | 0.81 | -0.025 | 0.962 | 8469.05 | 6 | 7 | 214 | 175 | skip |
| AUD_JPY | 15m | 94897.73 | -5102.27 | -5.10 | -21.90 | 49.79% | 0.83 | 0.012 | 1.035 | 11517.09 | 7 | 7 | 233 | 195 | skip |
| AUD_NZD | 15m | 94835.88 | -5164.12 | -5.16 | -122.96 | 33.33% | 0.45 | -0.328 | 0.945 | 5414.12 | 3 | 6 | 42 | 381 | skip |
| NZD_CHF | 15m | 94773.48 | -5226.52 | -5.23 | -14.28 | 47.27% | 0.9 | -0.047 | 1.003 | 8710.50 | 10 | 7 | 366 | 43 | skip |
| AUD_CAD | 15m | 94680.61 | -5319.39 | -5.32 | -332.46 | 37.50% | 0.09 | -0.178 | 1.131 | 5799.39 | 4 | 9 | 16 | 429 | skip |
| EUR_CHF | 15m | 94656.92 | -5343.08 | -5.34 | -61.41 | 41.38% | 0.63 | -0.141 | 1.025 | 7484.44 | 6 | 7 | 87 | 297 | skip |
| GBP_CHF | 15m | 94546.07 | -5453.93 | -5.45 | -89.41 | 45.90% | 0.49 | -0.082 | 0.983 | 6518.99 | 5 | 7 | 61 | 329 | skip |
| EUR_GBP | 15m | 94520.83 | -5479.17 | -5.48 | -21.24 | 43.02% | 0.86 | -0.118 | 1.015 | 8176.29 | 7 | 8 | 258 | 133 | skip |
| CAD_CHF | 15m | 94504.14 | -5495.86 | -5.50 | -15.35 | 45.53% | 0.89 | -0.102 | 0.957 | 7734.60 | 7 | 6 | 358 | 44 | skip |
| AUD_CHF | 15m | 94431.70 | -5568.30 | -5.57 | -31.11 | 43.58% | 0.81 | -0.086 | 1.072 | 11037.22 | 7 | 9 | 179 | 243 | skip |
| GBP_CAD | 15m | 94010.20 | -5989.80 | -5.99 | -34.82 | 45.35% | 0.78 | -0.087 | 0.998 | 12435.50 | 7 | 10 | 172 | 251 | skip |

Batch takeaways:
- Symbols tested: 21
- Positive-return symbols: 10
- PF above 1.0: 10
- Keep candidates: 3
- Mean ending balance: $101053.32
- Mean net PnL: $1053.32
- Mean return: 1.05%
- Mean win rate: 47.77%
- Mean profit factor: 0.93
- Mean max drawdown: $7063.41

## Indices

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SPX500_USD | 5m | 127245.43 | 27245.43 | 27.25 | 32.91 | 54.95% | 1.38 | 0.101 | 1.021 | 4178.33 | 13 | 6 | 828 | 241 | keep |
| NAS100_USD | 5m | 124521.57 | 24521.57 | 24.52 | 29.94 | 54.70% | 1.34 | 0.096 | 1.015 | 6588.69 | 8 | 8 | 819 | 215 | keep |
| JP225_USD | 5m | 119097.11 | 19097.11 | 19.10 | 23.90 | 55.44% | 1.27 | 0.118 | 1.042 | 13412.60 | 8 | 9 | 799 | 178 | keep |
| UK100_GBP | 5m | 117998.51 | 17998.51 | 18.00 | 26.16 | 54.65% | 1.29 | 0.075 | 0.977 | 4691.64 | 11 | 6 | 688 | 164 | keep |
| US30_USD | 5m | 110864.28 | 10864.28 | 10.86 | 14.09 | 52.40% | 1.13 | 0.069 | 1.057 | 8112.63 | 12 | 8 | 771 | 265 | watch |
| FR40_EUR | 5m | 106709.84 | 6709.84 | 6.71 | 12.95 | 50.19% | 1.12 | 0.010 | 1.014 | 7452.97 | 6 | 7 | 518 | 88 | watch |

Batch takeaways:
- Symbols tested: 6
- Positive-return symbols: 6
- PF above 1.0: 6
- Keep candidates: 4
- Mean ending balance: $117739.46
- Mean net PnL: $17739.46
- Mean return: 17.74%
- Mean win rate: 53.72%
- Mean profit factor: 1.26
- Mean max drawdown: $7406.14

## Commodities

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| XAG_USD | 15m | 115635.26 | 15635.26 | 15.64 | 39.89 | 53.32% | 1.47 | 0.083 | 1.054 | 2720.00 | 10 | 5 | 392 | 37 | keep |
| XAU_USD | 15m | 114873.36 | 14873.36 | 14.87 | 38.43 | 54.01% | 1.45 | 0.086 | 1.026 | 2720.00 | 8 | 5 | 387 | 32 | keep |
| BCO_USD | 15m | 108362.00 | 8362.00 | 8.36 | 24.10 | 51.30% | 1.27 | 0.026 | 1.006 | 6204.58 | 8 | 8 | 347 | 22 | keep |
| WTICO_USD | 15m | 94850.89 | -5149.11 | -5.15 | -91.95 | 44.64% | 0.56 | -0.061 | 1.085 | 6722.20 | 5 | 9 | 56 | 312 | skip |

Batch takeaways:
- Symbols tested: 4
- Positive-return symbols: 3
- PF above 1.0: 3
- Keep candidates: 3
- Mean ending balance: $108430.38
- Mean net PnL: $8430.38
- Mean return: 8.43%
- Mean win rate: 50.82%
- Mean profit factor: 1.19
- Mean max drawdown: $4591.69

Unavailable / failed symbols:
- NATGAS: Failed fetching NATGAS M15
- COPPER: Failed fetching COPPER M15
- PLATINUM: Failed fetching PLATINUM M15
- PALLADIUM: Failed fetching PALLADIUM M15

## Shortlist

Keep:
- SPX500_USD (indices, 5m): ending balance $127245.43, net PnL $27245.43, 27.25% return, PF 1.38, win rate 54.95%, max DD $4178.33
- AUD_USD (major_fx, 5m): ending balance $127174.76, net PnL $27174.76, 27.17% return, PF 1.37, win rate 53.55%, max DD $4810.00
- USD_JPY (major_fx, 5m): ending balance $126184.78, net PnL $26184.78, 26.18% return, PF 1.35, win rate 56.08%, max DD $5164.08
- NAS100_USD (indices, 5m): ending balance $124521.57, net PnL $24521.57, 24.52% return, PF 1.34, win rate 54.70%, max DD $6588.69
- NZD_USD (major_fx, 5m): ending balance $124405.38, net PnL $24405.38, 24.41% return, PF 1.33, win rate 54.11%, max DD $5720.00
- JP225_USD (indices, 5m): ending balance $119097.11, net PnL $19097.11, 19.10% return, PF 1.27, win rate 55.44%, max DD $13412.60
- UK100_GBP (indices, 5m): ending balance $117998.51, net PnL $17998.51, 18.00% return, PF 1.29, win rate 54.65%, max DD $4691.64
- XAG_USD (commodities, 15m): ending balance $115635.26, net PnL $15635.26, 15.64% return, PF 1.47, win rate 53.32%, max DD $2720.00
- XAU_USD (commodities, 15m): ending balance $114873.36, net PnL $14873.36, 14.87% return, PF 1.45, win rate 54.01%, max DD $2720.00
- CHF_JPY (minor_cross_fx, 15m): ending balance $113664.34, net PnL $13664.34, 13.66% return, PF 1.37, win rate 51.80%, max DD $3758.69
- GBP_NZD (minor_cross_fx, 15m): ending balance $110811.85, net PnL $10811.85, 10.81% return, PF 1.3, win rate 54.04%, max DD $3720.00
- NZD_JPY (minor_cross_fx, 15m): ending balance $109561.08, net PnL $9561.08, 9.56% return, PF 1.24, win rate 53.51%, max DD $3720.00
- BCO_USD (commodities, 15m): ending balance $108362.00, net PnL $8362.00, 8.36% return, PF 1.27, win rate 51.30%, max DD $6204.58

Watch:
- EUR_USD (major_fx, 5m): ending balance $115721.86, net PnL $15721.86, 15.72% return, PF 1.19, win rate 52.46%
- GBP_JPY (minor_cross_fx, 15m): ending balance $113208.76, net PnL $13208.76, 13.21% return, PF 1.32, win rate 49.25%
- USD_CAD (major_fx, 5m): ending balance $112251.72, net PnL $12251.72, 12.25% return, PF 1.14, win rate 51.02%
- US30_USD (indices, 5m): ending balance $110864.28, net PnL $10864.28, 10.86% return, PF 1.13, win rate 52.40%
- GBP_USD (major_fx, 5m): ending balance $110186.78, net PnL $10186.78, 10.19% return, PF 1.12, win rate 51.74%
- USD_CHF (major_fx, 5m): ending balance $109143.14, net PnL $9143.14, 9.14% return, PF 1.1, win rate 51.30%
- EUR_AUD (minor_cross_fx, 15m): ending balance $107225.13, net PnL $7225.13, 7.23% return, PF 1.19, win rate 52.71%
- GBP_AUD (minor_cross_fx, 15m): ending balance $106747.08, net PnL $6747.08, 6.75% return, PF 1.18, win rate 52.17%
- FR40_EUR (indices, 5m): ending balance $106709.84, net PnL $6709.84, 6.71% return, PF 1.12, win rate 50.19%
- EUR_JPY (minor_cross_fx, 15m): ending balance $106344.50, net PnL $6344.50, 6.34% return, PF 1.17, win rate 54.40%
- EUR_CAD (minor_cross_fx, 15m): ending balance $105946.62, net PnL $5946.62, 5.95% return, PF 1.15, win rate 50.66%
- EUR_NZD (minor_cross_fx, 15m): ending balance $104546.66, net PnL $4546.66, 4.55% return, PF 1.1, win rate 51.92%
- CAD_JPY (minor_cross_fx, 15m): ending balance $103292.18, net PnL $3292.18, 3.29% return, PF 1.07, win rate 50.62%

Skip:
- NZD_CAD (minor_cross_fx, 15m): ending balance $94913.86, net PnL $-5086.14, -5.09% return, PF 0.81, win rate 49.53%
- AUD_JPY (minor_cross_fx, 15m): ending balance $94897.73, net PnL $-5102.27, -5.10% return, PF 0.83, win rate 49.79%
- WTICO_USD (commodities, 15m): ending balance $94850.89, net PnL $-5149.11, -5.15% return, PF 0.56, win rate 44.64%
- AUD_NZD (minor_cross_fx, 15m): ending balance $94835.88, net PnL $-5164.12, -5.16% return, PF 0.45, win rate 33.33%
- NZD_CHF (minor_cross_fx, 15m): ending balance $94773.48, net PnL $-5226.52, -5.23% return, PF 0.9, win rate 47.27%
- AUD_CAD (minor_cross_fx, 15m): ending balance $94680.61, net PnL $-5319.39, -5.32% return, PF 0.09, win rate 37.50%
- EUR_CHF (minor_cross_fx, 15m): ending balance $94656.92, net PnL $-5343.08, -5.34% return, PF 0.63, win rate 41.38%
- GBP_CHF (minor_cross_fx, 15m): ending balance $94546.07, net PnL $-5453.93, -5.45% return, PF 0.49, win rate 45.90%
- EUR_GBP (minor_cross_fx, 15m): ending balance $94520.83, net PnL $-5479.17, -5.48% return, PF 0.86, win rate 43.02%
- CAD_CHF (minor_cross_fx, 15m): ending balance $94504.14, net PnL $-5495.86, -5.50% return, PF 0.89, win rate 45.53%
- AUD_CHF (minor_cross_fx, 15m): ending balance $94431.70, net PnL $-5568.30, -5.57% return, PF 0.81, win rate 43.58%
- GBP_CAD (minor_cross_fx, 15m): ending balance $94010.20, net PnL $-5989.80, -5.99% return, PF 0.78, win rate 45.35%
