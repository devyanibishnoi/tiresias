# 7. Functional / Performance Requirement Sheet

Targets below are starting points (PRD Section 14.2's seed list) with the reasoning for each.
Whether the main run actually met them is judged in Section 14.3 of the report, from
`results/summary.json`, not here.

## Functional requirements

| ID | Statement | Verification method |
|---|---|---|
| FR1 | Compute input and score drift signals for each window using only that window's features and the model's own scores, never the label | Unit tests (`tests/test_null_calibration.py`) and the leakage guard (`tests/test_label_vault.py`); code review of `telltale/monitors/` confirms no monitor function takes `y` as an argument |
| FR2 | An alarm names the signals and features responsible | `telltale/monitors/input_drift.py`'s `InputDriftResult.top_features`, logged per alarm window |
| FR3 | Defer the retrain until enough post-alarm labels have matured | `tests/test_policy_timing.py`: a label-free alarm at window t schedules the retrain no earlier than t + D + m |
| FR4 | Log every decision with its reason | `telltale/simulator.py`'s per-window record (`retrain_executed`, `retrain_source`, alarm flags, evidence values), aggregated by `telltale/experiments.py` into `results/retrains.csv` and `results/per_window_log.csv.gz` |
| FR5 | Run every baseline and strategy under the same rules (same model class, retrain window, label vault, cooldown) | `telltale/policies.py`'s `StrategyConfig` and `telltale/simulator.py`'s single shared `simulate()` function; strategies differ only in their flags |
| FR6 | Reproduce every result from one command and a seed | `tests/test_generator.py::test_reproducibility_same_seed_same_stream`; `python -m telltale.cli run --config configs/main.yaml` reruns the full grid deterministically from the seeds in the config |

## Performance requirements

| ID | Statement | Target | Reasoning | Verification method |
|---|---|---|---|---|
| PR1 | Median label-free detection delay, moderate sudden covariate drift | At most 3 windows | Chosen so the label-free path meaningfully beats the D=7-window label delay the backstop is stuck with | `results/summary.json`'s `detection.S1\|moderate\|M1.label_free_delay_median` |
| PR2 | Detection rate within 10 windows, moderate and severe covariate events | At least 90 percent | A monitor that only sometimes catches a clear covariate shift is not trustworthy enough to replace a fixed schedule | Fraction of (scenario, seed) runs where the first label-free alarm after onset is within 10 windows |
| PR3 | False alarm rate, S0 and S6 | At most 1 per 100 windows | PRD 6.5's calibration target; see `results/tuning.json` for the tuned CUSUM parameters and their measured rate on the tuning seeds | `results/summary.json`'s `false_alarms` block, evaluation seeds |
| PR4 | Retrain count relative to the fixed schedule, averaged over scenarios | At most 60 percent | Direct restatement of H3: the point of label-free monitoring is fewer unnecessary retrains, not just different ones | Mean of `retrain_count_mean` across scenarios for M1 divided by the same for B1 |
| PR5 | Time-averaged recall at budget relative to the fixed schedule | Within 3 percent relative | Fewer retrains should not come at a real performance cost | Same ratio as PR4, computed on `time_averaged_recall_mean` instead of retrain count |
| PR6 | Monitor time per window of 2000 transactions | At most 100 ms | A monitor that is too slow to run at serving time is not practical regardless of its accuracy | `telltale.cli profile`'s per-window monitor timing |
| PR7 | Backstop detection within D + 5 windows of onset, scenario S4 | Required | S4 is the scenario where label-free monitoring is expected to fail by design (H4); the backstop is what makes the overall framework safe on exactly this failure mode | `results/summary.json`'s `detection.S4\|moderate\|<strategy>.backstop_delay_median` |
