# Boards Overview

## Purpose

This file is the quick operational map of the live Discord boards and related projects in `swing-pr1`.

## Live Boards In The Shared Platform

| Board | Strategy id | Runtime | Cadence | Core output |
|---|---|---|---|---|
| Measured Drift | `little_rzy` | `signal_platform` route plus standalone bot | `4h` | Tactical continuation alerts |
| Measured Drift 1H | `little_rzy_1h` | `signal_platform` route | `1h` | Research and paper lower-timeframe continuation alerts |
| Trend Current | `strategy_two` | `signal_platform` route | `4h` | Managed basket lifecycle alerts |
| Cambist With Trend | `strategy_four` | `signal_platform` route | `M5` and `M15` | Lower-timeframe tactical continuation alerts |
| Secular Bull SIP | `strategy_five` | `signal_platform` route | Monthly and daily check cadence | Allocation and review board |

## Separate Standalone Project

| Project | Runtime | Current operational scope |
|---|---|---|
| `parabolic-exhaustion-bot` | standalone | NAS100 paper-forward parabolic exhaustion alerts |

This project is part of the repo, but not part of the shared `signal_platform` registry.

## Board Summaries

### Measured Drift

- Base implementation lives in [little_rzy_bot](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot).
- Shared route adapter lives in [little_rzy_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/little_rzy_strategy.py).
- Supports standalone research, backtests, and OANDA watchlist scans.
- Uses signal journaling, outcome tracking, and weekly and monthly report support when run through the platform.

### Trend Current

- Scanner lives in [strategy_two_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot/scanner.py).
- Shared route adapter lives in [trend_current_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/trend_current_strategy.py).
- Treats a position as one managed basket rather than independent random trades.
- Emits entry, add, move-stop, basket-exit, and cooldown lifecycle events.

### Cambist With Trend

- Scanner lives in [strategy_four_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_four_bot/scanner.py).
- Shared route adapter lives in [cwt_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/cwt_strategy.py).
- Uses `H1` bias plus `M5` and `M15` execution depending on the symbol.
- Includes ladder-based recommended risk sizing and recent-entry catch-up support.

### Secular Bull SIP

- Scanner lives in [strategy_five_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_five_bot/scanner.py).
- Shared route adapter lives in [secular_bull_sip_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/secular_bull_sip_strategy.py).
- Not a normal intraday trade board.
- Posts monthly allocation and review events for a macro basket.

### Parabolic Exhaustion

- Lives entirely in [parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot).
- Current operational scope is a NAS100 paper-forward alert profile.
- Use that project's own README for research, replay, and forward-test details.

## Which Board To Use For What

| Need | Best board |
|---|---|
| Higher-timeframe tactical continuation ideas | Measured Drift |
| Basket-style lifecycle management | Trend Current |
| Lower-timeframe tactical trend continuation | Cambist With Trend |
| Monthly long-only allocation board | Secular Bull SIP |
| Separate NAS100 paper-forward parabolic study | Parabolic Exhaustion |

## Experimental Or Research-Only Areas

- `little_rzy_1h` is disabled by default in the example config.
- The `parabolic-exhaustion-bot` project includes research-only and replay-only components that are not part of the shared root runtime.
- Several strategy docs in this repo describe research work that is not automatically launched as a live Discord board.
