# Vectorized vs Replay Alignment Notes

This note summarizes the main causes of the original mismatch observed before
the latest validation rerun.

## Primary Drivers Found

- Kill-zone inconsistency:
  `killzone_only: false` parameter sets originally disabled kill-zone tags in
  the strategy config while replay still required kill-zone eligibility for
  entry, which suppressed replay trades in those rows.
- Candidate collapse mismatch:
  replay collapsed overlapping daily candidates before execution, while the
  validation-side vectorized path initially did not.
- Intraday trigger mismatch:
  the original vectorized signal table used simple per-bar boolean masks,
  whereas replay required ordered state progression through watch, VWAP loss,
  retest, and entry conditions.
- Execution mismatch:
  the original vectorized trade model used a simpler exit path and did not
  mirror replay partials, break-even protection, invalidation handling, and
  add behavior closely enough.

## Alignment Changes Applied

- Validation parameter sets now toggle replay kill-zone gating consistently.
- Vectorized validation now uses replay-consistent candidate collapse.
- Vectorized validation signal extraction now derives entry signals from replay
  state transitions.
- Vectorized validation trade outcomes now use the same replay-consistent
  execution proxy used by the replay engine.

## Result

- `performance_matrix.csv` now shows matched vectorized and replay trade counts
  across all rows.
- `vectorized_replay_mismatch_report.csv` now reflects aligned trade counts and
  aligned average-R outcomes for the current validation batch.
