# CWT FWM Hybrid Research

## Scope

- Research-only comparison. Live `strategy_four` was left untouched.
- Baseline frozen to current CWT benchmark style:
  - `H1` bias
  - minimum timeframe by symbol
  - `Scenario 1 + Scenario 2`
  - fixed `1:1` exit
  - ZigZag/Cambist `12 / 5 / 3`
  - ladder `0.07 / 0.20 / 0.45 / 1.00`
  - funded caps `$1,000 / $5,000 / $95,000 brake`

## FWM Assumptions

- swing lookback: `8` bars
- gate lookback: `12` bars
- stop-order validity: `2` bars
- long FWM candidate: lowest low in lookback, close in upper half, low below Alligator cluster, lips flattening/up
- short FWM candidate: highest high in lookback, close in lower half, high above Alligator cluster, lips flattening/down
- no AO, no fractal breakout lane, no pyramiding, no Williams trailing exits

## Portfolio Comparison

| Mode | Trades Taken | Win Rate | PF | Ending Balance | Net PnL | Return | Max DD | Avg Hold | Skipped by Caps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 15402 | 53.84% | 1.28 | $496,687.88 | $396,687.88 | 396.69% | $13,606.74 | 181.74m | 4890 |
| fwm_gate | 3706 | 52.54% | 1.13 | $149,835.24 | $49,835.24 | 49.84% | $22,448.76 | 158.86m | 186 |
| fwm_entry_lane | 16527 | 54.66% | 1.32 | $580,917.36 | $480,917.36 | 480.92% | $10,117.14 | 161.64m | 6343 |
| fwm_selective | 16385 | 54.56% | 1.34 | $599,577.87 | $499,577.87 | 499.58% | $9,894.79 | 165.23m | 6032 |

## Verdict

Baseline reference on the 8-symbol shortlist finished at $496,687.88, 396.69% return, PF `1.28`, and max drawdown $13,606.74.

### fwm_gate

- verdict: `discard`
- PF `1.28` -> `1.13`
- return `396.69%` -> `49.84%`
- max DD `13606.74` -> `22448.76`
- trades `15402` -> `3706`
- improving symbols: `0` / `8`
- why it failed: `pf_improved_meaningfully, return_improved_without_pf_damage, drawdown_ok, trades_ok, breadth_ok`

### fwm_entry_lane

- verdict: `keep`
- PF `1.28` -> `1.32`
- return `396.69%` -> `480.92%`
- max DD `13606.74` -> `10117.14`
- trades `15402` -> `16527`
- improving symbols: `6` / `8`
- why it passed: all phase-1 acceptance checks cleared

### fwm_selective

- verdict: `keep`
- PF `1.28` -> `1.34`
- return `396.69%` -> `499.58%`
- max DD `13606.74` -> `9894.79`
- trades `15402` -> `16385`
- improving symbols: `7` / `8`
- why it passed: all phase-1 acceptance checks cleared

## Scenario Mix

### baseline

- raw scenario mix: `{'scenario1': 12329, 'scenario2': 7963}`
- funded scenario mix: `{'scenario1': 9381, 'scenario2': 6021}`
- funded source mix: `{'baseline': 15402}`

### fwm_gate

- raw scenario mix: `{'scenario1': 1668, 'scenario2': 2224}`
- funded scenario mix: `{'scenario1': 1583, 'scenario2': 2123}`
- funded source mix: `{'baseline': 3706}`

### fwm_entry_lane

- raw scenario mix: `{'fwm': 2945, 'scenario1': 12291, 'scenario2': 7634}`
- funded scenario mix: `{'fwm': 2154, 'scenario1': 8899, 'scenario2': 5474}`
- funded source mix: `{'baseline': 14373, 'fwm': 2154}`

### fwm_selective

- raw scenario mix: `{'fwm': 2427, 'scenario1': 12297, 'scenario2': 7693}`
- funded scenario mix: `{'fwm': 1779, 'scenario1': 9021, 'scenario2': 5585}`
- funded source mix: `{'baseline': 14606, 'fwm': 1779}`

## Per-Symbol Contribution

### baseline

| Symbol | Timeframe | Net PnL | Win Rate | Trades Taken |
|---|---|---:|---:|---:|
| `NAS100_USD` | `5m` | $70,879.50 | 55.93% | 2160 |
| `SPX500_USD` | `5m` | $50,231.99 | 54.67% | 2047 |
| `UK100_GBP` | `5m` | $35,697.63 | 54.41% | 1711 |
| `USD_JPY` | `5m` | $66,670.57 | 54.86% | 2244 |
| `NZD_USD` | `5m` | $54,636.15 | 52.81% | 2081 |
| `AUD_USD` | `5m` | $42,000.01 | 52.40% | 2044 |
| `EUR_USD` | `5m` | $41,390.63 | 52.60% | 2116 |
| `GBP_JPY` | `15m` | $35,181.40 | 52.05% | 999 |

### fwm_gate

| Symbol | Timeframe | Net PnL | Win Rate | Trades Taken |
|---|---|---:|---:|---:|
| `NAS100_USD` | `5m` | $13,418.88 | 54.14% | 495 |
| `SPX500_USD` | `5m` | $17,668.49 | 54.35% | 563 |
| `UK100_GBP` | `5m` | $3,140.19 | 54.71% | 446 |
| `USD_JPY` | `5m` | $10,304.68 | 55.74% | 531 |
| `NZD_USD` | `5m` | $9,903.94 | 50.96% | 522 |
| `AUD_USD` | `5m` | $1,219.69 | 51.04% | 529 |
| `EUR_USD` | `5m` | $-3,896.15 | 48.49% | 497 |
| `GBP_JPY` | `15m` | $-1,924.47 | 45.53% | 123 |

### fwm_entry_lane

| Symbol | Timeframe | Net PnL | Win Rate | Trades Taken |
|---|---|---:|---:|---:|
| `NAS100_USD` | `5m` | $64,049.98 | 55.63% | 2229 |
| `SPX500_USD` | `5m` | $63,202.43 | 55.37% | 2207 |
| `UK100_GBP` | `5m` | $44,408.41 | 55.59% | 1871 |
| `USD_JPY` | `5m` | $75,304.96 | 55.86% | 2365 |
| `NZD_USD` | `5m` | $90,991.85 | 54.20% | 2299 |
| `AUD_USD` | `5m` | $63,370.02 | 53.84% | 2279 |
| `EUR_USD` | `5m` | $48,986.30 | 52.88% | 2243 |
| `GBP_JPY` | `15m` | $30,603.41 | 53.29% | 1034 |

### fwm_selective

| Symbol | Timeframe | Net PnL | Win Rate | Trades Taken |
|---|---|---:|---:|---:|
| `NAS100_USD` | `5m` | $76,594.51 | 56.24% | 2164 |
| `SPX500_USD` | `5m` | $68,388.10 | 55.16% | 2219 |
| `UK100_GBP` | `5m` | $52,828.43 | 55.67% | 1886 |
| `USD_JPY` | `5m` | $74,791.82 | 55.82% | 2372 |
| `NZD_USD` | `5m` | $89,913.36 | 54.12% | 2295 |
| `AUD_USD` | `5m` | $57,557.03 | 53.70% | 2272 |
| `EUR_USD` | `5m` | $45,464.85 | 52.64% | 2200 |
| `GBP_JPY` | `15m` | $34,039.77 | 51.69% | 977 |

## Recommendation

Phase 1 found a viable FWM hybrid path in: `fwm_entry_lane, fwm_selective`. Only after that should phase 2 even consider fractal confirmation.
