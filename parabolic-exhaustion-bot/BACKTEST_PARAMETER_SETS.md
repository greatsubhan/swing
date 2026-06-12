# Backtest Parameter Sets

| parameter_set_id | market_family | extension_mode | extension_value | volume_rank_min | slope_score_min | target_r | partial_take_r | stop_buffer_points | killzone_only | notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| idx_ps07_baseline_on | indices | atr_multiple | 3.00 | 0.85 | 60.0 | 2.00 | 1.50 | 0.25 | True | Baseline around ps07 for indices with kill-zone gating enabled. |
| idx_ps07_baseline_off | indices | atr_multiple | 3.00 | 0.85 | 60.0 | 2.00 | 1.50 | 0.25 | False | Baseline around ps07 for indices without kill-zone gating. |
| idx_looser_ext_on | indices | atr_multiple | 2.50 | 0.80 | 55.0 | 2.00 | 1.50 | 0.25 | True | Looser extension and slope filter for indices with kill-zone gating. |
| idx_looser_ext_off | indices | atr_multiple | 2.50 | 0.80 | 55.0 | 2.00 | 1.50 | 0.25 | False | Looser extension and slope filter for indices without kill-zone gating. |
| idx_tighter_stop_on | indices | atr_multiple | 3.00 | 0.85 | 60.0 | 1.50 | 1.25 | 0.15 | True | Tighter stop and smaller target for indices with kill-zone gating. |
| idx_tighter_stop_off | indices | atr_multiple | 3.00 | 0.85 | 60.0 | 1.50 | 1.25 | 0.15 | False | Tighter stop and smaller target for indices without kill-zone gating. |
| idx_wider_stop_on | indices | atr_multiple | 3.25 | 0.85 | 60.0 | 2.00 | 1.50 | 0.35 | True | Wider stop variant for indices with kill-zone gating. |
| idx_wider_stop_off | indices | atr_multiple | 3.25 | 0.85 | 60.0 | 2.00 | 1.50 | 0.35 | False | Wider stop variant for indices without kill-zone gating. |
| met_balanced_on | metals | atr_multiple | 2.00 | 0.70 | 50.0 | 1.00 | 1.00 | 0.00 | True | Balanced metals filter with kill-zone gating enabled. |
| met_balanced_off | metals | atr_multiple | 2.00 | 0.70 | 50.0 | 1.00 | 1.00 | 0.00 | False | Balanced metals filter without kill-zone gating. |
| met_smaller_target_on | metals | atr_multiple | 2.25 | 0.70 | 50.0 | 0.75 | 0.75 | 0.00 | True | Smaller target profile for metals with kill-zone gating. |
| met_smaller_target_off | metals | atr_multiple | 2.25 | 0.70 | 50.0 | 0.75 | 0.75 | 0.00 | False | Smaller target profile for metals without kill-zone gating. |
| met_buffered_on | metals | atr_multiple | 2.50 | 0.75 | 55.0 | 1.00 | 0.75 | 0.10 | True | Buffered stop profile for metals with kill-zone gating. |
| met_buffered_off | metals | atr_multiple | 2.50 | 0.75 | 55.0 | 1.00 | 0.75 | 0.10 | False | Buffered stop profile for metals without kill-zone gating. |
