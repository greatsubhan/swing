# Secular Bull SIP Regime Analogs

## Method

- Regime definition: last 12 completed monthly bars across the core Secular Bull assets.
- Similarity method: Euclidean distance across concatenated monthly return vectors for Gold, Nasdaq, Dow, Bitcoin, and Ethereum.
- Analogs selected: the two closest non-overlapping historical 12-month windows with a full following 12-month window available.
- SIP model inside each window: long-only, no leverage, no stop, monthly contribution `$8,333.33` per asset.

## Current Regime

- Current comparison window: `2025-03-31 21:00:00+00:00` to `2026-02-28 22:00:00+00:00`
- Basket mean ending value over that 12-month SIP slice: `$95,866.29`
- Basket mean net PnL: `$-4,133.71`
- Basket mean max drawdown: `8.76%`

## Analog 1

- Similarity distance: `0.952987`
- Matching window: `2023-10-31 21:00:00+00:00` to `2024-09-30 21:00:00+00:00`
- Following window: `2024-10-31 21:00:00+00:00` to `2025-09-30 21:00:00+00:00`

### Matching Window

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 123,238.55 | 23,238.55 | 0.00% |
| `NAS100_USD` | 112,018.41 | 12,018.41 | 0.00% |
| `US30_USD` | 108,538.02 | 8,538.02 | 0.00% |
| `BTC_USD` | 133,114.72 | 33,114.72 | 3.87% |
| `ETH_USD` | 94,125.89 | -5,874.11 | 14.72% |

- Basket mean net PnL: `$14,207.12` with mean max DD `3.72%`

### Following 12 Months

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 130,444.60 | 30,444.60 | 0.00% |
| `NAS100_USD` | 120,859.64 | 20,859.64 | 0.00% |
| `US30_USD` | 109,530.49 | 9,530.49 | 0.00% |
| `BTC_USD` | 114,167.30 | 14,167.30 | 0.00% |
| `ETH_USD` | 139,740.60 | 39,740.60 | 11.90% |

- Basket mean net PnL: `$22,948.53` with mean max DD `2.38%`

## Analog 2

- Similarity distance: `1.098607`
- Matching window: `2021-06-30 21:00:00+00:00` to `2022-05-31 21:00:00+00:00`
- Following window: `2022-06-30 21:00:00+00:00` to `2023-05-31 21:00:00+00:00`

### Matching Window

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 99,011.99 | -988.01 | 0.00% |
| `NAS100_USD` | 77,864.48 | -22,135.52 | 3.76% |
| `US30_USD` | 88,791.54 | -11,208.46 | 0.00% |
| `BTC_USD` | 43,997.76 | -56,002.24 | 43.03% |
| `ETH_USD` | 34,539.57 | -65,460.43 | 54.53% |

- Basket mean net PnL: `$-31,158.93` with mean max DD `20.26%`

### Following 12 Months

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 105,851.15 | 5,851.15 | 0.00% |
| `NAS100_USD` | 124,647.61 | 24,647.61 | 0.00% |
| `US30_USD` | 105,711.41 | 5,711.41 | 0.00% |
| `BTC_USD` | 144,840.98 | 44,840.98 | 3.97% |
| `ETH_USD` | 132,248.44 | 32,248.44 | 1.72% |

- Basket mean net PnL: `$22,659.92` with mean max DD `1.14%`

## Analog 3

- Label: `US-Iran crisis / early 2020 geopolitical shock`
- Matching window: `2020-01-31 22:00:00+00:00` to `2020-12-31 22:00:00+00:00`
- Following window: `2021-01-31 22:00:00+00:00` to `2021-12-31 22:00:00+00:00`

### Matching Window

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 104,476.74 | 4,476.74 | 0.00% |
| `NAS100_USD` | 127,536.86 | 27,536.86 | 0.00% |
| `US30_USD` | 113,267.17 | 13,267.17 | 0.00% |
| `BTC_USD` | 327,100.77 | 227,100.77 | 0.00% |
| `ETH_USD` | 501,557.48 | 401,557.48 | 12.80% |

- Basket mean net PnL: `$134,787.80` with mean max DD `2.56%`

### Following 12 Months

| Asset | Ending Value $ | Net PnL $ | Max DD % |
|---|---:|---:|---:|
| `XAU_USD` | 100,258.63 | 258.63 | 0.00% |
| `NAS100_USD` | 102,786.36 | 2,786.36 | 1.77% |
| `US30_USD` | 103,295.18 | 3,295.18 | 0.00% |
| `BTC_USD` | 85,425.29 | -14,574.71 | 22.41% |
| `ETH_USD` | 110,744.82 | 10,744.82 | 35.92% |

- Basket mean net PnL: `$502.06` with mean max DD `12.02%`

## Read

- Pure monthly SIP should be judged by how well it survives messy windows without requiring timing skill.
- If the analog matching windows and the following windows remain broadly positive on the core assets, that supports staying systematic during noisy periods.
- If leveraged versions are tested later, these same analog windows will be the right place to stress-test them.