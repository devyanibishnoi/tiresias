# 1. Introduction

A deployed fraud classifier does not stay accurate on its own. Fraud patterns shift as attackers
change tactics, customer behaviour shifts with the seasons and with the economy, and the model
that was good on launch day quietly gets worse. The awkward part is that nobody finds out quickly.
A transaction is only confirmed as fraud once a customer disputes it or a chargeback lands, and
that can take weeks. So a team runs a model for a long stretch of time with no real way of knowing
whether it is still doing its job, until the complaints start arriving and the damage is already
done.

Two common responses exist and neither is satisfying. The first is to retrain on a fixed calendar,
say every month, whether or not anything has actually changed. This wastes compute during quiet
periods and still reacts too slowly to a sudden shift, because the shift might start the day after
a scheduled retrain and sit unnoticed for weeks. The second is to wait for the labels, meaning wait
for the complaints, which is exactly the slow path the first approach was trying to avoid.

telltale takes a third path. It watches the live stream of transactions and the model's own
predicted scores, both of which are available the instant a transaction happens, no label needed.
From these it builds two kinds of evidence: has the shape of the incoming data moved away from
what the model was trained on, and has the model's behaviour (how often it flags things, how
confident it is) moved in a way that looks like drift rather than normal day-to-day noise. When
that evidence is strong and persists for more than a couple of windows, it raises an alarm. Because
the labels needed to safely retrain are still delayed, the alarm does not trigger an instant
retrain: it marks one as pending and executes it once enough labels from after the alarm have had
time to mature. A second, slower channel acts as a backstop: once labels do arrive, it watches
whether the model's actual recall on matured windows has dropped, and if so, retrains immediately,
since by then there is no more reason to wait.

## 1.1 Domain information

Card and transaction fraud detection is usually framed as a highly imbalanced binary classification
problem: a tiny fraction of transactions (often well under 1 percent in real portfolios) are fraud,
and the cost of missing one is not symmetric with the cost of a false alarm. On top of that
imbalance sits concept drift, a term from the data stream mining literature for any change over
time in the relationship between the inputs and the label. The literature usually separates two
flavours. Covariate drift (also called virtual drift) is where the distribution of the input
features changes but the true mapping from inputs to label stays the same; a model that was
accurate before can still be accurate after, if it generalises to the new region, but in practice
it often does not. Concept drift in the narrow sense (real drift) is where the mapping itself
changes: the same transaction profile that used to be safe now is not, or vice versa, while the
inputs you can observe may look statistically identical to before. This second kind is the harder
one for any monitor that only looks at inputs, because there is nothing in the input distribution
to see.

Fraud detection has an additional complication on top of ordinary concept drift research: label
delay. In most drift-detection papers, the true label of a new example is assumed to arrive almost
immediately (classification is checked against ground truth right away). In fraud, the label is a
confirmed chargeback or a manual investigation result, and that can take days to months. This means
a monitor cannot simply watch accuracy drop in real time, because there is no real-time accuracy to
watch. Anything that wants to react quickly has to work from proxies: how the inputs look, how the
model's own scores behave, how confident it seems. That is the specific gap telltale is built to sit
in.

## 1.2 Software libraries used

| Library | Version (this environment) | Purpose |
|---|---|---|
| numpy | 2.5.4 | Array operations: the synthetic stream, feature generation, vectorised null-calibration bootstrap |
| pandas | 3.0.6 | Per-window result logs, aggregation into summary statistics and report tables |
| scipy | 1.18.1 | KS statistic (`scipy.stats.ks_2samp`), confidence intervals (`scipy.stats.t`, `scipy.stats.sem`) |
| scikit-learn | 1.9.1 | `HistGradientBoostingClassifier` (the deployed fraud model), `average_precision_score` |
| matplotlib | 3.11.2 | All figures (architecture diagram, performance-over-time, ablation bars, scale-up plots) |
| pyyaml | (latest via pip) | Reading `configs/*.yaml` run configurations |
| python-docx | (latest via pip) | Building the Word report from `report/template.docx` |
| pytest | (latest via pip) | The test suite (`tests/`), PRD Section 15.1's quality gates |

Exact installed versions are pinned by `requirements.txt` and recorded at build time; the table
above reflects the environment the project was actually built and run in.

## 1.3 Contributions by team members

[AUTHOR TO FILL]

## 1.4 Challenges faced

Written only from `docs/dev_log.md`, the project's dated log of problems and fixes, as PRD Section
0 rule 8 requires. See that file for the full, dated account; the headline issues were:

