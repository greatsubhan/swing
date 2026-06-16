# CWT Asset Batch Report

Date range: `2023-01-01` to `2026-04-01`

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
| USD_JPY | 5m | 164045.80 | 64045.80 | 64.05 | 27.98 | 54.52% | 1.31 | 0.091 | 1.016 | 9325.55 | 10 | 8 | 2289 | 638 | keep |
| NZD_USD | 5m | 155461.63 | 55461.63 | 55.46 | 25.81 | 52.82% | 1.27 | 0.059 | 1.016 | 7827.21 | 10 | 9 | 2149 | 619 | keep |
| AUD_USD | 5m | 149125.13 | 49125.13 | 49.13 | 23.07 | 52.61% | 1.24 | 0.052 | 1.009 | 6170.00 | 10 | 7 | 2129 | 638 | keep |
| EUR_USD | 5m | 145926.93 | 45926.93 | 45.93 | 21.03 | 52.66% | 1.22 | 0.062 | 1.028 | 7529.38 | 9 | 8 | 2184 | 672 | keep |
| GBP_USD | 5m | 136003.44 | 36003.44 | 36.00 | 17.38 | 51.11% | 1.17 | 0.023 | 1.005 | 7600.58 | 7 | 8 | 2072 | 722 | watch |
| USD_CHF | 5m | 125167.03 | 25167.03 | 25.17 | 11.73 | 51.35% | 1.11 | 0.027 | 1.006 | 15417.27 | 13 | 12 | 2146 | 746 | watch |
| USD_CAD | 5m | 94705.30 | -5294.70 | -5.29 | -103.82 | 47.06% | 0.47 | -0.102 | 0.905 | 7720.00 | 5 | 10 | 51 | 2718 | skip |

Batch takeaways:
- Symbols tested: 7
- Positive-return symbols: 6
- PF above 1.0: 6
- Keep candidates: 4
- Mean ending balance: $138633.61
- Mean net PnL: $38633.61
- Mean return: 38.64%
- Mean win rate: 51.73%
- Mean profit factor: 1.11
- Mean max drawdown: $8798.57

