# Launch Prep

This file prepares the project for the next stage: running as a live signal bot and posting alerts into Discord.

## Recommended Launch Order

1. Live scan only
2. Discord delivery
3. Paper-trade observation period
4. Optional broker execution later

This is the safest order because it lets the signal engine prove itself in real time before money movement is automated.

## Recommended First Production Scope

Timeframe:

- `4h`

Watchlist:

- `WTICO_USD`
- `BCO_USD`
- `XAG_USD`
- `UK100_GBP`
- `NAS100_USD`
- `XAU_USD`

Mode:

- alert only
- no order placement
- one scan on each new `4h` candle close

## Discord Delivery Plan

The simplest first version is a Discord webhook sender.

Recommended flow:

1. scan OANDA watchlist
2. generate structured signals
3. deduplicate signals by `setup_id`
4. post formatted alert to a Discord webhook
5. persist sent alert ids locally so the same signal is not re-posted

Why webhook first:

- cheaper
- simpler
- easier to operate than a full Discord bot app
- enough for a private signal channel

Suggested alert payload fields:

- symbol
- side
- timeframe
- entry
- stop
- target
- risk-reward
- quality score
- quality grade
- trend maturity
- timestamp

The new platform layer already supports:

- strategy registration
- one webhook route per strategy
- persisted sent-alert dedupe
- config-driven execution

See [docs/MULTI_STRATEGY_PLATFORM.md](/C:/Users/Seeker/Documents/swing-pr1/docs/MULTI_STRATEGY_PLATFORM.md).

## Run Modes

### Laptop mode

Best for:

- development
- manual supervision
- paper testing

Pros:

- no extra hosting bill
- fastest setup
- easiest debugging

Cons:

- not reliable for 24/7 uptime
- depends on power, sleep settings, and internet stability

### VPS mode

Best for:

- continuous scanning
- production-style signal delivery
- reduced risk of missed alerts

Pros:

- stable uptime
- easier scheduling
- easier to keep isolated from daily laptop use

Cons:

- extra monthly cost
- needs deployment and monitoring setup

## Recommended Operational Setup

For the next step, the best balance is:

- develop locally on the laptop
- deploy the live signal scheduler to a small VPS once Discord is wired

Suggested VPS shape:

- 2 vCPU
- 2 GB to 4 GB RAM
- persistent internet access
- Python 3.11+ or newer
- cron or task scheduler equivalent

This bot is lightweight enough that it does not need a large server.

## Scheduling Guidance

Recommended scan cadence:

- run shortly after each `4h` candle closes

Practical example:

- every 4 hours with a small delay to allow the candle to finalize and the API data to settle

## Config Prep

Use [.env.example](/C:/Users/Seeker/Documents/swing-pr1/.env.example) as the starting point for the next stage.

Important future environment variables:

- `OANDA_API_TOKEN`
- `OANDA_ENV`
- `DISCORD_WEBHOOK_URL`
- `BOT_WATCHLIST`
- `BOT_GRANULARITY`
- `BOT_HIGHER_TIMEFRAME`

## Before Going Live

Checklist:

- confirm the OANDA token is rotated and stored securely
- run the scan manually for several days
- verify no duplicate alerts are emitted
- verify every Discord alert matches the stored signal fields
- store alert history so reconnects do not repost old setups
- log failures from OANDA or Discord calls
- decide whether to keep `XAU_USD` in the production watchlist or treat it as optional

## Not Yet Recommended

Not recommended yet:

- direct broker execution
- auto-sizing positions from broker balance
- multi-timeframe global filters as defaults
- broad forex expansion

The current best path is a disciplined signal service, not a fully automated execution stack.
