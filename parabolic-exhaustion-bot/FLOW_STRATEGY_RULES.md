# Flow Strategy Rules

Strategy B uses a session VWAP pullback continuation model.

## Instruments

- `NAS100_USD, US30_USD`

## Timeframes

- Daily context: `1d`
- Execution timeframe: `M5`

## Session And Kill-Zone Windows

- Uses the existing London and New York session definitions from `config/strategy.yaml`.
- Kill zones are optional per parameter set and stay objective timing filters only.

## Entry Rules

- Daily ATR regime must be above the configured minimum.
- Long bias: price above VWAP, EMA fast above EMA slow, positive VWAP slope, and recent pullback back toward VWAP.
- Short bias: price below VWAP, EMA fast below EMA slow, negative VWAP slope, and recent pullback back toward VWAP.
- Long trigger: bullish continuation bar closes through the prior bar high after the pullback.
- Short trigger: bearish continuation bar closes through the prior bar low after the pullback.

## Stop Rules

- Long stop: recent swing low minus ATR buffer.
- Short stop: recent swing high plus ATR buffer.

## Take-Profit Rules

- Partial profit at configured partial R.
- Stop moves to break-even after the partial when enabled.
- Final target at configured target R.
- Exit on VWAP invalidation before the partial or at forced end-of-session cutoff.

## Risk And Trade Limits

- Max trades per day per symbol: default `2` before parameter overrides.
- Fixed-R trade model with no overnight holds.
