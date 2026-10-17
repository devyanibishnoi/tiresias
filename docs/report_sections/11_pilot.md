## Setup

Pilot config (`configs/pilot.yaml`): scenarios S0 and S1 (moderate severity only), 5 seeds (0-4),
strategies B0, B1, M1. Deliberately quick and rough (PRD Section 9 item 1), run in about 193
seconds. Full results in `results/pilot/`.

## Figure and table

See `results/pilot/pilot_performance_over_time.png`: average precision over the stream, meaned
across the 5 pilot seeds, for B0 (never retrain), B1 (fixed schedule), and M1 (full framework), on
S1 moderate, with M1's label-free alarms and retrains marked.

| Strategy | Time-averaged recall at budget (mean, 5 pilot seeds) | Mean retrains |
|---|---|---|
| B0 (never retrain) | 0.488 | 0.0 |
| B1 (fixed schedule, K=20) | 0.533 | 6.0 |
| M1 (full framework) | 0.526 | 1.6 |

## What this suggests

1. The label-free monitor in M1 caught the onset of moderate covariate drift with 0 windows of
   delay on every pilot seed, while the delayed-label backstop needed a median of 8.5 windows
   (close to the analytical prediction of D=7 plus a small accumulation delay), which is the
   early-warning gap this project is built around.
2. M1 reached a time-averaged recall at budget within about 1.3 percent relative of the fixed
   schedule B1 while retraining about 1.6 times on average against B1's fixed 6, a large reduction
   in retrain count for essentially matching performance.
3. This is 5 pilot seeds and one scenario, not the full statistics; it is evidence the pipeline
   behaves as intended end to end, not a result to draw conclusions from (that is the main run's
   job, with 10 evaluation seeds, a paired Wilcoxon test, and confidence intervals).
