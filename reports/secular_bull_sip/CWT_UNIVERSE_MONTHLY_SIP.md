# Secular Bull SIP Baseline Across CWT Universe

## Test Setup

- Date range: `2020-01-01` to `2026-04-01`
- Starting capital reference: `$100,000`
- Monthly contribution per asset test: `$8,333.33`
- Variant: pure monthly SIP baseline
- Long-only
- No leverage
- No stop loss
- One asset per simulation
- Universe source: CWT market batches

## Batch Summary

| Batch | Tested | Mean Ending Value $ | Mean Net PnL $ | Mean TWR Ann. | Mean XIRR | Mean Max DD % |
|---|---:|---:|---:|---:|---:|---:|
| Major FX | 7 | 638,910.58 | 13,910.58 | 0.31% | 0.56% | 4.82% |
| Commodity FX | 3 | 619,006.72 | -5,993.28 | -0.52% | -0.36% | 5.10% |
| Minor & Cross FX | 21 | 667,780.64 | 42,780.64 | 1.46% | 1.85% | 2.92% |
| Indices | 6 | 913,752.80 | 288,752.80 | 10.27% | 12.06% | 8.75% |
| Commodities | 4 | 1,321,687.58 | 696,687.58 | 15.50% | 23.34% | 21.16% |

## Detailed Results

### Major FX

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `USD_JPY` | USD/JPY | 75 | 625,000.00 | 766,609.67 | 141,609.67 | 1.23 | 6.28% | 6.62% | 39,660.95 | 7.77% | 54.67% | 13.00% | -3.18% |
| `USD_CAD` | USD/CAD | 75 | 625,000.00 | 651,695.36 | 26,695.36 | 1.04 | 1.09% | 1.36% | 15,371.11 | 2.70% | 49.33% | 8.13% | -6.26% |
| `EUR_USD` | EUR/USD | 75 | 625,000.00 | 649,963.29 | 24,963.29 | 1.04 | 0.47% | 1.27% | 10,527.31 | 2.02% | 50.67% | 14.40% | -7.45% |
| `GBP_USD` | GBP/USD | 75 | 625,000.00 | 641,151.76 | 16,151.76 | 1.03 | 0.00% | 0.83% | 14,710.08 | 2.50% | 52.00% | 10.47% | -8.37% |
| `AUD_USD` | AUD/USD | 75 | 625,000.00 | 632,945.05 | 7,945.05 | 1.01 | -0.22% | 0.41% | 26,669.41 | 5.61% | 52.00% | 14.60% | -7.53% |
| `NZD_USD` | NZD/USD | 75 | 625,000.00 | 572,379.74 | -52,620.26 | 0.92 | -2.44% | -2.86% | 32,880.39 | 7.00% | 53.33% | 11.47% | -8.46% |
| `USD_CHF` | USD/CHF | 75 | 625,000.00 | 557,629.21 | -67,370.79 | 0.89 | -2.99% | -3.71% | 31,334.04 | 6.15% | 41.33% | 5.80% | -15.18% |

Top performers:
- `USD_JPY`: ending value `$766,609.67`, net PnL `$141,609.67`, XIRR `6.62%`, max DD `7.77%`
- `USD_CAD`: ending value `$651,695.36`, net PnL `$26,695.36`, XIRR `1.36%`, max DD `2.70%`
- `EUR_USD`: ending value `$649,963.29`, net PnL `$24,963.29`, XIRR `1.27%`, max DD `2.02%`
Weakest performers:
- `USD_CHF`: ending value `$557,629.21`, net PnL `$-67,370.79`, XIRR `-3.71%`, max DD `6.15%`
- `NZD_USD`: ending value `$572,379.74`, net PnL `$-52,620.26`, XIRR `-2.86%`, max DD `7.00%`
- `AUD_USD`: ending value `$632,945.05`, net PnL `$7,945.05`, XIRR `0.41%`, max DD `5.61%`

