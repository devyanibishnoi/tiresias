# Pilot note (S1 moderate, S0, 5 seeds, strategies B0/B1/M1)

Quick and rough on purpose (PRD Section 9 item 1). Feeds report Section 11.

1. The label-free monitor in M1 caught the onset of moderate covariate drift with 0 windows of
   delay on every pilot seed, while the delayed-label backstop needed a median of 8.5 windows
   (close to the analytical prediction of D=7 plus a small accumulation delay), which is the
   early-warning gap this project is built around.
2. M1 reached a time-averaged recall at budget (0.526) within about 1.3 percent relative of the
   fixed schedule B1 (0.533) while retraining about 1.6 times on average against B1's fixed 6, a
   large reduction in retrain count for essentially matching performance.
3. This is 5 pilot seeds and one scenario, not the full statistics; it is evidence the pipeline
   behaves as intended end to end, not a result to draw conclusions from (that is the main run's
   job, with 10 evaluation seeds, a paired Wilcoxon test, and confidence intervals).
