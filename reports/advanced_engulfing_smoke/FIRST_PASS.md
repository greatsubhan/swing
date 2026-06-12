# Advanced Engulfing Batch

## Setup

- Date range: `2025-01-01` to `2026-04-01`
- Universe config: `config\advanced_engulfing_market_constraints.json`
- Symbols requested: `3`
- Trend filter: price above/below `EMA(50)`
- Structure: confirmed fractal `HH` / `LL`
- Pullback: at least `2` opposite-color candles
- Entry: strict advanced engulfing definition
- Target: fixed `1R`
- EMA slope filter: off in Phase 1

## Results

| Group | Symbol | TF | Trades | Win Rate | Avg R | PF | Max DD R | Win Streak | Loss Streak | TP | SL | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `indices` | `NAS100_USD` | `5m` | 235 | 54.04% | 0.067 | 1.15 | 9.98 | 6 | 5 | 114 | 100 | Mixed |
| `crypto` | `BTC_USD` | `15m` | 84 | 54.76% | 0.078 | 1.17 | 11.00 | 7 | 7 | 43 | 37 | Mixed |
| `crypto` | `ETH_USD` | `15m` | 56 | 41.07% | -0.219 | 0.62 | 14.30 | 3 | 5 | 19 | 32 | Weak |