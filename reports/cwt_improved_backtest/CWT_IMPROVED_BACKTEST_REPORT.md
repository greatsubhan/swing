# CWT Improved Rules Backtest

## Improved Ruleset Tested

- `Require one-bar follow-through`
- `Skip high-noise sessions`
- `Skip duplicate-cluster trades`
- `Mild stop help`: `+10%` widen plus `0.35 ATR` minimum floor
- Bankroll: `$100,000`
- Ladder: `0.07%, 0.20%, 0.45%, 1.00%`

## Comparison

| Dataset | Baseline Trades | Improved Trades | Trade Delta | Baseline Return | Improved Return | Baseline PF | Improved PF | Baseline Avg R | Improved Avg R | Baseline Max DD | Improved Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `operational_journal_root_only` | `95` | `33` | `-62` | `-9.25%` | `0.31%` | `0.8627` | `0.9799` | `-0.073684` | `-0.007314` | `12.59%` | `0.94%` |
| `since_inception_replay_root_only` | `131` | `50` | `-81` | `-25.72%` | `-3.12%` | `0.6795` | `0.964` | `-0.19084` | `-0.015126` | `26.6%` | `4.77%` |
| `since_inception_replay_raw` | `277` | `50` | `-227` | `-37.93%` | `-3.12%` | `0.9645` | `0.964` | `-0.018051` | `-0.015126` | `38.76%` | `4.77%` |

## Skip Breakdown

### `operational_journal_root_only`

- Baseline trades: `95`
- Improved trades: `33`
- Improved skipped: `61`
- `high_noise_session`: `9`
- `missing_followthrough`: `50`
- `target_already_passed`: `2`

### `since_inception_replay_root_only`

- Baseline trades: `131`
- Improved trades: `50`
- Improved skipped: `81`
- `high_noise_session`: `10`
- `missing_followthrough`: `70`
- `target_already_passed`: `1`

### `since_inception_replay_raw`

- Baseline trades: `277`
- Improved trades: `50`
- Improved skipped: `227`
- `duplicate_cluster`: `146`
- `high_noise_session`: `10`
- `missing_followthrough`: `70`
- `target_already_passed`: `1`

