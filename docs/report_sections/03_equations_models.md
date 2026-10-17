# 3. Concept Sketches, Equations, and Models

## 3.1 Concept sketches

Three figures (built by `telltale.cli make-figures`, saved under `results/figures/`):

1. **Architecture diagram**: the full pipeline from the stream source through the drift injector,
   deployed model, label vault, monitors, evidence combiner, backstop, and retrain policy, to the
   retrainer and the logger. Mirrors PRD Section 4.1's diagram.
2. **Label-delay timeline**: one drift event (S1 moderate) shown on a single timeline, marking the
   true onset, the label-free alarm, the point the post-alarm labels mature, the retrain, and the
   recovery in measured performance. Makes the gap between "detected" and "acted on" visible.
3. **Drift taxonomy sketch**: sudden, gradual, recurring, and concept drift drawn as four small
   panels of a signal over time, so the difference between "the input moved" (the first three) and
   "the relationship moved while the input looks the same" (the fourth) is visually obvious before
   any equation is introduced.

## 3.2 Equations

**Population stability index (PSI).** For a reference sample and a current sample, both binned
into the same k bins (here k=10, edges taken as quantiles of the reference):

    PSI = sum over bins i of (c_i - r_i) * ln(c_i / r_i)

where r_i and c_i are the reference and current fraction of observations in bin i. PSI is zero when
the two samples are binned identically and grows as the current sample's distribution moves away
from the reference's. telltale computes PSI per feature and aggregates a window's input-drift value
as the mean of the five largest per-feature PSI values (PRD 6.3), so a handful of genuinely shifted
features drive the signal instead of being diluted by sixteen that did not move.

**Kolmogorov-Smirnov (KS) statistic.** The maximum absolute difference between the reference and
current empirical cumulative distribution functions:

    KS = max over x of |F_reference(x) - F_current(x)|

Computed per feature alongside PSI as a second, complementary view of the same question (PRD 6.3);
used for diagnosis (which features moved and by how much) rather than feeding the alarm threshold
directly.

**Predictive entropy.** For a predicted fraud probability p (clipped away from 0 and 1 to avoid a
logarithm of zero):

    H(p) = -p * ln(p) - (1 - p) * ln(1 - p)

A model that has become less certain about its own predictions, on average, shows a rising mean
entropy relative to its reference-period baseline; one of the three raw score-drift statistics
(PRD 6.4), alongside the log-odds PSI and the alert-rate ratio.

**CUSUM recursion.** The evidence combiner's one-sided cumulative sum, updated each window:

    S_t = max(0, S_{t-1} + E_t - k)

where E_t is the window's evidence (already scaled so that 1.0 sits at the edge of what the null
calibration considers normal) and k is a slack constant. An alarm fires the first window S_t
exceeds a height h; after an alarm, S_t resets to 0 and alarms are suppressed for a short cooldown
(PRD 6.5). This is the same recursive idea behind Page's original cumulative sum control chart
(Page, 1954, PRD literature seed list item 10): accumulate small persistent deviations, ignore
isolated noise, alarm once the accumulated evidence crosses a fixed height.

**Average precision (AP).** The area under the precision-recall curve for one window's hidden
labels and predicted scores, computed with scikit-learn's `average_precision_score`. Used instead
of accuracy or ROC-AUC because fraud is rare: AP is sensitive to how well the model ranks the rare
positive class, which is what matters operationally, rather than being dominated by the easy
majority class the way raw accuracy would be.

**Recall at the alert budget.** If the alert budget is b (2 percent by default, matching the base
fraud rate), and a window has n transactions, recall at budget is the share of true frauds among
the top round(b * n) transactions by predicted score. This is the metric that most directly answers
the operational question: given that an analyst team can only review a fixed share of transactions,
how many of the actual frauds get caught.

**Detection delay.** For a true event at window t_onset and the first alarm at window t_alarm after
it, detection delay is t_alarm - t_onset, measured separately for the label-free alarm and the
backstop alarm so the two channels can be compared directly (this is the basis of H1).

## 3.3 Models

**The classifier.** `sklearn.ensemble.HistGradientBoostingClassifier`, scikit-learn's histogram-
based gradient boosting implementation, used unweighted (see Section 1.4's note on the
`class_weight="balanced"` performance issue) with a capped iteration count of 60. The same
configuration is used by every strategy (PRD 6.7): strategies differ only in when they retrain,
never in what gets trained.

**The monitors.** Four components, described in Section 1.5 and Section 3.2's equations: the input
drift monitor (per-feature PSI and KS), the score drift monitor (log-odds PSI, alert-rate ratio,
mean entropy), the calibrator (turns each raw statistic into a common evidence scale via a
bootstrap null), and the evidence combiner (the CUSUM recursion above, run on the maximum of the
input and score evidence for the full framework, or on a single signal for the M1a/M1b ablation).

**The decision rule.** A label-free alarm marks a retrain as pending at alarm time + D + m, never
earlier; if a second alarm fires while one is already pending, the earlier pending retrain is kept
unchanged. A backstop alarm, once labels show a confirmed recall drop, retrains immediately and
takes over any pending label-free retrain (PRD 6.6).

**The analytical model.** Five derived quantities (A1 detection delay, A2 false alarm rate, A3
exposure, A4 retrain count, A5 compute cost), stated in full in `docs/analytical_model.md`, each
with its assumptions. Section 14.1 of the report compares these predictions against what the main
run measured.
