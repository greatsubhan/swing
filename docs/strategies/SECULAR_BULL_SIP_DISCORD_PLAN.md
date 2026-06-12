# Secular Bull SIP Discord Plan

## Decision

Yes, the Secular Bull SIP work is good enough to convert into a **Discord board**.

No, it is **not** ready to be treated like a high-frequency signal bot.

The right product is:

- a **monthly allocation and review board**
- built around a fixed sleeve and fixed profile
- with clear math, size guidance, and payout tracking
- without pretending to be an execution bot

This strategy is slow, capital-allocation driven, and regime-aware. The bot should reflect that.

## What The Research Says

### 1. Pure monthly SIP baseline

From:

- [BASELINE_MONTHLY_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/BASELINE_MONTHLY_SIP.md)
- [CRYPTO_MONTHLY_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/CRYPTO_MONTHLY_SIP.md)

Main read:

- `BTC_USD` and `ETH_USD` had the biggest upside.
- `XAU_USD` was the cleanest high-return, lower-pain asset.
- `NAS100_USD` was solid and balanced.
- `US30_USD` was weaker.
- `LTC_USD` was a reject in the crypto-only pass.

### 2. Leveraged monthly SIP

From:

- [LEVERAGED_MONTHLY_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/LEVERAGED_MONTHLY_SIP.md)

Main read:

- `Gold` was the only clean first-pass leveraged keep.
- `Nasdaq` and `US30` were usable only with caution.
- `BTC` and `ETH` had huge upside but unacceptable leveraged violence for a clean production recommendation.

### 3. Static funded-rule SIP

From:

- [FUNDED_STATIC_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/FUNDED_STATIC_SIP.md)

Main read:

- funded-style floors force much smaller practical size on many assets
- `BTC` still dominated on upside
- `Gold` stayed the cleanest quality asset
- `Silver` was interesting but rougher
- `Nasdaq` and `US30` lost appeal once size was compressed

### 4. Two-year profile and payout study

From:

- [TWO_YEAR_PROFILE_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/TWO_YEAR_PROFILE_SIP.md)
- [SLEEVE_COMPARE_2Y.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/SLEEVE_COMPARE_2Y.md)

Main read:

- the `2-year` lens is more useful than the giant full-sample view
- profit skimming is much more realistic than adding TP logic
- the strongest profile/sleeve combinations were:
  - `FTMO Swing + Full Classic + No Withdrawal`
  - `FTMO Swing + Full Classic + Skim 50%`
- the calmer version was:
  - `The5ers High Stakes + Full Classic` or `Balanced Core`

## Product Recommendation

The SIP strategy should be launched as a **Discord allocation board**, not a normal intraday signal bot.

### Product Type

- cadence: monthly
- output: allocation instructions, not trade-chasing alerts
- account management: left to the follower
- bot responsibility:
  - identify the monthly sleeve action
  - present price references
  - show size math
  - show profile assumptions
  - track monthly outcomes and withdrawn-vault stats

## Recommended First Live Lane

If we launch one SIP lane first, it should be:

- sleeve: `Full Classic`
- assets:
  - `XAU_USD`
  - `XAG_USD`
  - `NAS100_USD`
  - `US30_USD`
  - `BTC_USD`
- profile style: `FTMO Swing` style risk framing
- payout overlay: `Skim 50% of month-end profit above $100k`

Why this lane:

- it is the strongest payout-aware result from the research
- it is more realistic than pure no-withdrawal compounding
- it reduces dependence on `BTC` alone
- it keeps the “classical” macro sleeve idea intact

If we want a calmer secondary lane later:

- sleeve: `Balanced Core`
- profile style: `The5ers High Stakes`

## What The Bot Should Do

### Monthly signal

On the first trading day of the month, the board should post:

- sleeve name
- active assets
- allocation mode
- price reference for each asset
- monthly budget assumption
- example size math
- payout mode
- caution note if current regime is messy

### Monthly review

At month end, the board should post:

