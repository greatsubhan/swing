# Secular Bull SIP Strategy (Draft Spec)

## Status

This is the working draft for the long-only `Secular Bull SIP` strategy based on:

- [Week11SecularBullMarket.pdf](/C:/Users/Seeker/Downloads/Week11SecularBullMarket.pdf)
- the user's earlier lecture notes

This strategy is separate from:

- `Measured Drift`
- `Trend Current`
- `Cambist With Trend`

It is a long-term accumulation strategy, not an intraday signal system.

## Current Research State

What is already completed:

- pure monthly SIP baseline
- crypto-only SIP slice
- wider monthly-universe SIP scan
- regime analogue study
- leveraged monthly SIP stress test

Key read from the leveraged pass:

- `XAU_USD` / Gold is the only clean `keep` under the first leveraged stress test
- `NAS100_USD` and `US30_USD` are usable only with caution
- `BTC_USD` and `ETH_USD` still have enormous upside, but their leveraged drawdowns are too violent for a clean production recommendation
- correction-entry SIP is still deferred until after the leveraged lane is reviewed
- no SIP bot/product layer should be built yet

## Core Idea

A `secular bull market` is a market that can continue making higher prices for many years.

The lecture examples focus on assets that are treated as long-run winners:

- `XAU_USD` / Gold
- `NAS100_USD` / Nasdaq 100
- `US30_USD` / Dow Jones 30
- `BTC_USD`
- `ETH_USD`

The idea is not to catch reversals. The idea is to keep building exposure over time in assets that are already in a long-term bull regime.

## Two Variants

The lecture clearly describes two versions of the strategy.

### 1. Without Leverage

This is the simpler `spot / investment` version.

Rules:

- add capital on a recurring basis
- buy the secular-bull asset
- either buy at current market price or wait for a correction / support level
- no stop loss is required in the lecture framing

The lecture presents this as a lower-risk inflation-beating investment style rather than a short-term trading model.

### 2. With Leverage

This is the prop-firm or leveraged version.

Rules:

- still build positions over time
- still only trade secular-bull assets
- size monthly contributions using a fixed yearly budget split
- stop loss is required to protect funded-account limits

This is the version that is most relevant for future bot or backtest work.

## Asset Universe

The lecture repeatedly uses these as the main assets:

- `XAU_USD`
- `NAS100_USD`
- `US30_USD`
- `BTC_USD`
- `ETH_USD`

Current recommendation is to keep the first backtest limited to those five.

## Timeframe Structure

The lecture framing is primarily:

- `Monthly` for regime and accumulation

The user's notes also mention waiting for corrections using technical analysis.

So the practical structure for backtesting should likely be:

- regime / accumulation clock: `1M`
- optional correction-entry filter: `1W` or `1D`

This is not a lower-timeframe strategy.

## Position Building Logic

### Base SIP Logic

The lecture repeatedly describes a monthly contribution model.

Interpretation:

- every month, allocate a fixed amount to the chosen asset
- continue building as long as the long-term secular-bull regime remains valid

For a first backtest, the simplest faithful version is:

1. choose one asset
2. invest once per month
3. hold prior tranches
4. do not short

### Correction Entry Option

The lecture also allows:

- buying at support
- waiting for a good correction

This is less precisely defined than the monthly accumulation rule.

So the safest research order is:

1. monthly blind SIP baseline
2. monthly plus correction-entry variant

## Lot Size / Sizing Logic

### Without Leverage

The user's notes and lecture formula imply:

```text
lot_size = monthly_investment / current_price / contract_size
```

The deck uses this style for Gold and the index examples.

### Leveraged Version

The lecture logic is:

1. start from account size
2. divide by `12`
3. that becomes the monthly investment amount
4. convert that into lot size using current price and contract size
5. optionally multiply by the leverage ratio

So the working formula is:

```text
monthly_budget = account_size / 12
base_lot = monthly_budget / current_price / contract_size
leveraged_lot = base_lot * leverage_multiplier
```

Examples shown in the deck:

- Gold:
  - `Mockapital $100K` often shown as `0.05` lots in examples
- ETH:
  - contract size shown as `1`
  - examples show month-by-month lot variation based on current ETH price
- NAS100:
  - contract size shown as `1`
  - examples use `0.1` and `0.5` style lots in illustrations

## Stop-Loss Logic

The lecture separates this clearly:

### Without Leverage

- no SL required in the lecture framing

### With Leverage

- SL is required
- purpose is not a tactical intraday invalidation
- purpose is to keep the account from breaching funded-account risk rules during deeper corrections

The lecture notes mention that this protects the account against deeper pullbacks like:

- `15%`
- `20%`

Important unresolved detail:

- the lecture material does not provide a single exact universal SL rule
- it emphasizes risk containment rather than a fixed chart-pattern stop model

So for backtesting, the stop rule still needs to be explicitly defined.

## Most Faithful First Backtest Variants

Because the lecture is more investment-focused than rule-heavy, the cleanest path is to test small rule families.

### Variant A: Pure Monthly SIP

- pick one asset
- buy once per month at monthly open
- no leverage
- no stop
- hold all tranches through the full sample

This is the simplest lecture-faithful baseline.

### Variant B: Leveraged Monthly SIP

- pick one asset
- monthly budget = `account / 12`
- convert to lot size
- apply leverage multiplier
- use a protective stop based on a fixed correction allowance

Candidate protective stop models:

- `10%`
- `15%`
- `20%`

### Variant C: Monthly SIP With Correction Filter

- still add once per month
- but only after price pulls back to a weekly or daily support measure
- possible filters:
  - `20 EMA`
  - `50 EMA`
  - previous monthly low zone
  - ATR correction threshold

This is closer to the lecture's “wait for a good correction” language, but it is more interpretive.

## What The Deck Confirms Well

- long-only thesis
- monthly accumulation framing
- narrow asset universe
- leverage sizing logic based on `account / 12`
- examples for Gold, ETH, BTC, and NAS100
- separate treatment for leveraged vs non-leveraged accounts

## What Is Still Unresolved

Before this strategy is treated as locked, these pieces still need explicit research decisions:

1. exact stop model for leveraged backtests
2. exact leverage multipliers we want to test
3. whether `US30` should be treated equally with Gold, Nasdaq, BTC, and ETH
4. whether monthly buys happen on:
   - first trading day
   - monthly open
   - a pullback condition inside the month
5. whether the strategy should ever rotate between assets, or remain one-asset-at-a-time

## Recommended Next Step

The clean research sequence is:

1. run a `pure monthly SIP` baseline on:
   - `XAU_USD`
   - `NAS100_USD`
   - `US30_USD`
   - `BTC_USD`
   - `ETH_USD`
2. run a `leveraged monthly SIP` version using:
   - monthly budget = `account / 12`
   - leverage variants like `1x`, `2x`, `3x`
   - protective correction stops
3. compare:
   - ending balance
   - CAGR
   - max drawdown
   - worst year
   - contribution efficiency

## Bottom Line

Secular Bull SIP is not a signal-board strategy like CWT.

It is better understood as:

- a long-horizon capital-allocation system
- long-only
- monthly
- focused on a very small set of secular winners

That means the first backtest should be simple and faithful before we add any tactical “buy the correction” logic.
