# Measured Drift

## What it is

Measured Drift is the main tactical `4h` continuation board in `swing-pr1`.

Route and code:

- route id: `little_rzy`
- adapter: [signal_platform/little_rzy_strategy.py](/C:/Users/Seeker/Documents/swing-pr1/signal_platform/little_rzy_strategy.py)
- engine package: [little_rzy_bot](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot)

## Role in the project

This is the most mature tactical board in the repo. It is the baseline signal
engine that the rest of the platform architecture was originally built around.

## Timeframe and watchlist

Default live route:

- watchlist: `primary-4h`
- execution timeframe: `H4`
- higher timeframe: `1d`

Research-only variant:

- route id: `little_rzy_1h`
- watchlist: `research-1h`
- execution timeframe: `H1`
- higher timeframe bias: `H4`

## How signals are generated

The platform route calls the standalone scanner in
[little_rzy_bot/scanner.py](/C:/Users/Seeker/Documents/swing-pr1/little_rzy_bot/scanner.py).

Important building blocks:

- market-family profiles
- structure detection
- measured-move continuation logic
- profile-tuned ATR behavior
- optional logging of filtered setups and accepted signals

## What it sends

The live route can send:

- tactical entry cards
- TP / SL / break-even outcome cards
- weekly and monthly review cards

## How outcomes are tracked

Measured Drift is journal-backed:

- open signals are written to `signal_journal.json`
- later route cycles re-check open entries
- outcome cards are posted when TP / SL / BE is detected
- missed closure notifications are recoverable if they remain unnotified

## Why it matters

Measured Drift is the repo’s reference tactical board. Operational improvements
to the runtime are usually validated here first before being generalized.

## Research notes

The strongest established lane remains:

- `4h`
- market-family or symbol-specific tuning
- selective basket rather than universal expansion

The `1h` route exists, but it is still research-only and disabled by default.
