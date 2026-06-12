# CWT First Signal Only Summary

## Headline
- Starting capital: `$100,000.00`
- Selected signals: `96`
- Suppressed repetitive signals: `74`
- Closed selected signals: `95`
- Open selected signals: `1`
- TP: `44`
- SL: `51`
- Win rate: `46.32%`
- Ending equity: `$105,741.30`
- Net profit: `$5,741.30`

## Assumptions
- Only root signals are considered tradable.
- Same-symbol/timeframe/side follow-up signals are suppressed while the prior selected trade is still open.
- After a TP, same-direction follow-ups inside the repetition window are treated as cluster duplicates rather than new trades.
- After an SL, the next qualifying same-direction signal is allowed so the ladder can progress.

## By Symbol
| Symbol | Signals | TP | SL | Net Risk % |
|---|---:|---:|---:|---:|
| `AUD_USD` | `17` | `8` | `9` | `+3.94%` |
| `EUR_USD` | `9` | `5` | `4` | `+2.19%` |
| `GBP_JPY` | `10` | `6` | `4` | `+1.07%` |
| `NAS100_USD` | `15` | `6` | `9` | `+0.20%` |
| `NZD_USD` | `9` | `2` | `7` | `-1.96%` |
| `SPX500_USD` | `22` | `12` | `10` | `-0.63%` |
| `UK100_GBP` | `7` | `2` | `5` | `+0.59%` |
| `USD_JPY` | `6` | `3` | `3` | `+0.29%` |

## Suppressed Repetition Reasons
| Reason | Count |
|---|---:|
| `same_direction_post_tp_cluster` | `74` |
