# Advanced Engulfing Batch

## Setup

- Date range: `2025-01-01` to `2026-04-01`
- Universe config: `config\advanced_engulfing_market_constraints.json`
- Symbols requested: `1`
- Trend filter: price above/below `EMA(50)`
- Structure: confirmed fractal `HH` / `LL`
- Pullback: at least `2` opposite-color candles
- Entry: strict advanced engulfing definition
- Target: fixed `1R`
- EMA slope filter: off in Phase 1

## Results

| Group | Symbol | TF | Trades | Win Rate | Avg R | PF | Max DD R | Win Streak | Loss Streak | TP | SL | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `crypto` | `BTC_USD` | `15m` | 84 | 54.76% | 0.078 | 1.17 | 11.00 | 7 | 7 | 43 | 37 | Mixed |