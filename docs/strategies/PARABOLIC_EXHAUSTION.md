# Parabolic Exhaustion

## What it is

Parabolic Exhaustion is a separate research and alerting project located in:

- [parabolic-exhaustion-bot](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot)

It is not currently part of the shared `signal_platform` runtime.

## Scope

Current focus is a paper-forward exhaustion strategy on instruments such as:

- `XAU_USD`
- `XAG_USD`
- `WTICO_USD`
- `NAS100_USD`
- `UK100_GBP`
- `US30_USD`
- `SPX500_USD`

## Current implementation state

The subproject already includes:

- config loading
- feature engineering
- research backtesting
- replay logic
- live alert scanning
- Discord publication
- tests

## Why it is documented separately

Although it lives in the same repo, it has a different shape from the main
platform:

- its own source tree
- its own config patterns
- its own output folders
- its own research notes and runbooks

For now, treat it as a sibling project rather than a `signal_platform` route.

## Main reference

Read:

- [parabolic-exhaustion-bot/README.md](/C:/Users/Seeker/Documents/swing-pr1/parabolic-exhaustion-bot/README.md)