- A naive synthetic covariate-drift injector (shift the mean of the features the label depends on,
  in the direction of their own coefficients) made average precision go up after drift instead of
  down, because the shift also raised the ambient fraud rate in the window and average precision is
  sensitive to prevalence. Fixed by making the shift zero-sum against the label's weight vector and
  adding the real performance damage as an explicit noise term on the logit.
- `HistGradientBoostingClassifier`'s `class_weight="balanced"` parameter (or any `sample_weight`
  array at all) cost a fixed 6 to 10 seconds per `.fit()` call on this machine's scikit-learn 1.9.1
  / Python 3.14 build, regardless of data size, against about 0.3 to 2 seconds unweighted. At the
  scale the main experiment needed this made the difference between an infeasible multi-day run and
  a tractable one.
- The null-calibration bootstrap for the drift monitors first resampled individual transaction rows
  from the reference pool, which washed out the shared per-window structure that scenario S6
  (benign weekly seasonality) deliberately has. Its false alarm rate came out around 3x the target
  no matter how the CUSUM was tuned. Fixed by resampling whole reference windows instead of rows,
  which then uncovered a second, subtler bug: resampling only 10 whole windows verbatim caps the
  null distribution at 10 distinct outcomes, understating its true tail and letting a fresh window
  exceed the threshold 60 percent of the time instead of about 1 percent. The final fix resamples
  the window choice and then separately resamples that window's own rows.
- A first end-to-end timing check projected the full main experiment (20 evaluation seeds) at about
  26.6 hours, almost entirely due to the two bugs above plus an unoptimised calibration bootstrap
  loop (originally about 135 seconds per reference rebuild, needed thousands of times). After fixing
  all three and discovering this machine's sandboxed shell only gives genuine parallelism across
  about 2 real cores (not the 12 `os.cpu_count()` reports), the author agreed to cut evaluation
  seeds from 20 to 10, PRD Section 3's own first cut-list item, bringing the run to a tractable
  1.5 to 1.75 hours.

## 1.5 Scientific / Technical Principle Note

**Drift types.** The project distinguishes three structural kinds of change, following the general
split used in the concept-drift literature (see Section 2). Sudden drift is a step change at a
known or unknown point in time. Gradual drift ramps in over a window rather than switching
instantly. Recurring drift turns on, off, and on again, the kind a system might see from a seasonal
attack pattern or a promotional period. telltale's generator implements all three as covariate
drift (scenarios S1, S2, S3), plus a fourth kind that is not about the inputs at all: concept drift
in the narrow sense, where the label-generating relationship itself changes while every input
feature's marginal distribution stays the same (scenario S4).

**Why labels are late.** A transaction's true fraud status is only confirmed when a cardholder
disputes a charge, a chargeback process completes, or an investigator closes a case. PRD Section
5.1 fixes this label delay at D = 7 windows by default (with a sensitivity sweep over 0, 3, 7, 14
windows as a P1 item), representing roughly a week if one window is one day. Any monitoring
approach that needs ground truth to detect degradation is structurally stuck waiting at least D
windows before it can see anything.

**Why label-free signals work, and when they cannot.** The input drift monitor and the score drift
monitor (PRD Section 6.3, 6.4) never touch the label. The input monitor compares the live feature
distribution against a reference using the population stability index (PSI) and the
Kolmogorov-Smirnov statistic; the score monitor does the same for the model's own predicted
probabilities, plus how often it flags transactions (the alert rate) and how uncertain its
predictions look (predictive entropy). All of these are observable instantly, at serving time, no
label needed. This works precisely when drift changes something about the observable inputs or the
model's observable behaviour on them, which is exactly what covariate drift does by definition. It
structurally cannot work when the inputs look identical and only the hidden mapping from inputs to
label has changed (pure concept drift, scenario S4): there is nothing in X or in the model's scores
on X for a label-free monitor to notice, because the model was never told the relationship had
moved.

**The role of the backstop.** This is exactly the gap the delayed-label backstop (PRD Section 6.6)
is there to close. It is slower by construction, since it needs real labels to mature before it can
compute anything, but it is not blind to concept drift the way the label-free monitors are: it
watches the model's actual recall at the alert budget on matured windows, compared against its
calibration-period baseline, and retrains immediately on a sustained drop. The combination is the
project's central claim: label-free signals buy speed on the drift they can see, and the backstop
guarantees nothing silently rots forever, at the cost of being no faster than the label delay
allows.
