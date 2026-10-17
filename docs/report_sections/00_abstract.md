Fraud classifiers degrade as fraud patterns shift, but the labels needed to measure that directly
are delayed by days to weeks through disputes and chargebacks. telltale is a label-free drift
monitor for deployed fraud classifiers: it watches the incoming transaction features and the
model's own predicted scores, both available instantly with no label needed, and raises an alarm
when the evidence of drift is strong and persistent (a calibrated CUSUM over population stability
index and score-based signals). Because a safe retrain still needs matured labels, an alarm defers
the retrain until the label delay plus a short maturity wait has passed; a slower, delayed-label
backstop retrains immediately once matured-window recall shows a confirmed drop, catching the one
failure mode label-free signals structurally cannot see: pure concept drift, where the inputs look
unchanged and only the relationship to the label has moved. Across 10 evaluation seeds and eight
synthetic drift scenarios (sudden, gradual, recurring and pure concept drift, plus a benign
seasonality control), the label-free monitor detected moderate sudden covariate drift with a median
delay of 0 windows against the delayed-label backstop's 9, a statistically significant lead
(paired Wilcoxon, p less than 0.01) that held across every covariate-drift scenario tested. The full
framework used about 39 percent of a fixed retraining schedule's retrain count while keeping
time-averaged recall within about 2 percent (relative) of it. As expected, the label-free monitor
structurally failed to detect the pure concept drift scenario at its true onset; the backstop
caught it at a median of 7 windows after onset, comfortably inside its target, in every evaluation
seed. One hypothesis did not hold as cleanly: the false alarm target (at most 1 per 100 windows)
was met by the input-only signal and by the backstop alone, but the combined and score-only
variants of the full framework exceeded it slightly on the no-drift control, a genuine ablation
finding discussed directly in Section 14 rather than hidden. These results come from a controlled
simulation tuned to its own acceptance criteria, not a claim that the method works unmodified on a
real bank's fraud stream; what does and does not transfer is discussed directly in the report's
final sections.
