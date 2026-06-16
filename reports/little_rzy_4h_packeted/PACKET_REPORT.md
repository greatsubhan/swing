# Little RZY 4H Packeted Research

Date: `2026-04-08`

## Goal

Increase the number of `4h` Little RZY signals without touching the original production logic, and only keep changes that improve trade count while preserving strong quality.

## Universe

Research basket: `26` assets

- energy: `WTICO_USD`, `BCO_USD`
- metals: `XAG_USD`, `XAU_USD`
- indices: `UK100_GBP`, `NAS100_USD`, `US30_USD`, `SPX500_USD`, `FR40_EUR`, `JP225_USD`, `ESPIX_EUR`
- forex: `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `AUD_CHF`, `USD_CAD`, `USD_CHF`, `NZD_USD`, `EUR_GBP`, `EUR_JPY`, `GBP_JPY`
- crypto: `BTC_USD`, `ETH_USD`, `LTC_USD`, `BCH_USD`

Segments:

- `2023 H1`
- `2023 H2`
- `2024 H1`
- `2024 H2`
- `2025 H1`
- `2025 H2`

Mode:

- original `4h` Little RZY logic
- zero costs
- no portfolio constraints
- market profiles on

## Packet Ladder

| Variant | Change |
|---|---|
| `base` | original `4h` logic |
| `packet_a` | `min_impulse_atr = 1.5` |
| `packet_b` | `packet_a` + `max_breakout_bars_after_pullback = 5` |
| `packet_c` | `packet_b` + `pullback_min_retrace = 0.20`, `pullback_max_retrace = 0.70` |
| `packet_d` | `packet_c` + `max_setup_age_bars = 12` |

## Variant Summary

Practical read:

- `packet_a` did nothing
- `packet_b` is the best quality/quantity compromise
- `packet_c` and `packet_d` create more trades, but the extra looseness degrades average quality too much

All active symbols:

| Variant | Active Symbols | Total Trades | Mean Win Rate | Mean Avg R | Mean PF | Mean Max DD R | Total Net PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `base` | `25` | `1834` | `27.20%` | `0.157` | `21.17` | `-2.75` | `385.12` |
| `packet_a` | `25` | `1834` | `27.20%` | `0.157` | `21.17` | `-2.75` | `385.12` |
| `packet_b` | `25` | `1978` | `27.89%` | `0.128` | `21.16` | `-3.07` | `88.03` |
| `packet_c` | `25` | `2224` | `28.37%` | `0.129` | `21.14` | `-3.34` | `-22.70` |
| `packet_d` | `25` | `2261` | `28.39%` | `0.120` | `21.14` | `-3.40` | `-567.25` |

Decision-grade assets only: `trades >= 20`

| Variant | Decision Assets | Total Trades | Mean Win Rate | Mean Avg R | Mean PF | Median PF | Mean Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| `base` | `18` | `1787` | `32.46%` | `0.003` | `1.321` | `1.162` | `-3.68` |
| `packet_a` | `18` | `1787` | `32.46%` | `0.003` | `1.321` | `1.162` | `-3.68` |
| `packet_b` | `19` | `1927` | `32.57%` | `0.084` | `1.390` | `1.196` | `-3.86` |
| `packet_c` | `20` | `2192` | `31.64%` | `0.049` | `1.296` | `1.113` | `-4.09` |
| `packet_d` | `20` | `2227` | `31.67%` | `0.044` | `1.295` | `1.152` | `-4.15` |

## Compare To Base

| Variant | Trade Delta | Signal Delta | Mean Win Rate Delta | Mean Avg R Delta | Mean PF Delta | Mean DD Delta | Assets With More Trades And Better PF | Assets With More Trades And PF Not Worse |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `packet_a` | `0` | `0` | `0.000` | `0.000` | `0.000` | `0.000` | `0` | `0` |
| `packet_b` | `144` | `144` | `0.007` | `-0.027` | `-0.010` | `-0.307` | `10` | `17` |
| `packet_c` | `390` | `390` | `0.011` | `-0.027` | `-0.030` | `-0.560` | `11` | `15` |
| `packet_d` | `427` | `427` | `0.011` | `-0.035` | `-0.031` | `-0.624` | `11` | `15` |

## Why Each Packet Behaved The Way It Did

### `packet_a`

Verdict: `discard`

- lowering `min_impulse_atr` from `1.8` to `1.5` changed nothing
- conclusion:
  - the scarcity problem was not coming from impulse size
  - any setup that already survived the other gates was already strong enough on impulse

### `packet_b`

Verdict: `keep for research`

- extending `max_breakout_bars_after_pullback` from `3` to `5` added `144` trades
- it improved the decision-grade mean PF from `1.321` to `1.390`
- it increased the number of decision-grade assets from `18` to `19`
- this is the best small-packet improvement

Interpretation:

- the original breakout timing window is slightly too tight
- some otherwise-valid `4h` continuations are simply triggering a bar or two later than the current code allows

### `packet_c`

Verdict: `discard`

- widening the retrace band added a lot of trades, but it started admitting weaker pullbacks
- total trades jumped nicely, but median PF fell and drawdown worsened

Interpretation:

- this packet improves quantity more than quality
- it starts to admit lower-grade setups rather than just “missed good ones”

### `packet_d`

Verdict: `discard`

- extending setup age on top of packet C pushed trade count a little higher again
- but it hurt total net PnL badly and further weakened average quality

Interpretation:

- older setups are usually stale setups here
- the strategy works better when the continuation is still fresh

## Practical Winners

These are the best practical `4h` names from the packeted run.

Base version winners:

| Symbol | Trades | Win Rate | Avg R | PF | Max DD R |
|---|---:|---:|---:|---:|---:|
| `EUR_USD` | `104` | `48.22%` | `0.335` | `4.42` | `-2.86` |
| `XAG_USD` | `107` | `39.02%` | `0.364` | `2.37` | `-2.77` |
| `WTICO_USD` | `123` | `41.99%` | `0.336` | `2.17` | `-3.66` |
| `BCO_USD` | `107` | `37.89%` | `0.167` | `1.51` | `-3.33` |

Packet B winners:

| Symbol | Trades | Win Rate | Avg R | PF | Max DD R |
|---|---:|---:|---:|---:|---:|
| `UK100_GBP` | `28` | `33.93%` | `1.359` | `4.72` | `-2.11` |
| `XAG_USD` | `111` | `39.65%` | `0.375` | `2.29` | `-2.77` |
| `WTICO_USD` | `127` | `43.01%` | `0.325` | `2.11` | `-3.81` |
| `EUR_USD` | `114` | `42.05%` | `0.188` | `1.81` | `-3.76` |
| `GBP_USD` | `101` | `32.18%` | `0.136` | `1.76` | `-3.92` |
| `XAU_USD` | `63` | `33.02%` | `0.256` | `1.50` | `-2.77` |

Packet C and D additions that looked interesting but not strong enough to justify the wider looseness:

- `EUR_JPY`
- `AUD_USD`

## Important Negative Read

The widened bucket also made something very clear:

- crypto is not naturally fitting this `4h` Little RZY structure right now
  - `BTC_USD` produced `0` trades in every packet
  - `ETH_USD` and `LTC_USD` were consistently poor
- several indices still remain structurally weak under this model
  - `SPX500_USD`
  - `US30_USD`
- several forex names stay unconvincing even after loosening
  - `USD_CAD`
  - `USD_CHF`
  - `EUR_GBP`

So the right way to get more signals is not “force more signals from everything.”
It is:

1. widen the asset bucket
2. keep the original baseline where it is already strong
3. use `packet_b` selectively as the research-friendly loosened variant

## Final Recommendation

### Keep production baseline unchanged

Do not touch the original live `4h` Little RZY logic.

### Keep for research

Use `packet_b` as the main research candidate:

- `min_impulse_atr = 1.5`
- `max_breakout_bars_after_pullback = 5`

### Discard

- `packet_a`
- `packet_c`
- `packet_d`

### Best next live-bucket expansion candidates

If the goal is simply more high-quality `4h` opportunities, the best additions from this research are:

- `EUR_USD`
- `GBP_USD`
- `XAG_USD`
- `XAU_USD`
- `WTICO_USD`
- `UK100_GBP`

### Leave out for now

- `BTC_USD`
- `ETH_USD`
- `LTC_USD`
- `SPX500_USD`
- `US30_USD`
- `USD_CAD`
- `USD_CHF`
- `EUR_GBP`

## Files

- [fetch_status.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/fetch_status.csv)
- [variant_segment_rows.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/variant_segment_rows.csv)
- [variant_asset_summary.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/variant_asset_summary.csv)
- [variant_overall_summary.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/variant_overall_summary.csv)
- [variant_comparison_vs_base.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/variant_comparison_vs_base.csv)
- [best_variant_by_symbol.csv](/C:/Users/Seeker/Documents/swing-pr1/reports/little_rzy_4h_packeted/best_variant_by_symbol.csv)