- sleeve performance
- per-asset performance
- ending equity estimate
- vault withdrawn estimate
- whether the next month remains active

### Optional quarterly review

Every quarter, the board can post:

- sleeve-level summary
- asset contribution table
- BTC share of sleeve wealth
- drawdown summary

## What The Bot Should Not Do

- no broker execution
- no automatic prop-firm compliance promises
- no lower-timeframe alerts
- no fake precision about live fills
- no TP-based communication that distorts the lecture logic

## Discord Message Design

### Monthly allocation card

Should include:

- `Secular Bull SIP`
- month and year
- sleeve name
- profile assumption
- payout mode
- asset
- price reference
- monthly notional assumption
- example lot size / units
- note that users must size according to their own broker and account rules

### Month-end review card

Should include:

- month closed
- sleeve return
- best asset
- worst asset
- vault added this month
- cumulative vault
- current stance:
  - continue
  - continue with caution
  - research-only warning

## Technical Rollout Plan

### Phase 1. Research freeze

Freeze the current research baseline and use these as the reference set:

- [SECULAR_BULL_SIP_STRATEGY.md](/C:/Users/Seeker/Documents/swing-pr1/docs/SECULAR_BULL_SIP_STRATEGY.md)
- [BASELINE_MONTHLY_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/BASELINE_MONTHLY_SIP.md)
- [LEVERAGED_MONTHLY_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/LEVERAGED_MONTHLY_SIP.md)
- [FUNDED_STATIC_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/FUNDED_STATIC_SIP.md)
- [TWO_YEAR_PROFILE_SIP.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/TWO_YEAR_PROFILE_SIP.md)
- [SLEEVE_COMPARE_2Y.md](/C:/Users/Seeker/Documents/swing-pr1/reports/secular_bull_sip/SLEEVE_COMPARE_2Y.md)

### Phase 2. Add a new platform strategy

Create a new strategy module in the platform, likely:

- `signal_platform/secular_bull_sip_strategy.py`

And a matching package:

- `strategy_five_bot/`

Suggested strategy id:

- `strategy_five`

### Phase 3. Implement a monthly scanner

The SIP bot does not need a traditional scanner.

It needs:

- monthly market data pull
- sleeve composition config
- profile config
- withdrawal overlay config
- message formatter

### Phase 4. Add SIP journaling

Track:

- monthly issued allocations
- month-end sleeve values
- vault withdrawn
- cumulative vault
- per-asset contribution

### Phase 5. Add Discord route

Add a route in:

- [platform.example.json](/C:/Users/Seeker/Documents/swing-pr1/config/platform.example.json)

With a webhook like:

- `DISCORD_WEBHOOK_URL_SIP`

Cadence should be monthly, not every 5 minutes or 4 hours.

## Recommended Initial Config

### Live board name

- `Secular Bull SIP`

### Initial sleeve

- `Full Classic`

### Initial profile assumption

- `FTMO Swing style`

### Initial payout mode

- `Skim 50% of month-end profit above $100k`

### Initial assets

- `XAU_USD`
- `XAG_USD`
- `NAS100_USD`
- `US30_USD`
- `BTC_USD`

## Why This Is Better Than Waiting Forever

- the research is already strong enough to support a slow, honest product
- the bot does not need broker automation to be useful
- a monthly board fits the actual strategy better than trying to force it into a high-frequency shape
- followers can still use the math and the review process even before choosing a specific firm

## Why We Still Should Be Careful

- this is not yet a finalized prop-firm execution system
- profile rules are research approximations, not legal/compliance guarantees
- the bot should be presented as:
  - a structured allocation board
  - a research-backed guidance system
  - not a promise of identical live account outcomes

## Immediate Next Move

Build the first SIP Discord board in this order:

1. `strategy_five` monthly SIP strategy module
2. sleeve config for `Full Classic`
3. `FTMO Swing style` profile assumptions
4. `Skim 50%` overlay support
5. monthly Discord allocation card
6. month-end review card

That is the cleanest path from research to product.
