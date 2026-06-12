# CWT Readiness (3Y)

## Summary

CWT is now strong enough to move from research into bot-prep, but only with a narrowed universe.

The 3-year batch says the strategy is strongest on:

- `5m` indices
- `5m` major FX
- a few `15m` JPY/NZD/GBP crosses

It is not strong enough to justify a broad "trade everything" bot.

## Keep / Watch / Exclude

Reference:

- [CWT_EXECUTIVE_SHORTLIST_3Y.md](/C:/Users/Seeker/Documents/swing-pr1/reports/cwt_forex/CWT_EXECUTIVE_SHORTLIST_3Y.md)
- [ASSET_BATCH_REPORT_3y.md](/C:/Users/Seeker/Documents/swing-pr1/reports/cwt_forex/ASSET_BATCH_REPORT_3y.md)

## Production Recommendation

Phase 1 live board:

- `NAS100_USD`
- `SPX500_USD`
- `UK100_GBP`
- `USD_JPY`
- `NZD_USD`
- `AUD_USD`
- `EUR_USD`
- `GBP_JPY`

Phase 2 watch expansion:

- `FR40_EUR`
- `GBP_USD`
- `US30_USD`
- `USD_CHF`
- `GBP_NZD`
- `NZD_JPY`
- `XAG_USD`
- `BCO_USD`

## Why This Narrowing

- stronger 3-year dollar outcomes
- better repeatability than the weaker crosses
- more stable PF and win rate
- fewer obvious "funded brake" failures than the excluded names

## Next Build Step

The next phase should be:

1. freeze the shortlist as machine-readable watchlists
2. create a CWT bot package with `core`, `watch`, and `broad` watchlists
3. keep CWT separate from Measured Drift and Trend Current
4. only after that decide whether to wire it into the multi-strategy platform
