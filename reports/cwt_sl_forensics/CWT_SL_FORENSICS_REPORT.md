# CWT SL Forensics Report

## Headline Findings

- Operational summary markdown/json is stale versus the current journal: SL delta +13.
- First-signal-only summary is behind the current journal state: TP delta +1, SL delta +0.
- Total analyzed SL rows: `339`
- Views covered: `operational_journal:raw, operational_journal:root_only, since_inception_replay:raw, since_inception_replay:root_only`

## SL Counts By Source / Lens

| View | Trades | SL Hits |
|---|---:|---:|
| `operational_journal:raw` | `159` | `69` |
| `operational_journal:root_only` | `94` | `51` |
| `since_inception_replay:raw` | `277` | `141` |
| `since_inception_replay:root_only` | `131` | `78` |

## Top Recurring SL Reasons

| Reason | Count |
|---|---:|
| `continuation_failed_cleanly` | `98` |
| `insufficient_reward_after_survival` | `82` |
| `duplicate_cluster_exposure` | `77` |
| `structure_invalidated_before_reversal` | `42` |
| `high_noise_session` | `20` |
| `stop_too_tight` | `14` |
| `entry_too_early` | `6` |

## SL Breakdown By Symbol / TF / Ladder Step

| Source | Lens | Symbol | TF | Ladder Step | SL Hits | Top Reason |
|---|---|---|---|---:|---:|---|
| `since_inception_replay` | `raw` | `NAS100_USD` | `5m` | `3` | `8` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `NZD_USD` | `5m` | `3` | `8` | `continuation_failed_cleanly` |
| `since_inception_replay` | `raw` | `UK100_GBP` | `5m` | `3` | `8` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `USD_JPY` | `5m` | `0` | `8` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `EUR_USD` | `5m` | `0` | `7` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `EUR_USD` | `5m` | `3` | `7` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `SPX500_USD` | `5m` | `0` | `7` | `insufficient_reward_after_survival` |
| `since_inception_replay` | `raw` | `USD_JPY` | `5m` | `1` | `7` | `insufficient_reward_after_survival` |
| `operational_journal` | `raw` | `AUD_USD` | `5m` | `0` | `6` | `duplicate_cluster_exposure` |
| `operational_journal` | `raw` | `AUD_USD` | `5m` | `1` | `6` | `insufficient_reward_after_survival` |
| `since_inception_replay` | `raw` | `AUD_USD` | `5m` | `0` | `6` | `continuation_failed_cleanly` |
| `since_inception_replay` | `root_only` | `AUD_USD` | `5m` | `0` | `5` | `continuation_failed_cleanly` |
| `since_inception_replay` | `raw` | `EUR_USD` | `5m` | `1` | `5` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `NAS100_USD` | `5m` | `0` | `5` | `duplicate_cluster_exposure` |
| `since_inception_replay` | `raw` | `NZD_USD` | `5m` | `0` | `5` | `continuation_failed_cleanly` |
| `since_inception_replay` | `raw` | `NZD_USD` | `5m` | `1` | `5` | `continuation_failed_cleanly` |
| `since_inception_replay` | `root_only` | `NZD_USD` | `5m` | `3` | `5` | `continuation_failed_cleanly` |
| `since_inception_replay` | `raw` | `SPX500_USD` | `5m` | `3` | `5` | `continuation_failed_cleanly` |
| `since_inception_replay` | `raw` | `USD_JPY` | `5m` | `2` | `5` | `insufficient_reward_after_survival` |
| `since_inception_replay` | `root_only` | `USD_JPY` | `5m` | `0` | `5` | `insufficient_reward_after_survival` |

## Saved vs Still Bad

- Saved by `+10%` stop widening and still reaches TP: `20`
- Saved by `0.25 ATR` floor and still reaches TP: `0`
- Still SL after `+30%` widening: `295`
- Still SL after `1-bar` delayed entry: `331`

## Intervention Leaderboard

