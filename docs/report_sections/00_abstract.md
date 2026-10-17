Fraud classifiers degrade as fraud patterns shift, but the labels needed to measure that directly
are delayed by days to weeks through disputes and chargebacks. telltale is a label-free drift
monitor for deployed fraud classifiers: it watches the incoming transaction features and the
model's own predicted scores, both available instantly with no label needed, and raises an alarm
when the evidence of drift is strong and persistent (a calibrated CUSUM over population stability
index and score-based signals). Because a safe retrain still needs matured labels, an alarm defers
the retrain until the label delay plus a short maturity wait has passed; a slower, delayed-label
backstop retrains immediately once matured-window recall shows a confirmed drop, catching the one
failure mode label-free signals structurally cannot see: pure concept drift, where the inputs look
unchanged and only the relationship to the label has moved. Across [N] evaluation seeds and eight
synthetic drift scenarios (sudden, gradual, recurring and pure concept drift, plus a benign
seasonality control), the label-free monitor detected covariate drift with a median delay of
[X] windows against the backstop's [Y], used about [Z] percent of a fixed retraining schedule's
retrain count while keeping time-averaged recall within [W] percent (relative) of it, and held a
false alarm rate of [F] per 100 windows on the no-drift and benign-seasonality controls. As
expected, the label-free monitor failed to detect the pure concept drift scenario, confirming its
structural blind spot; the backstop caught it within [B] windows of onset. These results come from
a controlled simulation tuned to its own acceptance criteria, not a claim that the method works
unmodified on a real bank's fraud stream; what does and does not transfer is discussed directly in
the report's final sections.
