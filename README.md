# Little RZY Signal Bot

This repo contains the current best Python implementation of the Little RZY strategy as a:

- backtest runner
- live signal scanner
- market-profiled research bot

It also now includes a reusable multi-strategy signal platform so additional strategies can share the same runtime and Discord delivery flow.

It does not place broker orders yet. The current target is a reliable signal bot first, then Discord delivery, then optional live execution later.

## Current Status

The strategy is now in its strongest tested form so far:

- Fixed the original optimistic backtest behavior
- Tightened the structure rules to match the written Little RZY process more closely
- Switched to a hybrid stop model
- Added market-specific tuning profiles
- Kept only the ATR stop-width changes that actually improved results
- Added live watchlists and scan mode for the best 4h markets

## Best Current Focus

Timeframe:

- `4h`

Primary assets:

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`
- `UK100_GBP`
- `NAS100_USD`
- `XAU_USD`

The current working view is that this strategy behaves best as a market-specific 4h continuation model. It did not hold up as a universal all-market, all-timeframe system.

## Final Kept Changes

What we kept:

- stricter structure detection
- next-bar style backtest fills
- hybrid stop model
- family and symbol-specific profiles
- selective ATR stop tightening

What we tested and rejected as defaults:

- global higher-timeframe confirmation
- global rejection-candle requirement
- global early-maturity cap

Those ideas were useful to test, but they hurt too many good markets when applied universally.

## Final Profile Layer

Current profile settings in [little_rzy_bot/profiles.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/profiles.py):

- Energy (`WTICO_USD`, `BCO_USD`)
  - retrace `0.25 -> 0.65`
  - `min_rr = 1.0`
  - `atr_stop_padding = 0.15`
- Silver (`XAG_USD`)
  - retrace `0.20 -> 0.60`
  - `max_setup_age_bars = 8`
  - `atr_stop_padding = 0.15`
- Gold (`XAU_USD`)
  - retrace `0.20 -> 0.60`
  - `max_setup_age_bars = 8`
  - `atr_stop_padding = 0.25`
- Indices (`UK100_GBP`, `NAS100_USD`)
  - retrace `0.25 -> 0.65`
  - `min_rr = 1.0`
  - `atr_stop_padding = 0.05`

## Benchmark Snapshot

Current best long-window benchmark snapshot:

| Asset | Timeframe | Trades | Win Rate | Avg R | Profit Factor |
| --- | --- | ---: | ---: | ---: | ---: |
| `WTICO_USD` | `4h` | 172 | 40.12% | 0.250 | 1.75 |
| `BCO_USD` | `4h` | 152 | 33.55% | 0.170 | 1.48 |
| `XAG_USD` | `4h` | 175 | 36.57% | 0.178 | 1.50 |
| `XAU_USD` | `4h` | 84 | 28.57% | 0.070 | 1.14 |
| `UK100_GBP` | `4h` | 23 | 43.48% | 1.025 | 2.96 |
| `NAS100_USD` | `4h` | 14 | 35.71% | 2.184 | 4.40 |

Notes:

- `NAS100_USD` uses a longer test window because it is sparse and needed more history.
- `UK100_GBP` and `NAS100_USD` look strong, but they still have lower sample counts than energy and silver.
- `WTICO_USD`, `BCO_USD`, and `XAG_USD` are the best balanced candidates today.

## Portfolio What-If

Using the improved ATR version, if you traded every signal across the primary 4h basket during calendar year 2025 with:

- starting equity = `$100,000`
- fixed risk per trade = `$500`

the result was:

- ending equity = `$118,961.55`
- total PnL = `$18,961.55`
- trades = `125`
- win rate = `39.2%`
- average trade = `0.303R`
- max drawdown = `-$4,501.35`

See [docs/PORTFOLIO_EXAMPLES.md](/C:/Users/Seeker/Documents/swing-pr1/docs/PORTFOLIO_EXAMPLES.md) for the full breakdown and the assumption note about `0.5%` versus `0.05%`.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

### Smoke test

```bash
python -m little_rzy_bot --out backtest_output
```

### Backtest a CSV

```bash
python -m little_rzy_bot --csv data/your_ohlcv.csv --timestamp-col timestamp --out backtest_output
```

### Fetch Yahoo data and backtest

```bash
python -m little_rzy_bot --provider yahoo --symbol SPY --interval 1d --period 1y --out backtest_output
```

### Fetch OANDA data and backtest

```bash
python -m little_rzy_bot --provider oanda --symbol EUR_USD --granularity H4 --start 2024-01-01 --end 2024-06-30 --oanda-env practice --out backtest_output
```

### Run the current live scan watchlist

```bash
python -m little_rzy_bot --scan --watchlist primary-4h --granularity H4 --higher-timeframe 1d --oanda-env practice --out live_scan_output
```

### Disable the auto-profile layer

```bash
python -m little_rzy_bot --provider oanda --symbol WTICO_USD --granularity H4 --start 2024-01-01 --end 2024-06-30 --disable-auto-profile --out backtest_output
```

## Docs

- Research learnings: [docs/RESEARCH_LEARNINGS.md](/C:/Users/Seeker/Documents/swing-pr1/docs/RESEARCH_LEARNINGS.md)
- Launch prep: [docs/LAUNCH_PREP.md](/C:/Users/Seeker/Documents/swing-pr1/docs/LAUNCH_PREP.md)
- Portfolio examples: [docs/PORTFOLIO_EXAMPLES.md](/C:/Users/Seeker/Documents/swing-pr1/docs/PORTFOLIO_EXAMPLES.md)
- Multi-strategy platform: [docs/MULTI_STRATEGY_PLATFORM.md](/C:/Users/Seeker/Documents/swing-pr1/docs/MULTI_STRATEGY_PLATFORM.md)

## Multi-Strategy Platform

The repo now includes a generic signal-platform layer for future strategies.

List strategies:

```bash
python -m signal_platform list-strategies
```

Run Little RZY through the platform:

```bash
python -m signal_platform scan --strategy little_rzy --watchlist primary-4h --granularity H4 --oanda-env practice --out platform_output/little_rzy
```

Run config-based routes:

```bash
python -m signal_platform run-config --config config/platform.example.json
```

The config example is at [config/platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json).

## Repo Layout

- [little_rzy_bot/__main__.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/__main__.py): CLI entrypoint
- [little_rzy_bot/market_data.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/market_data.py): OANDA and Yahoo fetching
- [little_rzy_bot/signal_engine.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/signal_engine.py): signal generation
- [little_rzy_bot/structure_detection.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/structure_detection.py): Little RZY structure logic
- [little_rzy_bot/backtest_adapter.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/backtest_adapter.py): trade simulation
- [little_rzy_bot/profiles.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/profiles.py): market and symbol-specific tuning
- [little_rzy_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/scanner.py): watchlist scanning
- [little_rzy_bot/watchlists.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/watchlists.py): current production watchlists

## Next Stage

The next recommended step is:

1. Keep this as a signal bot
2. Add Discord webhook delivery
3. Run it live on the primary 4h watchlist
4. Validate paper/live behavior before any broker execution

The launch prep is documented in [docs/LAUNCH_PREP.md](/C:/Users/Seeker/Documents/swing-pr1/docs/LAUNCH_PREP.md).
