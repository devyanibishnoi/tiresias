telltale was built and evaluated as a full pipeline: a synthetic transaction stream and drift
injector covering eight scenarios (no drift, three severities of sudden covariate drift, gradual,
recurring, pure concept drift, mixed, and benign seasonality), a label vault enforcing a strict
label delay with a tested leakage guard, two label-free monitors (input drift and score drift)
combined through a calibrated CUSUM, a delayed-label backstop, a deferred retrain policy, and eight
compared strategies, all run end to end and aggregated into the statistics reported in Section 13.

What was found: four of the five hypotheses held. H1 held clearly: on sudden moderate covariate
drift (S1), the label-free monitor detected with a median delay of 0 windows against the
delayed-label backstop's median of 9, a lead that was statistically significant (paired Wilcoxon,
p = 0.002) and held the same way, with the same direction, across every covariate-drift scenario
tested (S1 at all three severities, S2, S3). H3 held: the full framework (M1) used about 39 percent
of the fixed schedule's mean retrain count while keeping time-averaged recall within about 2
percent (relative) of it, comfortably inside the 60-percent and 3-percent targets. H4 held in the
way it was designed to: the label-free monitor did not detect the true onset of pure concept drift
(S4) in 7 of 10 evaluation seeds, and the 3 seeds where it did eventually alarm did so 18 to 20
windows after onset, well after the backstop had already triggered a retrain; the backstop itself
detected S4 at a median delay of exactly 7 windows (the label delay D itself, no measurable
accumulation delay added), in every one of the 10 evaluation seeds, comfortably inside the D+5
target. H2's ablation showed the combined signal added no detection-delay benefit over either
signal alone on S1 moderate (all three variants detected at a median of 0 windows, the evidence
already saturates the alarm height in the first drifted window), but did inherit the score signal's
higher false alarm rate: input-only held 0.21 false alarms per 100 windows, score-only and combined
both held 0.75.

What did not fully work: H5 (false alarm rate at or below 1 per 100 windows on S0 and S6) held for
the input-only signal (M1a, 0.25 and 0.17 per 100), for the backstop alone (B3, 0.25 and 0.17 per
100), and for the label-free-only strategy with no backstop (M0, 0 per 100 on both), but the full
framework (M1) and the score-only variant (M1b) exceeded the target on S0 (1.08 per 100, against a
ceiling of 1.0). Looking at the per-window evidence around scenario S4 explains part of this: the
backstop's own retrain, triggered while its training window still straddles the concept-drift
boundary, temporarily destabilises the monitor's reference and produces a real (not spurious)
evidence spike afterward, not independent early detection of the original drift (Section 13.3's S4
figure shows this directly). The same mechanism, a retrain happening while its own calibration data
is in flux, plausibly contributes to M1 and M1b's elevated false alarm rate on the no-drift control
too, since both run the backstop and therefore retrain more often than M0. This is reported as a
finding, not adjusted after the fact: the hypotheses and their targets were fixed before the main
run (`docs/first_pass_prediction.md`), and H5 simply did not hold for two of the five label-free
strategies.

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
