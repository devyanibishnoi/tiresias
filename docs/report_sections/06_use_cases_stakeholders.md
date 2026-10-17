# 6. Use Case and Stakeholder Definition

## 6.1 Use cases

**UC1: Detect silent degradation while labels are still delayed.** A fraud analytics team runs a
classifier in production. telltale watches the live stream and raises an alarm when the input or
score distributions move persistently away from the reference, without waiting for chargebacks to
confirm anything, giving the team a head start on the days-to-weeks label delay.

**UC2: Reduce unnecessary retraining compared with a fixed calendar.** An ML platform team
currently retrains every model on a fixed schedule (say, monthly) regardless of whether anything
has changed, burning compute and engineering time. telltale only triggers a retrain when there is
actual evidence of drift (label-free alarm, deferred until labels mature) or a confirmed recall drop
(backstop), cutting unnecessary retrains while keeping performance close to the fixed schedule's.

**UC3: Explain which features drove an alarm.** When the input monitor flags a window, it keeps
track of which features had the largest population stability index contribution (PRD Section 6.3),
so an analyst investigating the alarm has a concrete starting point instead of a single opaque
number.

**UC4: Tell real drift apart from regular seasonality.** A naive monitor that just watches for any
distribution shift would fire constantly on predictable patterns, like a weekly cycle in transaction
amounts. Scenario S6 is built specifically to test this: telltale's null calibration is built from
the reference period's own natural variability, including whatever regular seasonality is already
present there, so the same pattern recurring later does not look anomalous.

**UC5: Audit trail of every monitoring decision for model governance.** Every alarm, its reason
(label-free or backstop), the signal values behind it, and every retrain's trigger and timing are
logged per window (PRD Section 6.1 step 8), giving a governance or compliance reviewer a complete,
reconstructable record of why and when the model changed.

## 6.2 Stakeholders

| Stakeholder | What they need | How they use the system |
|---|---|---|
| Fraud analysts | Early warning with enough context to act, without being buried in noise | Receive alarms with the implicated features (UC3); investigate flagged windows; tune their own trust in the system based on its calibrated false-alarm rate (UC4) rather than treating every alarm as equally urgent |
| ML platform / operations engineers | Lower retraining cost, predictable compute budget | Own the retrain pipeline the policy triggers (PRD Section 6.6); use the measured seconds-per-retrain and retrain-count numbers (Section 9, Section 4) to budget compute, compare telltale's retrain count against the fixed-schedule baseline (UC2) |
| Data scientists | Confidence the deployed model is still the right one, without manually re-checking it | Treat a telltale alarm as the trigger to look at the model again instead of relying on a calendar; use the ablation results (input-only vs score-only vs combined) to understand which signal is actually doing the work |
| Risk, compliance, model governance teams | Documented thresholds and a complete audit log of every automated decision | Review the decision log (UC5) for every alarm and retrain, including the calibration method and the tuned parameters logged in `docs/decisions.md`, to confirm the system behaves as documented |
| Business and product owners | Fewer missed frauds, fewer false declines, predictable operating cost | See the gap-closed metric (PRD Section 8) against the fixed schedule and the oracle upper bound, translated into the feasibility sheet's cost comparison (Section 4) |
| Cardholders and merchants | Correct decisions: real fraud caught, legitimate transactions not declined | Not direct users of the system, but the ultimate reason recall at a fixed alert budget (not raw accuracy) is the headline metric: it is a proxy for how many frauds get caught without flooding legitimate customers with false declines |