## Minor & Cross FX

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| GBP_JPY | 15m | 132682.76 | 32682.76 | 32.68 | 31.55 | 52.03% | 1.33 | 0.046 | 1.019 | 4869.53 | 8 | 6 | 1036 | 80 | keep |
| GBP_NZD | 15m | 122521.24 | 22521.24 | 22.52 | 21.91 | 52.43% | 1.22 | 0.069 | 1.054 | 13436.85 | 8 | 11 | 1028 | 69 | keep |
| NZD_JPY | 15m | 121796.81 | 21796.81 | 21.80 | 20.43 | 52.86% | 1.21 | 0.060 | 1.018 | 10633.23 | 11 | 7 | 1067 | 64 | keep |
| GBP_AUD | 15m | 116650.78 | 16650.78 | 16.65 | 16.36 | 49.02% | 1.15 | 0.003 | 1.046 | 8796.93 | 11 | 7 | 1018 | 86 | watch |
| GBP_CAD | 15m | 114144.79 | 14144.79 | 14.14 | 14.00 | 51.29% | 1.13 | 0.025 | 1.004 | 13435.50 | 7 | 10 | 1010 | 88 | watch |
| AUD_JPY | 15m | 110789.68 | 10789.68 | 10.79 | 10.33 | 53.01% | 1.1 | 0.070 | 1.036 | 12556.80 | 10 | 9 | 1045 | 87 | watch |
| EUR_NZD | 15m | 104321.88 | 4321.88 | 4.32 | 4.25 | 51.92% | 1.04 | 0.041 | 1.013 | 12527.61 | 10 | 9 | 1017 | 103 | watch |
| CAD_CHF | 15m | 103813.28 | 3813.28 | 3.81 | 3.88 | 49.54% | 1.03 | -0.006 | 1.006 | 10097.84 | 10 | 8 | 983 | 102 | watch |
| CAD_JPY | 15m | 103280.64 | 3280.64 | 3.28 | 3.21 | 49.85% | 1.03 | 0.014 | 1.037 | 9989.31 | 11 | 10 | 1023 | 105 | watch |
| EUR_AUD | 15m | 94990.91 | -5009.09 | -5.01 | -18.62 | 47.96% | 0.87 | -0.040 | 0.994 | 7113.24 | 6 | 8 | 269 | 821 | skip |
| NZD_CHF | 15m | 94758.70 | -5241.30 | -5.24 | -27.59 | 51.05% | 0.8 | 0.003 | 0.966 | 6820.93 | 11 | 8 | 190 | 872 | skip |
| AUD_NZD | 15m | 94709.38 | -5290.62 | -5.29 | -6.75 | 46.68% | 0.95 | -0.070 | 0.981 | 15840.69 | 7 | 9 | 784 | 361 | skip |
| AUD_CAD | 15m | 94676.21 | -5323.79 | -5.32 | -12.83 | 46.51% | 0.91 | -0.046 | 1.039 | 11615.90 | 11 | 8 | 415 | 688 | skip |
| EUR_GBP | 15m | 94472.24 | -5527.76 | -5.53 | -7.51 | 47.96% | 0.94 | -0.034 | 1.006 | 10673.57 | 8 | 8 | 736 | 263 | skip |
| GBP_CHF | 15m | 94469.56 | -5530.44 | -5.53 | -27.38 | 46.53% | 0.82 | -0.063 | 0.997 | 11252.43 | 5 | 9 | 202 | 837 | skip |
| CHF_JPY | 15m | 94326.92 | -5673.08 | -5.67 | -109.10 | 34.62% | 0.54 | -0.246 | 1.085 | 5873.08 | 3 | 6 | 52 | 1048 | skip |
| AUD_CHF | 15m | 94322.52 | -5677.48 | -5.68 | -120.80 | 44.68% | 0.45 | -0.065 | 1.076 | 7051.69 | 6 | 7 | 47 | 1087 | skip |
| EUR_JPY | 15m | 94162.85 | -5837.15 | -5.84 | -162.14 | 41.67% | 0.37 | -0.100 | 1.119 | 7406.38 | 4 | 9 | 36 | 1039 | skip |
| EUR_CAD | 15m | 94141.03 | -5858.97 | -5.86 | -29.59 | 50.51% | 0.79 | 0.004 | 0.989 | 8973.27 | 9 | 9 | 198 | 903 | skip |
| NZD_CAD | 15m | 94020.00 | -5980.00 | -5.98 | -299.00 | 30.00% | 0.22 | -0.400 | 1.0 | 6160.00 | 5 | 7 | 20 | 1027 | skip |
| EUR_CHF | 15m | 94010.29 | -5989.71 | -5.99 | -157.62 | 34.21% | 0.43 | -0.308 | 0.995 | 6995.15 | 3 | 7 | 38 | 999 | skip |

Batch takeaways:
- Symbols tested: 21
- Positive-return symbols: 9
- PF above 1.0: 9
- Keep candidates: 3
- Mean ending balance: $103002.97
- Mean net PnL: $3002.97
- Mean return: 3.00%
- Mean win rate: 46.87%
- Mean profit factor: 0.87
- Mean max drawdown: $9624.76

## Indices

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| NAS100_USD | 5m | 176362.69 | 76362.69 | 76.36 | 34.06 | 56.11% | 1.41 | 0.119 | 1.013 | 6588.69 | 10 | 8 | 2242 | 609 | keep |
| JP225_USD | 5m | 159140.47 | 59140.47 | 59.14 | 29.10 | 54.53% | 1.33 | 0.094 | 1.026 | 13412.60 | 9 | 9 | 2032 | 547 | keep |
| SPX500_USD | 5m | 156030.92 | 56030.92 | 56.03 | 26.44 | 54.65% | 1.29 | 0.090 | 1.012 | 6830.30 | 13 | 8 | 2119 | 663 | keep |
| UK100_GBP | 5m | 148399.56 | 48399.56 | 48.40 | 27.21 | 54.64% | 1.29 | 0.093 | 1.016 | 6865.32 | 11 | 9 | 1779 | 446 | keep |
| FR40_EUR | 5m | 129935.20 | 29935.20 | 29.94 | 22.42 | 52.06% | 1.22 | 0.048 | 1.021 | 7452.97 | 8 | 8 | 1335 | 199 | keep |
| US30_USD | 5m | 127549.24 | 27549.24 | 27.55 | 13.45 | 53.10% | 1.13 | 0.070 | 1.029 | 14496.17 | 12 | 10 | 2049 | 746 | watch |

