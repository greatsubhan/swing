# CWT Operational Summary

## Headline Metrics

- Total signals: `114`
- Closed signals: `112`
- Open signals: `2`
- TP hits: `56`
- SL hits: `56`
- Win rate: `50.00%`
- Total realized R: `0.00R`
- Average closed R: `0.00R`
- Average hold: `3.75h`

## Reinforcement Snapshot

- Root detections processed: `185`
- Reinforcement detections processed: `371`
- Average reinforcement strength: `85.45/100`

## Busiest Symbol Buckets

| Symbol | TF | Side | Signals | Closed | Open | TP | SL | Win Rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `AUD_USD` | `5m` | `long` | `24` | `24` | `0` | `11` | `13` | `45.83%` |
| `GBP_JPY` | `15m` | `long` | `21` | `21` | `0` | `17` | `4` | `80.95%` |
| `SPX500_USD` | `5m` | `long` | `18` | `18` | `0` | `8` | `10` | `44.44%` |
| `NAS100_USD` | `5m` | `long` | `15` | `14` | `1` | `7` | `7` | `50.00%` |
| `EUR_USD` | `5m` | `long` | `7` | `7` | `0` | `3` | `4` | `42.86%` |
| `NZD_USD` | `5m` | `long` | `6` | `6` | `0` | `0` | `6` | `0.00%` |
| `USD_JPY` | `5m` | `long` | `6` | `6` | `0` | `3` | `3` | `50.00%` |
| `UK100_GBP` | `5m` | `long` | `5` | `5` | `0` | `2` | `3` | `40.00%` |

## Duplicate-Feeling Clusters

| Symbol | TF | Side | Signals | Same-Hour Bursts | First | Last |
|---|---|---:|---:|---:|---|---|
| `AUD_USD` | `5m` | `long` | `24` | `11` | `2026-04-13T22:35:00+00:00` | `2026-04-16T05:55:00+00:00` |
| `GBP_JPY` | `15m` | `long` | `21` | `9` | `2026-04-13T11:00:00+00:00` | `2026-04-15T05:15:00+00:00` |
| `SPX500_USD` | `5m` | `long` | `18` | `3` | `2026-04-14T22:10:00+00:00` | `2026-04-17T05:45:00+00:00` |
| `NAS100_USD` | `5m` | `long` | `15` | `7` | `2026-04-13T19:20:00+00:00` | `2026-04-16T05:30:00+00:00` |
| `EUR_USD` | `5m` | `long` | `7` | `4` | `2026-04-13T23:05:00+00:00` | `2026-04-14T23:35:00+00:00` |

## Route Health

- Logged route cycles: `142`
- Cycles with dispatch errors: `23`
- Average signals found per cycle: `8.8`
- Average suppressed duplicates per cycle: `4.62`

## Recommendations

- Reinforcement is doing useful work: clustered same-structure alerts are present, especially on the busiest symbols, so keeping one tradable root signal plus reinforcement updates is justified.
- There have been some dispatch-error cycles in the route log. Keep the new watchdog/restart layer in place and continue watching webhook delivery, but the errors are not yet large enough to justify strategy-level changes.