### Commodity FX

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `USD_CAD` | USD/CAD | 75 | 625,000.00 | 651,695.36 | 26,695.36 | 1.04 | 1.09% | 1.36% | 15,371.11 | 2.70% | 49.33% | 8.13% | -6.26% |
| `AUD_USD` | AUD/USD | 75 | 625,000.00 | 632,945.05 | 7,945.05 | 1.01 | -0.22% | 0.41% | 26,669.41 | 5.61% | 52.00% | 14.60% | -7.53% |
| `NZD_USD` | NZD/USD | 75 | 625,000.00 | 572,379.74 | -52,620.26 | 0.92 | -2.44% | -2.86% | 32,880.39 | 7.00% | 53.33% | 11.47% | -8.46% |

Top performers:
- `USD_CAD`: ending value `$651,695.36`, net PnL `$26,695.36`, XIRR `1.36%`, max DD `2.70%`
- `AUD_USD`: ending value `$632,945.05`, net PnL `$7,945.05`, XIRR `0.41%`, max DD `5.61%`
- `NZD_USD`: ending value `$572,379.74`, net PnL `$-52,620.26`, XIRR `-2.86%`, max DD `7.00%`
Weakest performers:
- `NZD_USD`: ending value `$572,379.74`, net PnL `$-52,620.26`, XIRR `-2.86%`, max DD `7.00%`
- `AUD_USD`: ending value `$632,945.05`, net PnL `$7,945.05`, XIRR `0.41%`, max DD `5.61%`
- `USD_CAD`: ending value `$651,695.36`, net PnL `$26,695.36`, XIRR `1.36%`, max DD `2.70%`