Batch takeaways:
- Symbols tested: 6
- Positive-return symbols: 6
- PF above 1.0: 6
- Keep candidates: 5
- Mean ending balance: $149569.68
- Mean net PnL: $49569.68
- Mean return: 49.57%
- Mean win rate: 54.18%
- Mean profit factor: 1.28
- Mean max drawdown: $9274.34

## Commodities

| Symbol | TF | Ending Balance $ | Net PnL $ | Return % | Avg Trade $ | Win Rate | PF | Avg R | RR | Max DD $ | Max Win Streak | Max Loss Streak | Trades | Skipped | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| XAG_USD | 15m | 113032.48 | 13032.48 | 13.03 | 13.45 | 50.36% | 1.12 | 0.013 | 1.015 | 12716.66 | 10 | 7 | 969 | 100 | watch |
| BCO_USD | 15m | 109065.71 | 9065.71 | 9.07 | 9.96 | 49.78% | 1.09 | 0.012 | 1.035 | 15200.20 | 8 | 12 | 910 | 83 | watch |
| WTICO_USD | 15m | 103120.23 | 3120.23 | 3.12 | 3.33 | 50.16% | 1.03 | 0.020 | 1.038 | 16419.85 | 7 | 10 | 937 | 87 | watch |
| XAU_USD | 15m | 94136.38 | -5863.62 | -5.86 | -183.24 | 28.12% | 0.37 | -0.436 | 0.946 | 7047.63 | 2 | 9 | 32 | 1012 | skip |

Batch takeaways:
- Symbols tested: 4
- Positive-return symbols: 3
- PF above 1.0: 3
- Keep candidates: 0
- Mean ending balance: $104838.70
- Mean net PnL: $4838.70
- Mean return: 4.84%
- Mean win rate: 44.60%
- Mean profit factor: 0.90
- Mean max drawdown: $12846.08

Unavailable / failed symbols:
- NATGAS: Failed fetching NATGAS M15
- COPPER: Failed fetching COPPER M15
- PLATINUM: Failed fetching PLATINUM M15
- PALLADIUM: Failed fetching PALLADIUM M15

## Shortlist

Keep:
- NAS100_USD (indices, 5m): ending balance $176362.69, net PnL $76362.69, 76.36% return, PF 1.41, win rate 56.11%, max DD $6588.69
- USD_JPY (major_fx, 5m): ending balance $164045.80, net PnL $64045.80, 64.05% return, PF 1.31, win rate 54.52%, max DD $9325.55
- JP225_USD (indices, 5m): ending balance $159140.47, net PnL $59140.47, 59.14% return, PF 1.33, win rate 54.53%, max DD $13412.60
- SPX500_USD (indices, 5m): ending balance $156030.92, net PnL $56030.92, 56.03% return, PF 1.29, win rate 54.65%, max DD $6830.30
- NZD_USD (major_fx, 5m): ending balance $155461.63, net PnL $55461.63, 55.46% return, PF 1.27, win rate 52.82%, max DD $7827.21
- AUD_USD (major_fx, 5m): ending balance $149125.13, net PnL $49125.13, 49.13% return, PF 1.24, win rate 52.61%, max DD $6170.00
- UK100_GBP (indices, 5m): ending balance $148399.56, net PnL $48399.56, 48.40% return, PF 1.29, win rate 54.64%, max DD $6865.32
- EUR_USD (major_fx, 5m): ending balance $145926.93, net PnL $45926.93, 45.93% return, PF 1.22, win rate 52.66%, max DD $7529.38
- GBP_JPY (minor_cross_fx, 15m): ending balance $132682.76, net PnL $32682.76, 32.68% return, PF 1.33, win rate 52.03%, max DD $4869.53
- FR40_EUR (indices, 5m): ending balance $129935.20, net PnL $29935.20, 29.94% return, PF 1.22, win rate 52.06%, max DD $7452.97
- GBP_NZD (minor_cross_fx, 15m): ending balance $122521.24, net PnL $22521.24, 22.52% return, PF 1.22, win rate 52.43%, max DD $13436.85
- NZD_JPY (minor_cross_fx, 15m): ending balance $121796.81, net PnL $21796.81, 21.80% return, PF 1.21, win rate 52.86%, max DD $10633.23

