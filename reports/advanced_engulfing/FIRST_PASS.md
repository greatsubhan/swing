# Advanced Engulfing First Pass

## Setup

- Date range: `2025-01-01` to `2026-04-01`
- Assets: `BTC_USD`, `ETH_USD`, `NAS100_USD`
- Timeframes: `15m`, `1h`
- Trend filter: price above/below `EMA(50)`
- Structure: confirmed fractal `HH` / `LL`
- Pullback: at least `2` opposite-color candles
- Entry: strict advanced engulfing definition
- Target: fixed `1R`
- EMA slope filter: off in Phase 1

## Results

| Symbol | TF | Trades | Win Rate | Avg R | PF | Max DD R | Win Streak | Loss Streak | TP | SL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `BTC_USD` | `15m` | 84 | 54.76% | 0.078 | 1.17 | 11.00 | 7 | 7 | 43 | 37 | Mixed |
| `BTC_USD` | `1h` | 16 | 43.75% | -0.125 | 0.78 | 4.00 | 2 | 3 | 7 | 9 | Weak |
| `ETH_USD` | `15m` | 56 | 41.07% | -0.219 | 0.62 | 14.30 | 3 | 5 | 19 | 32 | Weak |
| `ETH_USD` | `1h` | 19 | 26.32% | -0.439 | 0.37 | 9.34 | 1 | 5 | 5 | 13 | Weak |
| `NAS100_USD` | `15m` | 76 | 55.26% | 0.087 | 1.21 | 8.90 | 5 | 7 | 36 | 30 | Promising |
| `NAS100_USD` | `1h` | 18 | 22.22% | -0.556 | 0.29 | 11.00 | 2 | 9 | 4 | 14 | Weak |