telltale was built and evaluated as a full pipeline: a synthetic transaction stream and drift
injector covering eight scenarios (no drift, three severities of sudden covariate drift, gradual,
recurring, pure concept drift, mixed, and benign seasonality), a label vault enforcing a strict
label delay with a tested leakage guard, two label-free monitors (input drift and score drift)
combined through a calibrated CUSUM, a delayed-label backstop, a deferred retrain policy, and eight
compared strategies, all run end to end and aggregated into the statistics reported in Section 13.

What was found: [FILL from results/summary.json and Section 14.2's verdicts: which of H1-H5 held,
with the actual numbers, stated plainly].

What did not work, or did not fully work: the label-free monitor's structural blindness to pure
concept drift (scenario S4) was confirmed exactly as predicted (H4), which is the project's
clearest honest negative result, not a flaw to explain away. [FILL any hypothesis that was only
partly supported or not supported, with the number that shows it, and why].

Limits: results come from a synthetic generator tuned to meet its own acceptance criteria (PRD
Section 5.3), not real transaction data; the one real-data check (Kaggle) is detection-only, since
the dataset has too few frauds and too little natural drift to retrain against safely; evaluation
used 10 seeds rather than the PRD's default of 20, cut for wall-clock feasibility on this machine
(see docs/decisions.md). None of this is hidden: every number in this report traces to
`results/summary.json`, and every cut and deviation is logged in `docs/decisions.md` and
`docs/dev_log.md`.

Future work: real data with natural (not injected) drift, to see whether the synthetic generator's
covariate-drift mechanism (a zero-sum feature shift plus added logit noise, see docs/decisions.md)
actually matches how real fraud drift degrades a deployed model; the interim adaptation ablation
(importance-weighted refitting on old labels while waiting for a full retrain, PRD 6.8), not
reached under this deadline; cost-sensitive alerting, where the alert budget itself adapts to the
estimated cost of a missed fraud versus a false decline rather than staying fixed at 2 percent; and
an adaptive retrain window size, rather than the fixed W=20 windows used throughout this project.
