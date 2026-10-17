# 8. Analytical and Desk Study Report

## Comparison of existing approaches

| Approach | Needs labels | Fits delayed labels | Weakness for this problem |
|---|---|---|---|
| Scheduled retraining (fixed calendar, baseline B1 in this project) | No (does not use any signal at all) | Trivially, since it ignores labels entirely | Retrains on a fixed clock regardless of whether anything changed; wastes compute in quiet periods and can miss a sudden shift for up to a full cycle |
| Error-rate drift detectors, e.g. DDM (Gama, Medas, Castillo, Rodrigues, 2004) | Yes, at every step | No: needs the true label immediately to track the online error rate | Cannot run at all until a label exists for each new example, which is exactly what a multi-day label delay rules out |
| Unsupervised two-sample tests, e.g. MMD (Gretton, Borgwardt, Rasch, Schoelkopf, Smola, 2012) or the comparison in Rabanser, Guennemann, Lipton (2019) | No | Yes, since it only needs the incoming features | Detects that the input distribution moved but says nothing about whether that move actually hurt the model, and is structurally blind to drift where the input marginals do not change (telltale's S4) |
| Classifier-based two-sample tests | No | Yes | Same blind spot as other input-only tests: a classifier trained to tell "old" windows from "new" windows cannot see a change confined to the label-generating function alone |
| Confidence / score-based monitoring, e.g. ATC (Garg, Balakrishnan, Lipton, Neyshabur, Sedghi, 2022) | No | Yes | Closest prior art to telltale's score monitor, but evaluated on static image benchmarks, not a streaming setting with a retrain policy or a delayed-label backstop |
| Label-shift estimation, e.g. BBSE (Lipton, Wang, Smola, 2018) | Needs source labels, not target labels | Partially | Assumes a specific shift structure (the label marginal moves, the class-conditional input distribution does not), which does not cover general covariate or concept drift |
| **telltale (this project)** | No for the label-free path; yes for the backstop, but only once labels mature | By design: this is the parameter the whole method is organised around | Structurally blind to pure concept drift on the label-free path alone (by the same logic as the input-only and classifier-based tests above); this is why the backstop exists |

## Reasoning for the proposed design

No single approach in the table solves the actual operating constraint: a fraud classifier needs
monitoring that works before labels exist, but any detector that is blind to concept drift leaves a
real gap unaddressed, and that gap cannot be closed without eventually using real labels. telltale's
design is therefore two channels, not one. The label-free channel (input drift PSI/KS plus score
drift PSI/alert-ratio/entropy, PRD 6.3-6.4) gives speed on the drift type it can see, covariate
drift, which is also the drift type the literature's input-only and confidence-based methods are
built for. The delayed-label backstop (PRD 6.6) is a direct descendant of the classical error-rate
detector idea (DDM), but deliberately only applied once labels mature, since that is the one thing
DDM-style detectors cannot do without labels. Running both channels and letting the faster one win,
with the retrain policy deferring a label-free alarm until enough fresh labels exist (PRD 6.6), is
the combination none of the individual prior approaches attempt.

## Analytical model

Stated in full in `docs/analytical_model.md` (quantities A1 to A5: detection delay, false alarm
rate, exposure, retrain count, compute cost), each derived from the CUSUM mechanism (Page, 1954)
and the method's own structure, with assumptions stated alongside each formula. Section 14.1 of the
report compares these predictions against what the main run measured.