Watch:
- GBP_USD (major_fx, 5m): ending balance $136003.44, net PnL $36003.44, 36.00% return, PF 1.17, win rate 51.11%
- US30_USD (indices, 5m): ending balance $127549.24, net PnL $27549.24, 27.55% return, PF 1.13, win rate 53.10%
- USD_CHF (major_fx, 5m): ending balance $125167.03, net PnL $25167.03, 25.17% return, PF 1.11, win rate 51.35%
- GBP_AUD (minor_cross_fx, 15m): ending balance $116650.78, net PnL $16650.78, 16.65% return, PF 1.15, win rate 49.02%
- GBP_CAD (minor_cross_fx, 15m): ending balance $114144.79, net PnL $14144.79, 14.14% return, PF 1.13, win rate 51.29%
- XAG_USD (commodities, 15m): ending balance $113032.48, net PnL $13032.48, 13.03% return, PF 1.12, win rate 50.36%
- AUD_JPY (minor_cross_fx, 15m): ending balance $110789.68, net PnL $10789.68, 10.79% return, PF 1.1, win rate 53.01%
- BCO_USD (commodities, 15m): ending balance $109065.71, net PnL $9065.71, 9.07% return, PF 1.09, win rate 49.78%
- EUR_NZD (minor_cross_fx, 15m): ending balance $104321.88, net PnL $4321.88, 4.32% return, PF 1.04, win rate 51.92%
- CAD_CHF (minor_cross_fx, 15m): ending balance $103813.28, net PnL $3813.28, 3.81% return, PF 1.03, win rate 49.54%
- CAD_JPY (minor_cross_fx, 15m): ending balance $103280.64, net PnL $3280.64, 3.28% return, PF 1.03, win rate 49.85%
- WTICO_USD (commodities, 15m): ending balance $103120.23, net PnL $3120.23, 3.12% return, PF 1.03, win rate 50.16%

Skip:
- EUR_AUD (minor_cross_fx, 15m): ending balance $94990.91, net PnL $-5009.09, -5.01% return, PF 0.87, win rate 47.96%
- NZD_CHF (minor_cross_fx, 15m): ending balance $94758.70, net PnL $-5241.30, -5.24% return, PF 0.8, win rate 51.05%
- USD_CAD (major_fx, 5m): ending balance $94705.30, net PnL $-5294.70, -5.29% return, PF 0.47, win rate 47.06%
- AUD_NZD (minor_cross_fx, 15m): ending balance $94709.38, net PnL $-5290.62, -5.29% return, PF 0.95, win rate 46.68%
- AUD_CAD (minor_cross_fx, 15m): ending balance $94676.21, net PnL $-5323.79, -5.32% return, PF 0.91, win rate 46.51%
- EUR_GBP (minor_cross_fx, 15m): ending balance $94472.24, net PnL $-5527.76, -5.53% return, PF 0.94, win rate 47.96%
- GBP_CHF (minor_cross_fx, 15m): ending balance $94469.56, net PnL $-5530.44, -5.53% return, PF 0.82, win rate 46.53%
- CHF_JPY (minor_cross_fx, 15m): ending balance $94326.92, net PnL $-5673.08, -5.67% return, PF 0.54, win rate 34.62%
- AUD_CHF (minor_cross_fx, 15m): ending balance $94322.52, net PnL $-5677.48, -5.68% return, PF 0.45, win rate 44.68%
- EUR_JPY (minor_cross_fx, 15m): ending balance $94162.85, net PnL $-5837.15, -5.84% return, PF 0.37, win rate 41.67%
- EUR_CAD (minor_cross_fx, 15m): ending balance $94141.03, net PnL $-5858.97, -5.86% return, PF 0.79, win rate 50.51%
- XAU_USD (commodities, 15m): ending balance $94136.38, net PnL $-5863.62, -5.86% return, PF 0.37, win rate 28.12%
- NZD_CAD (minor_cross_fx, 15m): ending balance $94020.00, net PnL $-5980.00, -5.98% return, PF 0.22, win rate 30.00%
- EUR_CHF (minor_cross_fx, 15m): ending balance $94010.29, net PnL $-5989.71, -5.99% return, PF 0.43, win rate 34.21%
