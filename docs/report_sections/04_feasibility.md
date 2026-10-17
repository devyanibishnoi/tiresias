# 4. Feasibility Calculation Sheet

| Dimension | Rating | Evidence |
|---|---|---|
| Technical | High | Every component (generator, injector, label vault, monitors, backstop, retrainer, policies) is implemented, unit tested (38 tests, `pytest -q`), and runs end to end; the leakage guard is enforced, not just assumed |
| Data | High for the synthetic study, medium for real transfer | The generator meets its own acceptance criteria (PRD 5.3: stable-period AP in [0.60, 0.85], controlled AP degradation by severity, S4 marginals near-null, S6 seasonality visible but low-impact); the P1 real-data check (Kaggle) is the one place real transaction data enters, and it is detection-only by design (Section 5.4's own limitation) |
| Computational | High at the simulation's scale, needs care at production scale | See the worked cost calculation below; monitor time per window of 2000 transactions is about 5.6 ms (profiling, well under the 100 ms target, PR6), a retrain needing a monitor reference costs about 15.5 seconds, one that does not (B1, B2) costs about 2.8 seconds |
| Operational | Medium | The decision log (every alarm, its reason, the signal values) gives an audit trail a real team could review; what is not tested here is integration with a live scoring pipeline, alerting channels, or human review workflow |
| Economic | High relative to a fixed schedule, conditional on the drift rate assumed | The worked calculation below compares annual retrain cost under a fixed schedule against the framework; the saving scales with how much of the fixed schedule's retraining turns out to be unnecessary, which is scenario-dependent (see the retrain-count results, Section 13) |

## Worked cost calculation

Measured constants (profiling, `telltale.cli profile`, `results/profiling.json`):

- Seconds per retrain needing a monitor reference (M0, M1, M1a, M1b, B3): about 15.5 seconds (6
  model fits: 1 deployed model plus a 5-fold out-of-fold ensemble for the reference, PRD 6.6).
- Seconds per retrain not needing one (B1, B2): about 2.8 seconds (1 model fit only).
- Monitor time per window of 2000 transactions: about 5.6 ms.

Annual retrain cost, one window representing one day (PRD 5.1):

    annual compute seconds = retrains per year x seconds per retrain
                            + 365 x seconds per monitored window (if the strategy monitors)

Fixed schedule (B1, K=20): 365 / 20 is about 18 retrains per year, each about 2.8 seconds (no
monitor reference needed), for about 51 seconds of retrain compute per year, plus zero monitor
compute. The framework's annual retrain count and recall-at-budget, and therefore its own annual
compute and the actual relative saving, come from `results/summary.json` once the main run
completes; the retrain-count side of this comparison is filled in here after Section 13's results
are available (it is PR4/H3: at most 60 percent of B1's retrains for comparable recall).

## Scale to a bank-sized volume

Assumption: a mid-size issuer processing on the order of 10 million transactions per day, against
this simulation's 2000 transactions per window. Monitor time scales roughly linearly with window
size once binning and reference comparisons dominate (profiling: 5.6 ms at 2000 rows, about 313 ms
at 200,000 rows, about 1.5 seconds at 1,000,000 rows), so monitoring 10 million transactions in one
window would be on the order of 15 seconds if run as a single batch window, which is why a real
deployment would shard by time or by a feature-store-backed streaming aggregation rather than
scoring one undivided daily batch; see Section 14.5's scale-up note for the full discussion.