| View | Variant | Total R Delta | Profit Factor Delta | Trade Delta | Drawdown Delta R |
|---|---|---:|---:|---:|---:|
| `since_inception_replay:root_only` | `followthrough_1bar` | `+27.0000` | `+0.3946` | `-75` | `+0.2138` |
| `since_inception_replay:raw` | `followthrough_1bar` | `+26.0000` | `+0.3914` | `-138` | `+0.3432` |
| `operational_journal:root_only` | `followthrough_1bar` | `+15.0000` | `+0.5686` | `-53` | `+0.1096` |
| `since_inception_replay:root_only` | `fixed_widen_20` | `+13.1667` | `+0.1412` | `+0` | `+0.0737` |
| `since_inception_replay:root_only` | `fixed_widen_30` | `+10.7692` | `+0.1016` | `+0` | `+0.0754` |
| `operational_journal:raw` | `followthrough_1bar` | `+7.0000` | `+0.7327` | `-77` | `+0.1528` |
| `since_inception_replay:raw` | `fixed_widen_20` | `+6.6667` | `+0.0488` | `+0` | `+0.0591` |
| `since_inception_replay:root_only` | `delay_1bar` | `+6.5278` | `+0.0806` | `-1` | `+0.0262` |
| `since_inception_replay:root_only` | `fixed_widen_10` | `+4.7273` | `+0.0428` | `+0` | `+0.0230` |
| `since_inception_replay:raw` | `fixed_widen_30` | `+4.0000` | `+0.0272` | `+0` | `+0.0824` |
| `operational_journal:root_only` | `delay_1bar` | `+2.8818` | `+0.0545` | `-2` | `+0.0122` |
| `operational_journal:root_only` | `fixed_widen_10` | `+2.8175` | `+0.0466` | `-1` | `-0.0025` |
| `operational_journal:raw` | `fixed_widen_10` | `+2.3630` | `+0.0665` | `-1` | `+0.0306` |
| `operational_journal:root_only` | `atr_floor_035` | `+1.6244` | `+0.0294` | `+0` | `+0.0120` |
| `operational_journal:raw` | `atr_floor_035` | `+1.6244` | `+0.0284` | `+0` | `+0.0150` |
| `operational_journal:raw` | `atr_floor_050` | `+1.3864` | `+0.0249` | `+0` | `+0.0134` |

## Small Overshoot Cases That Recovered

| Source | Lens | Symbol | Setup | Overshoot R | MFE After SL R | Recommended Action |
|---|---|---|---|---:|---:|---|
| `since_inception_replay` | `raw` | `EUR_USD` | `cwt-eur_usd-5m-scenario1-long-202604080130` | `0.0044` | `1.1718` | `Require one-bar follow-through` |
| `since_inception_replay` | `raw` | `GBP_JPY` | `cwt-gbp_jpy-15m-scenario1-long-202604081100` | `0.0051` | `1.633` | `Keep baseline` |
| `since_inception_replay` | `root_only` | `GBP_JPY` | `cwt-gbp_jpy-15m-scenario1-long-202604081100` | `0.0051` | `1.633` | `Keep baseline` |
| `operational_journal` | `raw` | `NZD_USD` | `cwt-nzd_usd-5m-scenario1-long-202604150515` | `0.0147` | `1.0475` | `Keep baseline` |
| `operational_journal` | `root_only` | `NZD_USD` | `cwt-nzd_usd-5m-scenario1-long-202604150515` | `0.0147` | `1.0475` | `Keep baseline` |
| `since_inception_replay` | `raw` | `SPX500_USD` | `cwt-spx500_usd-5m-scenario1-long-202604080535` | `0.0153` | `1.5316` | `Require one-bar follow-through` |
| `since_inception_replay` | `root_only` | `SPX500_USD` | `cwt-spx500_usd-5m-scenario1-long-202604080535` | `0.0153` | `1.5316` | `Require one-bar follow-through` |
| `since_inception_replay` | `raw` | `EUR_USD` | `cwt-eur_usd-5m-scenario1-long-202604091320` | `0.0158` | `3.7472` | `Require one-bar follow-through` |
| `since_inception_replay` | `raw` | `NAS100_USD` | `cwt-nas100_usd-5m-scenario1-long-202604100135` | `0.0166` | `1.3467` | `Require one-bar follow-through` |
| `operational_journal` | `raw` | `AUD_USD` | `cwt-aud_usd-5m-scenario1-long-202604142315` | `0.019` | `4.4076` | `Skip high-noise session` |
| `since_inception_replay` | `raw` | `SPX500_USD` | `cwt-spx500_usd-5m-scenario1-long-202604100130` | `0.021` | `2.4931` | `Skip duplicate cluster` |
| `since_inception_replay` | `raw` | `EUR_USD` | `cwt-eur_usd-5m-scenario1-long-202604071820` | `0.0263` | `14.6683` | `Widen stop +10%` |

## Recommendations

- `Require one-bar follow-through`: `203` SL cases
- `Keep baseline`: `68` SL cases
- `Skip duplicate cluster`: `39` SL cases
- `Skip high-noise session`: `13` SL cases
- `Delay entry by 1 bar`: `8` SL cases
- `Widen stop +10%`: `8` SL cases