### Minor & Cross FX

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CHF_JPY` | CHF/JPY | 75 | 625,000.00 | 865,970.82 | 240,970.82 | 1.39 | 9.58% | 10.57% | 20,135.10 | 3.32% | 68.00% | 20.13% | -0.86% |
| `EUR_JPY` | EUR/JPY | 75 | 625,000.00 | 793,960.31 | 168,960.31 | 1.27 | 6.79% | 7.76% | 25,140.60 | 4.43% | 60.00% | 14.11% | -1.31% |
| `GBP_JPY` | GBP/JPY | 75 | 625,000.00 | 784,054.19 | 159,054.19 | 1.25 | 6.21% | 7.35% | 22,451.63 | 3.87% | 58.67% | 16.33% | -0.89% |
| `AUD_JPY` | AUD/JPY | 75 | 625,000.00 | 771,629.15 | 146,629.15 | 1.23 | 6.05% | 6.83% | 40,888.45 | 7.23% | 62.67% | 12.75% | -4.96% |
| `CAD_JPY` | CAD/JPY | 75 | 625,000.00 | 733,618.90 | 108,618.90 | 1.17 | 5.15% | 5.19% | 35,686.87 | 7.04% | 57.33% | 11.88% | -2.33% |
| `EUR_NZD` | EUR/NZD | 75 | 625,000.00 | 711,947.31 | 86,947.31 | 1.14 | 3.00% | 4.22% | 16,623.08 | 2.38% | 58.67% | 7.11% | -1.85% |
| `GBP_NZD` | GBP/NZD | 75 | 625,000.00 | 702,310.46 | 77,310.46 | 1.12 | 2.51% | 3.78% | 11,658.57 | 2.18% | 60.00% | 8.41% | -6.55% |
| `NZD_JPY` | NZD/JPY | 75 | 625,000.00 | 695,668.07 | 70,668.07 | 1.11 | 3.68% | 3.47% | 42,100.78 | 7.59% | 57.33% | 10.67% | -4.18% |
| `AUD_NZD` | AUD/NZD | 75 | 625,000.00 | 691,887.34 | 66,887.34 | 1.11 | 2.28% | 3.30% | 3,219.71 | 1.09% | 57.33% | 4.95% | -1.99% |
| `EUR_CAD` | EUR/CAD | 75 | 625,000.00 | 677,041.17 | 52,041.17 | 1.08 | 1.56% | 2.59% | 3,447.79 | 0.69% | 49.33% | 7.25% | -7.95% |
| `GBP_CAD` | GBP/CAD | 75 | 625,000.00 | 667,896.29 | 42,896.29 | 1.07 | 1.09% | 2.15% | 4,522.72 | 1.02% | 58.67% | 5.61% | -4.04% |
| `AUD_CAD` | AUD/CAD | 75 | 625,000.00 | 658,516.07 | 33,516.07 | 1.05 | 0.87% | 1.69% | 4,175.44 | 0.85% | 52.00% | 10.46% | -8.01% |
| `EUR_AUD` | EUR/AUD | 75 | 625,000.00 | 643,001.95 | 18,001.95 | 1.03 | 0.78% | 0.92% | 20,759.49 | 3.19% | 48.00% | 6.95% | -4.08% |
| `GBP_AUD` | GBP/AUD | 75 | 625,000.00 | 634,312.79 | 9,312.79 | 1.01 | 0.23% | 0.48% | 23,537.56 | 3.66% | 46.67% | 10.62% | -9.18% |
| `EUR_GBP` | EUR/GBP | 75 | 625,000.00 | 633,753.82 | 8,753.82 | 1.01 | 0.48% | 0.45% | 0.00 | 0.00% | 42.67% | 5.55% | -5.66% |
| `NZD_CAD` | NZD/CAD | 75 | 625,000.00 | 595,126.66 | -29,873.34 | 0.95 | -1.40% | -1.59% | 6,713.70 | 1.39% | 46.67% | 7.37% | -8.99% |
| `EUR_CHF` | EUR/CHF | 75 | 625,000.00 | 579,121.40 | -45,878.60 | 0.93 | -2.53% | -2.48% | 2,343.89 | 0.47% | 42.67% | 1.31% | -6.38% |
| `GBP_CHF` | GBP/CHF | 75 | 625,000.00 | 571,197.87 | -53,802.13 | 0.91 | -2.99% | -2.92% | 10,266.95 | 2.01% | 44.00% | 3.33% | -9.41% |
| `AUD_CHF` | AUD/CHF | 75 | 625,000.00 | 565,020.99 | -59,979.01 | 0.90 | -3.20% | -3.28% | 11,555.21 | 2.57% | 54.67% | 6.06% | -12.47% |
| `CAD_CHF` | CAD/CHF | 75 | 625,000.00 | 536,131.81 | -88,868.19 | 0.86 | -4.04% | -4.99% | 5,515.58 | 1.70% | 46.67% | 4.63% | -9.51% |
| `NZD_CHF` | NZD/CHF | 75 | 625,000.00 | 511,225.99 | -113,774.01 | 0.82 | -5.35% | -6.54% | 11,892.33 | 4.65% | 42.67% | 3.12% | -10.70% |

Top performers:
- `CHF_JPY`: ending value `$865,970.82`, net PnL `$240,970.82`, XIRR `10.57%`, max DD `3.32%`
- `EUR_JPY`: ending value `$793,960.31`, net PnL `$168,960.31`, XIRR `7.76%`, max DD `4.43%`
- `GBP_JPY`: ending value `$784,054.19`, net PnL `$159,054.19`, XIRR `7.35%`, max DD `3.87%`
Weakest performers:
- `NZD_CHF`: ending value `$511,225.99`, net PnL `$-113,774.01`, XIRR `-6.54%`, max DD `4.65%`
- `CAD_CHF`: ending value `$536,131.81`, net PnL `$-88,868.19`, XIRR `-4.99%`, max DD `1.70%`
- `AUD_CHF`: ending value `$565,020.99`, net PnL `$-59,979.01`, XIRR `-3.28%`, max DD `2.57%`

### Indices

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `JP225_USD` | Nikkei 225 | 75 | 625,000.00 | 1,087,521.53 | 462,521.53 | 1.74 | 14.07% | 17.99% | 109,373.63 | 9.14% | 58.67% | 36.08% | -3.19% |
| `NAS100_USD` | Nasdaq 100 | 75 | 625,000.00 | 1,023,223.93 | 398,223.93 | 1.64 | 17.53% | 16.00% | 67,632.28 | 15.48% | 62.67% | 44.88% | -18.92% |
| `SPX500_USD` | S&P 500 | 75 | 625,000.00 | 928,500.32 | 303,500.32 | 1.49 | 12.10% | 12.84% | 41,506.95 | 9.01% | 61.33% | 24.55% | -9.53% |
| `UK100_GBP` | FTSE 100 | 75 | 625,000.00 | 858,881.27 | 233,881.27 | 1.37 | 5.15% | 10.30% | 40,985.49 | 4.55% | 60.00% | 18.55% | -11.26% |
| `US30_USD` | Dow Jones 30 | 75 | 625,000.00 | 836,841.65 | 211,841.65 | 1.34 | 8.24% | 9.46% | 36,938.21 | 7.10% | 61.33% | 16.96% | -5.15% |
| `FR40_EUR` | France 40 | 75 | 625,000.00 | 747,548.10 | 122,548.10 | 1.20 | 4.53% | 5.80% | 50,816.10 | 7.23% | 58.67% | 30.48% | -6.38% |

Top performers:
- `JP225_USD`: ending value `$1,087,521.53`, net PnL `$462,521.53`, XIRR `17.99%`, max DD `9.14%`
- `NAS100_USD`: ending value `$1,023,223.93`, net PnL `$398,223.93`, XIRR `16.00%`, max DD `15.48%`
- `SPX500_USD`: ending value `$928,500.32`, net PnL `$303,500.32`, XIRR `12.84%`, max DD `9.01%`
Weakest performers:
- `FR40_EUR`: ending value `$747,548.10`, net PnL `$122,548.10`, XIRR `5.80%`, max DD `7.23%`
- `US30_USD`: ending value `$836,841.65`, net PnL `$211,841.65`, XIRR `9.46%`, max DD `7.10%`
- `UK100_GBP`: ending value `$858,881.27`, net PnL `$233,881.27`, XIRR `10.30%`, max DD `4.55%`

### Commodities

| Symbol | Asset | Months | Contributed $ | Ending Value $ | Net PnL $ | MOIC | TWR Ann. | XIRR | Max DD $ | Max DD % | Positive Months | Best Year | Worst Year |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `XAG_USD` | Silver | 75 | 625,000.00 | 1,864,285.90 | 1,239,285.90 | 2.98 | 25.72% | 35.86% | 454,820.75 | 19.61% | 56.00% | 171.93% | -17.02% |
| `XAU_USD` | Gold | 75 | 625,000.00 | 1,397,246.31 | 772,246.31 | 2.24 | 19.61% | 26.22% | 174,589.25 | 11.11% | 57.33% | 74.95% | -4.65% |
| `WTICO_USD` | WTI Crude | 75 | 625,000.00 | 1,036,110.68 | 411,110.68 | 1.66 | 8.91% | 16.41% | 169,340.03 | 28.97% | 53.33% | 70.00% | -16.05% |
| `BCO_USD` | Brent Crude | 75 | 625,000.00 | 989,107.43 | 364,107.43 | 1.58 | 7.77% | 14.89% | 133,018.18 | 24.95% | 53.33% | 63.25% | -14.77% |

Top performers:
- `XAG_USD`: ending value `$1,864,285.90`, net PnL `$1,239,285.90`, XIRR `35.86%`, max DD `19.61%`
- `XAU_USD`: ending value `$1,397,246.31`, net PnL `$772,246.31`, XIRR `26.22%`, max DD `11.11%`
- `WTICO_USD`: ending value `$1,036,110.68`, net PnL `$411,110.68`, XIRR `16.41%`, max DD `28.97%`
Weakest performers:
- `BCO_USD`: ending value `$989,107.43`, net PnL `$364,107.43`, XIRR `14.89%`, max DD `24.95%`
- `WTICO_USD`: ending value `$1,036,110.68`, net PnL `$411,110.68`, XIRR `16.41%`, max DD `28.97%`
- `XAU_USD`: ending value `$1,397,246.31`, net PnL `$772,246.31`, XIRR `26.22%`, max DD `11.11%`

## Unavailable Symbols

- Commodities: `NATGAS`, `COPPER`, `PLATINUM`, `PALLADIUM`

## Notes

- This report uses the same pure monthly SIP baseline as the initial five-asset lecture pass.
- A positive result here does not mean the asset belongs in the final secular-bull universe; it only shows how blind monthly accumulation behaved on this feed.
- Leveraged and correction-filter versions still need separate testing.