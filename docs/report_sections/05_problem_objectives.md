# 5. Problem Statement and Objectives

## 5.1 Problem statement

A deployed fraud classifier degrades as fraud patterns and customer behaviour shift, but the true
labels needed to measure that degradation directly (confirmed fraud or not) are delayed, often by
days to weeks, through disputes and chargebacks. Teams are left choosing between retraining on a
fixed calendar, which wastes compute and still misses sudden shifts that happen between scheduled
retrains, or waiting for labelled complaints to arrive, by which point the model has already been
wrong for a long time. There is no standard way to get an early, label-free signal that a model
needs attention while still respecting that a safe retrain needs real, matured labels, not a guess.

## 5.2 Objectives

Each objective is stated as something measurable and is tied to one of the project's five
hypotheses (PRD Section 2.3, repeated here for reference).

1. Detect covariate drift from input features and model scores alone, with no label, substantially
   faster than a backstop that must wait for labels to mature (H1: label-free median detection lead
   time of at least D/2 windows over the label-only backstop, on scenarios S1, S2, S3).
2. Show that combining the input-drift and score-drift signals gives a better detection-delay
   against false-alarm trade-off than either signal alone (H2, the M1a/M1b ablation).
3. Reduce the number of retrains needed relative to a fixed retraining schedule, without giving up
   time-averaged recall (H3: at most 60 percent of the fixed schedule's retrains, time-averaged
   recall within 3 percent relative of it).
4. Characterise honestly where label-free monitoring fails: on pure concept drift, where the input
   distribution does not move (H4, scenario S4), and confirm the delayed-label backstop still
   catches it, just later.
5. Keep false alarms rare enough to be usable in practice, including under benign, non-drift
   seasonal variation that a careless detector could mistake for drift (H5: at most 1 false alarm
   per 100 windows on S0 and S6).
