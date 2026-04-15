# Trend Current

## What it is

Trend Current is the managed-basket strategy in the platform.

Route and code:

- route id: `strategy_two`
- adapter: [signal_platform/trend_current_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/trend_current_strategy.py)
- scanner package: [strategy_two_bot](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot)

## Core idea

Trend Current is not meant to behave like a stream of unrelated trade alerts.
It treats a valid trend continuation as one managed basket:

- new basket
- add
- move stop
- basket exit

That means the board is intentionally quieter, but each active basket carries
more lifecycle information than the tactical routes.

## Timeframe and watchlist

Default live route:

- watchlist: `core-4h`
- execution timeframe: `H4`
- higher timeframe context: `1d`

## How signals are generated

The route adapter delegates to
[strategy_two_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/strategy_two_bot/scanner.py),
which produces:

- scan rows
- event payloads
- basket state

The adapter then converts those events into `PlatformSignal` objects for the
shared runtime.

## What it sends

Typical Trend Current Discord events include:

- new basket
- add
- move stop
- basket exit
- cooldown / holding-state style events where applicable

## How outcomes are tracked

Trend Current is treated as a managed-events board, not a standard TP/SL journal
board. The platform still records route health and event state, but the logic is
about basket progression rather than single-trade closure math.

## Why it matters

Trend Current is the main challenger to Measured Drift in tactical maturity. It
brings a different style of signal communication:

- less trade spam
- more stateful position management
- basket-level risk framing
