# PRD and Build Spec: telltale

Label-Free Drift Detection and Selective Retraining Framework for Deployed Fraud Classifiers Under Delayed Ground Truth

This file is the single source of truth for building the project from an empty folder to a finished repo and a finished report. Read all of it before writing anything.

---

## 0. How to work (instructions for Claude Code)

1. Read this entire file first. Then read the two Word files provided by the author (the evaluation criteria and the report template). They should be in `docs/inputs/`. If they are sitting in the repo root, move them there.
2. Work through the phases in Section 12 in order. Commit at the end of every phase with a clear message. Create a git tag called `frozen-config` right before the main experiment runs (Section 12, Phase 5).
3. The deadline is tonight. Everything is tagged P0 (must have), P1 (should have), P2 (only if time is left). Finish all P0 work before touching any P1 work. If time is running short, use the cut list in Section 3.
4. Never invent a number, a result, a citation or a quote. Every number in the report must come from a file produced by the code in this repo. Every reference must be verified to exist (Section 14.4).
5. Do not write literal code into any document, report body or checklist unless this file says a short snippet is wanted (Section 13 allows a few short snippets in report section 13). Documents describe things in words, tables and figures.
6. Do not use em dashes anywhere, in any file, comment, commit message or report text. Use commas, colons, parentheses or full stops instead. Run a search for the em dash character before every commit and before the final report build.
7. Report prose must read like a student who understood the material wrote it. Explain the intuition before the equation, use plain words, vary sentence length, and avoid filler phrases such as "in today's fast-paced world", "delve", "leverage", "robust and scalable" unless backed by a number.
8. Keep a running file `docs/dev_log.md`. Whenever something goes wrong or a decision is made (a bug, a leakage found and fixed, a threshold that did not calibrate, a design change), add a dated entry with what happened and what was done. The "Challenges Faced" section of the report must be written only from this log.
9. If you are blocked on something only the author can provide (the Kaggle file, an API token, a decision), stop that item, note it in `docs/dev_log.md`, continue with other work, and tell the author clearly at the end of the phase.

---

## 1. Project identity

| Field | Value |
|---|---|
| Course | BCSE306L Artificial Intelligence, School of Computer Science and Engineering, VIT Vellore |
| Supervisor | Dr. Ramesh Babu Vemuluri, Associate Professor (already printed on the template cover) |
| Title (16 words) | Label-Free Drift Detection and Selective Retraining Framework for Deployed Fraud Classifiers Under Delayed Ground Truth |
| Repo / package name | telltale |
| Authors on the cover | Devyani Bishnoi (24BCI0167), Anshika Agarwal (24BCE0989), Hridya Sharma (24BAI0182) |
| Report date on the cover | October 17, 2026 |
| Deliverables | 1) Git repo, 2) Word report built from the provided template, plus a PDF copy, 3) result files and figures, 4) README |

Marks: Row 1 (4 marks) concept and paper work, Row 2 (4 marks) requirements and early evidence, Row 3 (2 marks) simulation and validation. Most marks sit in the written concept and the analysis, so the report quality matters as much as the code.

---

## 2. Problem and hypotheses

### 2.1 Problem in plain words

A fraud classifier is deployed and the world keeps changing. Fraud patterns shift, customer behaviour shifts, and the model quietly gets worse. The true labels (confirmed fraud or not) arrive late, often weeks later through disputes and chargebacks, so by the time accuracy visibly drops, the damage has been done for a long time. Teams either retrain on a fixed calendar, which wastes compute and still misses sudden shifts, or they wait until complaints arrive.

telltale watches the model using only signals available instantly (the incoming transaction features and the model's own scores), raises an early warning when the evidence is strong and persistent, and triggers retraining only when needed. Because labels are delayed, it schedules the full retrain for the moment enough fresh labels have matured. A slower backstop that uses delayed labels catches the kind of drift that label-free signals cannot see.

### 2.2 Important honest limits (must be stated in the report)

1. A label-free alarm cannot make labels arrive sooner. So its benefit is early warning, fewer unnecessary retrains and a clearer picture of what changed, not instant recovery.
2. Label-free signals are blind to pure concept drift, where the relationship between inputs and fraud changes while the inputs themselves look the same. This is why the backstop exists, and one scenario (S4) exists specifically to show this failure.
3. Results come from a controlled simulation. The report must say clearly what transfers to real systems and what does not.

### 2.3 Hypotheses (decide pass or fail from the data, never adjust them after seeing results)

| ID | Hypothesis | How judged |
|---|---|---|
| H1 | On covariate drift scenarios (S1, S2, S3), the label-free monitor alarms at least D/2 windows earlier (median) than the label-only backstop | Early-warning lead time, paired Wilcoxon over seeds |
| H2 | The combined signal (input drift plus score shift) has a better detection delay versus false alarm trade-off than either signal alone | Ablation, Section 9 |
| H3 | The full framework uses at most 60 percent of the retrains of the fixed schedule (K=20) while keeping time-averaged recall within 3 percent (relative) of it | Cost and performance tables |
| H4 | On the pure concept drift scenario S4, the label-free signals fail to alarm (expected negative result), and the backstop alarms within D plus 5 windows | Detection rate in S4 for each component |
| H5 | On the benign seasonality scenario S6 and the no-drift control S0, the false alarm rate stays at or below 1 per 100 windows | False alarm table |

---

## 3. Scope, priorities and cut list

### P0 (must have, in this order)

1. Synthetic stream generator with a drift injector and the scenarios S0, S1 (three severities), S2, S3, S4, S5, S6.
2. Simulator with label delay and a leakage guard.
3. The base model, the label-free monitors, the backstop, the decision rule and the retrain policy.
4. Baselines B0 (never retrain), B1 (fixed schedule), B2 (oracle), B3 (label-only monitor).
5. Metrics, 20 evaluation seeds (10 if time is short), summary tables and figures.
6. Ablation: input-only, score-only, combined, with and without backstop.
7. First-pass prediction document, committed before the main run.
8. Profiling of the monitor and of retraining (for the component sheet, the feasibility sheet and the scale-up note).
9. The Word report built from the template, a PDF copy, README, unit tests.

### P1 (should have)

1. Semi-synthetic real-data check on the Kaggle credit card fraud dataset (detection only, see 5.4).
2. A second model type (logistic regression) to show the framework is not tied to one model.
3. Sensitivity sweeps over label delay D, schedule K and maturity m.
4. Interim adaptation by importance weighting (6.8), as an ablation.

### P2 (only if time remains)

1. Scenario S7: fraud prevalence shift (attack wave).
2. Excel version of the feasibility sheet.
3. A small plotted dashboard notebook.

### Cut list if running late (cut in this order)

Reduce seeds to 10, drop the sensitivity sweeps, drop the second model, drop the real-data check, drop interim adaptation, drop S5. Never cut the first-pass prediction, the ablation of Section 9 or the report.

---

## 4. Architecture

### 4.1 Diagram

```
                         SIMULATION (hidden ground truth lives only here)
 +----------------+      +-------------------+      +--------------------+
 | Stream source  | ---> | Drift injector    | ---> | Window t           |
 | synthetic or   |      | scenario S0..S7   |      | features X_t       |
 | real pool      |      | known change pts  |      | labels y_t (hidden)|
 +----------------+      +-------------------+      +----------+---------+
                                                               |
                  +--------------------------------------------+
                  |                                            |
                  v                                            v
        +-------------------+                       +--------------------+
        | Deployed model    |                       | Label vault        |
        | scores window t   |                       | releases y_(t-D)   |
        +---------+---------+                       | only (delay D)     |
                  | scores p_t                      +---------+----------+
                  |                                           |
   +--------------+---------------+                           |
   |                              |                           |
   v                              v                           v
+-----------------+     +------------------+     +-----------------------+
| Input drift     |     | Score and        |     | Delayed-label backstop|
| monitor         |     | confidence       |     | performance on matured|
| PSI and KS per  |     | monitor          |     | windows, CUSUM on drop|
| feature         |     | PSI, alert rate, |     +-----------+-----------+
+--------+--------+     | entropy          |                 |
         |              +---------+--------+                 |
         +----------+-------------+                          |
                    v                                        |
          +---------------------+                            |
          | Evidence combiner   |                            |
          | normalised by null  |                            |
          | thresholds, CUSUM   |                            |
          +----------+----------+                            |
                     |  label-free alarm                     | backstop alarm
                     v                                       v
              +-----------------------------------------------------+
              | Retrain policy                                      |
              | alarm now, retrain when post-alarm labels mature    |
              | (alarm time + D + m), or immediately on backstop    |
              | optional interim adaptation (P1)                    |
              +--------------------------+--------------------------+
                                         |
                                         v
                     +-----------------------------------------+
                     | Retrainer: refit on latest W matured    |
                     | windows, rebuild reference and null     |
                     | thresholds using out-of-fold scores     |
                     +--------------------+--------------------+
                                          |
                                          +--> new deployed model

 Side outputs: decision log (every alarm, reason, signal values), per-window
 true performance (evaluation only, never visible to the policy), timing log.
```

The author wants a clean version of this diagram in the report (matplotlib or a drawing library), and a second figure showing a timeline of one drift event that makes label delay visible (onset, label-free alarm, label maturity, retrain, recovery).

### 4.2 Components

| Component | Responsibility | Notes |
|---|---|---|
| Stream source | Produce window t with N transactions | Synthetic generator (primary), real pool (P1) |
| Drift injector | Apply a scenario with known change points | Writes ground truth events to a separate file |
| Label vault | Release the labels of window t-D only at time t | Any earlier access must raise an error. This is a tested guarantee |
| Deployed model | Score each window | HistGradientBoosting classifier from scikit-learn (primary) |
| Input drift monitor | Per-feature PSI and KS against the reference | Aggregate by mean of the top 5 PSI values |
| Score monitor | PSI on log-odds scores, alert rate ratio, mean predictive entropy | Reference scores must be out-of-fold, never in-sample |
| Calibrator | Turn raw statistics into evidence on a common scale | Null distribution from resampled reference windows |
| Evidence combiner | Merge input and score evidence, run CUSUM | Persistence is required before alarm |
| Backstop | Watch matured-window performance | Alarms on a sustained drop |
| Retrain policy | Decide when to retrain | See 6.6 |
| Retrainer | Refit and rebuild references | Sliding window of the latest W matured windows |
| Logger | Per-window records | One tidy table per run |

---

## 5. Data and drift scenarios

### 5.1 Stream layout (defaults, adjustable only during tuning and logged in `docs/decisions.md`)

| Parameter | Default |
|---|---|
| Windows in a stream (T) | 150 (one window is treated as one day) |
| Transactions per window (N) | 2000 |
| Features (d) | 20: 14 continuous, 2 skewed positive (amount-like), 2 cyclic (hour of day as sine and cosine), 2 categorical-like encoded as integers |
| Base fraud rate | 2 percent (document that real card fraud is far lower, and that 2 percent is chosen so every window has enough positives for stable metrics) |
| Training windows | 0 to 19 |
| Reference and calibration windows | 20 to 29 (no drift, used for thresholds, never for training) |
| Evaluation windows | 30 to 149 |
| Label delay D | 7 windows (sensitivity: 0, 3, 7, 14) |
| Retrain window W | 20 most recent matured windows |
| Maturity wait m | 3 windows |
| Fixed schedule K | 20 windows (sensitivity: 10, 40) |
| Tuning seeds | 100 to 104 (used only for calibration and parameter choices) |
| Evaluation seeds | 0 to 19 (never used for tuning) |

### 5.2 Scenarios

| ID | Name | What changes | Timing |
|---|---|---|---|
| S0 | No drift control | Nothing | Whole stream. Measures false alarms |
| S1 | Sudden covariate drift | Marginal distribution of 4 features shifts (mean shift in standard deviations: mild 0.5, moderate 1.0, severe 2.0) | Onset at window 60 |
| S2 | Gradual covariate drift | Same shift grows linearly | Starts at 60, full strength at 90 |
| S3 | Recurring covariate drift | Shift switches on and off | On 50 to 69, off 70 to 109, on 110 to 129 |
| S4 | Pure concept drift | The fraud relationship changes (different features become informative) while every feature marginal stays the same | Onset at window 60 |
| S5 | Mixed drift | Covariate shift and concept change together | Onset at window 60 |
| S6 | Benign seasonality | Weekly cycle (period 7 windows) in amounts and volumes that does not hurt the model | Whole stream. Tests that seasonality is not mistaken for drift |
| S7 (P2) | Prevalence shift | Fraud rate doubles for a while (attack wave) | Windows 60 to 80 |

### 5.3 Generator acceptance criteria (tests must check these, using the tuning seeds)

1. In the stable period the base model reaches average precision between 0.60 and 0.85. If the task is trivially easy or impossible, redesign the generator.
2. Severe S1 drift lowers the model's average precision by at least 25 percent (relative). Mild S1 drift lowers it by about 5 to 10 percent. Moderate falls between.
3. S4 leaves every feature marginal statistically unchanged (population stability index per feature stays at null level, two-sample tests do not reject beyond the chance rate) but lowers average precision by at least 25 percent.
4. S6 changes feature marginals visibly and periodically but leaves average precision within 5 percent (relative) of the stable value.
5. Ground truth event times are written out for every scenario and seed so detection delay can be computed exactly.
6. Same seed and same config always produce the identical stream.

### 5.4 Real data check (P1, detection only)

Dataset: Credit Card Fraud Detection, Machine Learning Group, Universite Libre de Bruxelles (Kaggle, `mlg-ulb/creditcardfraud`). It has 284,807 transactions over two days, 492 frauds, 28 anonymised PCA features plus Time and Amount. Do not commit it (it is large). The author must download it to `data/raw/creditcard.csv`. If the file is missing, skip this item and log it.

Because the data covers only two days and has very few frauds, build a semi-synthetic stream: train the model on the first half in time, then draw windows from the second half and inject the same kinds of covariate drift as in S1 (shifts on selected features, scaling of Amount). Use this for detection only: detection delay and false alarms of the label-free monitor. Do not run retraining on it, because resampling a small pool leaks identical rows between training and test windows. State this limitation in the report.

---

## 6. Method specification

### 6.1 Windows and time

At each window t, in this exact order: (1) the stream produces X_t and the hidden y_t, (2) the currently deployed model scores X_t, (3) true performance on window t is recorded for evaluation only, (4) the label vault releases the labels of window t-D, (5) monitors compute their signals from X_t and the scores only, (6) the policy decides, (7) any retrain that is due is executed using only matured windows, (8) everything is logged.

### 6.2 Reference and null calibration

The reference is the features and out-of-fold scores of the calibration windows (windows 20 to 29 at the start, and rebuilt after every retrain). For each signal, estimate its null distribution by repeatedly drawing windows of size N from the reference and computing the signal (at least 1000 draws). The raw threshold for a signal is its 99th percentile under the null. Evidence for a signal is its value divided by its threshold, so that 1.0 means "at the edge of normal" on a common scale. After a retrain, rebuild the reference and the null.

### 6.3 Input drift signal

For each feature, compute PSI against the reference using 10 bins whose edges are reference quantiles (with small smoothing to avoid empty bins), and the KS statistic. The window's input drift value is the mean of the five largest PSI values. Also store which features drove the alarm, because the decision log must explain the alarm (this supports the diagnosis use case).

### 6.4 Score and confidence signals

Computed from the model's predicted fraud probability: (a) PSI of the log-odds score distribution against the reference, (b) the ratio of the observed alert rate (share of transactions above the operating threshold) to the reference alert rate, (c) mean predictive entropy relative to the reference. The window's score drift value is the maximum of the three evidence values.

### 6.5 Evidence combiner and decision rule

Per window, evidence E_t is the larger of the input evidence and the score evidence (the ablation also tests each alone). Run a one-sided CUSUM on E_t: add the excess of E_t over a slack value, never let the sum fall below zero, and raise a label-free alarm when the sum passes a height h. The slack and h are chosen on the tuning seeds so that the false alarm rate on S0 and S6 is at most 1 per 100 windows. Log the chosen values and how they were chosen. After an alarm, reset the CUSUM and ignore new alarms for 3 windows (cooldown).

### 6.6 Delayed-label backstop and retrain policy

Backstop: when the labels of window t-D mature, compute the model's recall at the alert budget (Section 8) on that window and convert it to a z-score against the calibration windows. Run a one-sided CUSUM on sustained drops. A backstop alarm means labels showing real post-drift behaviour already exist, so retrain immediately.

Label-free alarm: do not retrain at once, because the freshest labels are still pre-drift. Mark a retrain as pending and execute it at alarm time plus D plus m windows, so that at least m post-alarm windows have matured. If the backstop fires first, it takes over. If a second label-free alarm happens while one is pending, keep the earlier pending retrain.

Retrain: refit on the W most recent matured windows. Rebuild the reference using out-of-fold scores (blocked by window, 5 folds), never in-sample scores, because in-sample scores are overconfident and would trigger false alarms right after the retrain. Rebuild the null thresholds.

### 6.7 Model

Primary model: scikit-learn HistGradientBoostingClassifier with fixed settings, same for every strategy. Handle class imbalance in one documented way and use it everywhere. P1: also run with logistic regression to show the framework does not depend on one model.

### 6.8 Interim adaptation (P1 ablation)

When a label-free alarm fires, immediately refit using the old matured labels but with importance weights, estimated by training a classifier to tell the reference windows from the recent unlabeled windows (the density ratio idea from covariate shift adaptation). Deploy this interim model until the full retrain happens. Treat it as an ablation (M1 with and without it). If it does not help, report that honestly.

---

## 7. Strategies compared

| ID | Strategy | Trigger | Notes |
|---|---|---|---|
| B0 | Never retrain | none | Lower bound |
| B1 | Fixed schedule | Every K windows | Main comparison for cost. Sensitivity over K |
| B2 | Oracle trigger | Knows the true change points, retrains at event time plus D plus m | Upper bound for timing |
| B3 | Label-only monitor | Backstop only | Shows what is possible without label-free signals |
| M0 | Label-free only | Label-free alarm, deferred retrain, no backstop | Ablation |
| M1 | Full framework | Label-free alarm plus backstop | Main proposed method |
| M1a, M1b | Input-only and score-only variants of M1 | | Ablation for H2 |
| M1+IW | M1 with interim adaptation | | P1 |

All strategies use the same model class, the same retrain window W, the same label vault and the same cooldown. They differ only in when they retrain.

---

## 8. Metrics and statistics

Fraud is rare, so plain accuracy is meaningless here. Never report accuracy as a main metric.

| Metric | Definition |
|---|---|
| Average precision (AP) per window | Area under the precision recall curve on window t, computed with the hidden labels (evaluation only) |
| Recall at alert budget | Share of frauds caught when the top 2 percent of transactions by score are flagged in each window (the budget equals the base fraud rate) |
| Time-averaged recall at budget | Mean of the above over evaluation windows |
| Gap closed | (method minus B0) divided by (B2 minus B0), on time-averaged recall at budget |
| Detection delay | Windows from the true event onset to the first alarm after it (per event, per alarm type) |
| Detection rate | Share of events detected within 10 windows |
| False alarm rate | Alarms per 100 windows in segments with no active drift (S0, S6 and the pre-onset period of the other scenarios) |
| Early-warning lead time | Backstop alarm window minus label-free alarm window, per event |
| Exposure | Windows between event onset and deployment of a corrected model |
| Retrain count | Number of retrains executed over the stream |
| Compute cost | Retrain count times measured seconds per retrain, plus monitoring seconds |

Statistics: report mean with a 95 percent confidence interval over seeds (t interval or bootstrap, say which). For headline comparisons between strategies use a paired Wilcoxon signed-rank test over seeds and report the p value and an effect size. Tuning seeds and evaluation seeds must never overlap. Do not drop or re-run seeds because they look bad.

---

## 9. Experiment plan

1. Pilot (feeds report section 11): scenario S1 moderate and S0, 5 seeds, strategies B0, B1, M1. Quick and rough on purpose. Save the output as "early simulation".
2. Main (feeds sections 13 and 14): all P0 scenarios, S1 at all three severities, 20 seeds, all strategies of Section 7 (except P1 ones).
3. Ablation: M0, M1a, M1b, M1, plus M1 without backstop, on S1, S2, S3, S4, S5, S0, S6.
4. Sensitivity (P1): label delay D in 0, 3, 7, 14; schedule K in 10, 20, 40; maturity m in 1, 3, 5, on S1 moderate.
5. Failure analysis: dedicate a figure and a paragraph to S4 showing the label-free signals staying flat while performance falls, and the backstop catching it late.
6. Real data check (P1) as in 5.4.
7. Profiling: seconds per monitor call and per retrain at several window sizes (1,000 up to 1,000,000 transactions per window, features fixed), memory use, and throughput in transactions per second.

Save per-window logs for every run in compact files, a `results/summary.json` with every number the report cites, and CSV tables.

---

## 10. Analytical model and the first-pass prediction protocol

The rubric asks for a first-pass performance prediction (before simulating) and a validation of the analytical model (after). Do this honestly and in this order.

### 10.1 Analytical model (write in `docs/analytical_model.md`, derive and state assumptions)

| ID | Quantity | Idea |
|---|---|---|
| A1 | Detection delay of the CUSUM monitor | If the evidence rises by an average amount mu above the slack after onset, the expected delay is about the CUSUM height divided by mu, plus one window of granularity. For gradual drift derive the corresponding ramp version. Estimate mu from the tuning seeds only |
| A2 | False alarm rate | About 100 divided by the in-control average run length per 100 windows, with the run length estimated by simulating the null on the reference |
| A3 | Exposure | Label-free path: detection delay plus D plus m. Label-only path: D plus the number of matured windows the backstop needs. Oracle: D plus m. Fixed schedule: wait until the next scheduled point, on average K divided by 2 |
| A4 | Retrain count | Fixed: horizon divided by K. Framework: number of true events plus false alarm rate times horizon |
| A5 | Compute | Retrain count times measured seconds per retrain, plus windows times measured monitor seconds |

### 10.2 First-pass prediction document (write in `docs/first_pass_prediction.md`)

After the tuning seeds are done and before the pilot and main runs, write down at least ten numeric predictions with ranges and the reasoning for each, for example expected median detection delay for moderate sudden drift, expected false alarm rate on S0, expected retrain counts for B1 and M1, expected lead time versus the backstop, and an explicit prediction that label-free detection fails on S4. Commit this file. The commit time must be earlier than the first run of the main config. Section 14 of the report compares predicted ranges with observed values in one table, says which predictions held, and explains the misses. Do not edit the prediction file after the main run.

---

## 11. Repo layout and interfaces

```
telltale/
  PRD.md
  CLAUDE.md                short pointer to PRD.md and the working rules
  README.md                what it is, quick start, results figure, architecture figure
  requirements.txt
  .gitignore               must ignore .venv, data/raw, large outputs
  configs/                 pilot, main, tuning settings (one file each)
  telltale/
    data/                  synthetic generator, drift injector, real pool stream
    monitors/              input drift, score drift, calibration, combiner, backstop
    models.py              model construction and the retrainer
    policies.py            all strategies of Section 7
    simulator.py           the window loop and the label vault
    metrics.py             all metrics of Section 8
    experiments.py         runs, aggregation, statistics
    profiling.py           timing and scale-up measurements
    cli.py                 command line entry points
  tests/                   see Section 15
  docs/
    inputs/                the two Word files from the author
    decisions.md           design decisions and parameter choices with reasons
    dev_log.md             dated problems and fixes (source for Challenges Faced)
    analytical_model.md
    first_pass_prediction.md
    literature.md          verified literature log
  data/
    sim_samples/           small compressed representative streams, one per scenario
    raw/                   not committed
  results/                 per-window logs, summary.json, tables, figures
  report/
    template.docx          copy of the author's template
    build_report.py        fills the template from results
    out/                   final docx and pdf
```

### 11.1 Commands the finished repo must support

The author will run these, so they must work exactly as written, from the repo root, on a fresh clone.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m telltale.cli generate-samples
python -m telltale.cli tune
python -m telltale.cli run --config configs/pilot.yaml
python -m telltale.cli run --config configs/main.yaml
python -m telltale.cli profile
python -m telltale.cli make-figures
python -m telltale.cli real-check
python report/build_report.py
```

On Windows the activation line is `.venv\Scripts\activate`. The README must say so. The environment needs Python 3.10 or newer. Packages to start with: numpy, pandas, scipy, scikit-learn, matplotlib, pyyaml, python-docx, pytest, and a plotting or drawing helper if needed.

---

## 12. Phased build plan

Times are rough guides for wall-clock work, not promises.

### Phase 0: scaffold (about 10 min)

Create the layout of Section 11, a virtual environment, `requirements.txt`, `.gitignore`, `CLAUDE.md`, a first README stub, and the first commit. Move the two Word files into `docs/inputs/` and copy the template to `report/template.docx`. Create the GitHub repo and push if the GitHub command line tool is available and the author is logged in (`gh repo create telltale --private --source=. --push`); otherwise tell the author the two commands to add a remote and push. Start `docs/decisions.md` and `docs/dev_log.md`.

Done when: the folder matches Section 11, `pytest -q` runs (even with zero tests), first commit exists.

### Phase 1: data and drift (about 40 min)

Build the synthetic generator, the drift injector for S0 to S6, and the ground truth event files. Write the tests for 5.3. Iterate on the generator until the acceptance criteria pass on the tuning seeds. Log what you changed in `docs/dev_log.md`.

Done when: all generator tests pass and a figure of feature marginals before and after drift looks sensible.

### Phase 2: simulator, model, monitors, policies (about 60 min)

Build the label vault and the window loop, the model and retrainer, the input and score monitors, the calibrator, the combiner, the backstop, and all strategies. Write the leakage test (any early label access fails the test) and a unit test that the PSI of identical samples is near zero and grows with shift.

Done when: one full stream runs end to end for every strategy and the leakage test passes.

### Phase 3: tuning and the prediction (about 30 min)

Choose slack, height and any other free parameter using the tuning seeds only, aiming at the false alarm target of 6.5. Record the choices and why. Write `docs/analytical_model.md` and `docs/first_pass_prediction.md`. Commit. Do not look at evaluation seeds yet.

Done when: the prediction file is committed and the configs are final.

### Phase 4: pilot (about 15 min)

Run the pilot config. Save outputs, a simple figure (performance over time with alarm and retrain marks) and a short factual note. This becomes report section 11. If the pilot shows a bug, fix it, log it, and rerun. Do not change tuned parameters because the pilot "looks off" without logging a reason.

### Phase 5: main experiment (run time depends on the machine)

Create the git tag `frozen-config`, then run the main config, the ablations and, if time permits, the sensitivity sweeps. Run long jobs in the background and write report sections 1 to 9 and 12 while they run (Phase 7 text work). Save `results/summary.json`.

Done when: summary tables, per-window logs and `summary.json` exist for all P0 scenarios and strategies.

### Phase 6: profiling and analysis (about 20 min)

Run profiling. Produce all figures of 13.3 and all tables. Fill the prediction versus observed table. Judge H1 to H5 as supported, partly supported or not supported, using only the data. Run the P1 real-data check if the file exists.

### Phase 7: report (about 75 min)

Build the report as described in Section 13. Draft the theory sections early, in parallel with Phase 5 if possible. Build with `report/build_report.py`, export to PDF, inspect every page as an image, and fix layout issues. Verify there is no em dash anywhere and that every number comes from `summary.json`.

### Phase 8: polish (about 15 min)

Final README with the architecture figure, a results figure, the quick start commands and an honest limitations paragraph. Run the full test suite. Final commit. Tell the author what to open, what to review, and what is still theirs to do (Section 13.4).

---

## 13. Report specification

### 13.1 General rules

Build the report by opening the author's template with python-docx and filling it, so the cover page, logo, styles, headings and table of contents stay exactly as the professor provided them. Do not recreate the document from scratch. On the cover: replace the title placeholder with the project title, fill the three names and registration numbers from Section 1 in the order given there, and set the date to October 17, 2026. Fix the obvious typos in the template headings (for example "Priniciple", "Objecives", "ad Models") and the duplicated "3.2" (the second one should be 3.3), and mention this in the final message to the author. Keep the 16 sections in the template order.

The rubric lists four items in the third row that the template has no section for: Defined Performance Metrics List, Representative Data Simulation Files, Application Feasibility Validation Report and Initial Scale-Up Consideration Note. Add them as subsections inside report sections 13 and 14, exactly as mapped in the table of Section 13.2 of this file (metrics list and data files go in report section 13, application feasibility validation and scale-up note go in report section 14). Do not add new top-level sections.

Figures: every figure and table gets a number, a caption and a sentence in the text that refers to it. Use readable fonts, a consistent colour scheme and labelled axes with units.

Equations: render them cleanly (Word equation objects if feasible, otherwise high-resolution images), numbered, and explained in words right after.

Tone: see rule 7 in Section 0. Write in plain academic English, mostly "we" for what was done. Do not claim anything the data does not show.

### 13.2 Section by section

| # | Template section | Content | Source |
|---|---|---|---|
| Cover | Title page | As above | Section 1 |
| TOC | Table of contents | Keep as is, fix the numbering after the typo fixes | Template |
| Abstract | One paragraph | Problem, method, scenarios, headline numbers, the honest limit. Write last | summary.json |
| 1 | Introduction | General introduction. 1.1 Domain information (fraud detection, concept drift, delayed labels). 1.2 Software libraries used, with versions and purpose in a table. 1.3 Contributions by team members, leave the placeholder text "[AUTHOR TO FILL]" exactly, never invent contributions. 1.4 Challenges faced, only from `docs/dev_log.md`. 1.5 Scientific and technical principle note: drift types, why labels are late, why label-free signals work and when they cannot, the role of the backstop | dev_log, literature |
| 2 | Literature and Reference Log | A table of 12 to 15 verified sources: citation, problem, method, finding relevant to us, limitation, and how it shaped a design choice. Then a short review paragraph grouped by theme. End the section with the gap this project fills | `docs/literature.md` |
| 3 | Concept Sketches, Equations, Models | 3.1 architecture figure, the label-delay timeline figure, a drift types figure. 3.2 Equations: PSI, KS statistic, predictive entropy, the CUSUM recursion, average precision, recall at budget, detection delay, importance weight (if P1 was done). 3.3 Models: the classifier, the monitors, the decision rule, the analytical model A1 to A5 | PRD, analytical_model.md |
| 4 | Feasibility Calculation Sheet | Technical, data, computational, operational and economic feasibility, each with a rating and the evidence. Include a worked cost calculation: annual retrains under a fixed schedule versus the framework, using the measured seconds per retrain and the measured retrain counts. Also scale the compute to a bank-sized volume (state the assumption) | profiling, summary.json |
| 5 | Problem Statement and Objectives | 5.1 Problem statement. 5.2 Objectives, numbered, measurable, tied to hypotheses H1 to H5 | Section 2 |
| 6 | Use Case and Stakeholder Definition | 6.1 Use cases (Section 14.1). 6.2 Stakeholders table with what each needs and how each would use the system | 14.1 |
| 7 | Functional / Performance Requirement Sheet | Requirement table with ID, statement, target, verification method. Seeds in 14.2. Mark each as met, partly met or not met in report section 14 | 14.2 |
| 8 | Analytical and Desk Study Report | Comparison table of existing approaches (scheduled retraining, error-rate drift detectors, unsupervised two-sample tests, classifier-based tests, confidence and score based monitoring, label-shift estimation), whether each needs labels, whether it fits delayed labels, its weakness. Then the reasoning for choosing the proposed design, and the analytical model with its assumptions | literature |
| 9 | Component Identification and Characterization Sheet | Table of every component: purpose, library or class, key parameters, measured runtime, measured memory, alternatives considered | profiling |
| 10 | First-Pass Performance Prediction Document | The predictions of 10.2 with ranges and reasoning, stated as made before the main run, with the commit date | first_pass_prediction.md |
| 11 | Early Simulation Output (Feasibility Evidence) | The pilot: setup, one or two figures, a table, three honest sentences on what it suggests | pilot results |
| 12 | Initial Qualitative Risk List | Table of at least 12 risks (seed list in 14.3) with likelihood, impact, mitigation and, where applicable, the evidence from the experiments | 14.3, results |
| 13 | Lab Test / Simulation Report for Critical Functions | 13.1 Experimental setup and the defined performance metrics list (all metrics of Section 8, as a table). 13.2 Scenario results with the figures of 13.3. 13.3 Ablation, failure analysis (S4), sensitivity, false alarms. 13.4 Representative data simulation files: describe the files in `data/sim_samples/` and the logs in `results/`, with a table of file names, contents and sizes. 13.5 Short code snippets (at most four, each under 25 lines: the PSI computation, the CUSUM update, the leakage guard, the retrain policy decision) and console output blocks. Leave two clearly marked placeholders "[AUTHOR TO INSERT TERMINAL SCREENSHOT]" for the author to add real screenshots | results |
| 14 | Analytical Model Validation Document | 14.1 Predicted versus observed table and error measures. 14.2 Which hypotheses H1 to H5 held. 14.3 Requirement check against section 7. 14.4 Application feasibility validation report: does the evidence support using this in a real fraud pipeline, and under which conditions. 14.5 Initial scale-up consideration note: measured throughput, extrapolation, what changes at millions of transactions per day (streaming windows, feature stores, approximate quantiles, retrain scheduling, monitoring many models) | results, profiling |
| 15 | Conclusion | What was built, what was found, what did not work, limits, future work (real data with natural drift, interim adaptation, cost-sensitive alerting, adaptive window size) | all |
| Refs | References | Verified entries only, consistent style (IEEE or APA, pick one), every entry cited somewhere in the text | literature.md |

### 13.3 Figure list (minimum)

1. Architecture diagram. 2. Label-delay timeline of one drift event. 3. Drift taxonomy sketch (sudden, gradual, recurring, concept). 4. Feature marginals before and after drift (and S4 showing unchanged marginals). 5. Performance over time for all strategies on S1 moderate, with alarm and retrain marks. 6. Detection delay versus severity. 7. Retrain count versus time-averaged recall (cost versus performance). 8. Ablation bars (H2). 9. False alarm rates on S0 and S6. 10. S4 failure figure. 11. Sensitivity to label delay (P1). 12. Scale-up: runtime versus window size.

### 13.4 What stays with the author (do not fill)

1. Section 1.3 Contributions by Team Members, including any terminal screenshots to paste in section 13.
2. Final proofreading of the abstract and conclusion in the author's own words.
3. Deciding whether the repo goes public after submission.

---

## 14. Seed content (verify and expand, never copy blindly)

### 14.1 Use cases and stakeholders

Use cases: UC1 detect silent degradation of a fraud model while labels are still delayed. UC2 reduce unnecessary retraining compared with a fixed calendar. UC3 explain which features drove an alarm so analysts can investigate. UC4 tell real drift apart from regular seasonality. UC5 audit trail of every monitoring decision for model governance.

Stakeholders: fraud analysts (need early warnings and explanations, suffer from alert fatigue), machine learning platform and operations engineers (own pipelines and retraining cost), data scientists (own the model), risk, compliance and model governance teams (need audit logs and documented thresholds), business and product owners (care about fraud losses and customer friction), cardholders and merchants (hurt by missed fraud and by wrongly declined payments). Describe how each uses the system, not only what they want.

### 14.2 Requirements seed (targets are starting points and must be justified in the report)

Functional: FR1 compute input and score signals for each window without labels. FR2 raise an alarm that names the signals and features responsible. FR3 defer the retrain until enough post-alarm labels have matured. FR4 log every decision with its reason. FR5 run the baselines under the same rules. FR6 reproduce every result from one command and a seed.

Performance: PR1 median detection delay of at most 3 windows for moderate sudden covariate drift. PR2 detection rate of at least 90 percent within 10 windows for moderate and severe covariate events. PR3 false alarms at most 1 per 100 windows on S0 and S6. PR4 retrains at most 60 percent of the fixed schedule on average over scenarios. PR5 time-averaged recall at budget within 3 percent (relative) of the fixed schedule. PR6 monitor time at most 100 ms per window of 2000 transactions on a laptop. PR7 the backstop detects S4 within D plus 5 windows.

### 14.3 Risk list seed (extend with likelihood, impact, mitigation)

1. Label-free signals cannot see pure concept drift. 2. Seasonality mistaken for drift. 3. Thresholds calibrated on a short reference window are noisy. 4. Retraining on contaminated or adversarially shaped data. 5. Feedback loop: model decisions change which cases get labelled. 6. Gap between the simulation and real fraud data. 7. Label delay that varies from case to case rather than being fixed. 8. Alert fatigue from false alarms. 9. PSI is sensitive to binning and sample size. 10. High dimensional drift hidden by averaging over features. 11. Overfitting thresholds to the simulation. 12. Information leakage inside the simulation. 13. Retrain after the alarm uses too few post-drift labels. 14. Anonymised features in public data limit explanations. 15. Compute cost grows with the number of monitored models. Also record the project's own delivery risks (deadline, single developer).

### 14.4 Literature seed list (verify every item exists with web search or the publisher page before use)

If no web access is available, mark every entry UNVERIFIED in `docs/literature.md`, list them for the author, and keep them out of the final reference list. Only summarise what you actually read in the abstract or paper. If an item cannot be verified, drop it. Do not add page numbers or DOIs unless confirmed.

1. Gama, Zliobaite, Bifet, Pechenizkiy, Bouchachia. A survey on concept drift adaptation. ACM Computing Surveys, 2014.
2. Lu, Liu, Dong, Gu, Gama, Zhang. Learning under concept drift: a review. IEEE Transactions on Knowledge and Data Engineering, 2019.
3. Webb, Hyde, Cao, Nguyen, Petitjean. Characterizing concept drift. Data Mining and Knowledge Discovery, 2016.
4. Dal Pozzolo, Caelen, Le Borgne, Waterschoot, Bontempi. Learned lessons in credit card fraud detection from a practitioner perspective. Expert Systems with Applications, 2014.
5. Dal Pozzolo, Boracchi, Caelen, Alippi, Bontempi. Credit card fraud detection and concept-drift adaptation with delayed supervised information. IJCNN, 2015.
6. Dal Pozzolo, Boracchi, Caelen, Alippi, Bontempi. Credit card fraud detection: a realistic modeling and a novel learning strategy. IEEE Transactions on Neural Networks and Learning Systems, 2018.
7. Rabanser, Guennemann, Lipton. Failing loudly: an empirical study of methods for detecting dataset shift. NeurIPS, 2019.
8. Bifet, Gavalda. Learning from time-changing data with adaptive windowing. SIAM International Conference on Data Mining, 2007.
9. Gama, Medas, Castillo, Rodrigues. Learning with drift detection. SBIA, 2004.
10. Page. Continuous inspection schemes. Biometrika, 1954.
11. Hendrycks, Gimpel. A baseline for detecting misclassified and out-of-distribution examples in neural networks. ICLR, 2017.
12. Garg, Balakrishnan, Lipton, Neyshabur, Sedghi. Leveraging unlabeled data to predict out-of-distribution performance. ICLR, 2022.
13. Gretton, Borgwardt, Rasch, Schoelkopf, Smola. A kernel two-sample test. Journal of Machine Learning Research, 2012.
14. Lipton, Wang, Smola. Detecting and correcting for label shift with black box predictors. ICML, 2018.
15. Shimodaira. Improving predictive inference under covariate shift by weighting the log-likelihood function. Journal of Statistical Planning and Inference, 2000.
16. Sugiyama, Krauledat, Mueller. Covariate shift adaptation by importance weighted cross validation. Journal of Machine Learning Research, 2007.
17. Sculley and colleagues. Hidden technical debt in machine learning systems. NeurIPS, 2015.
18. Ovadia and colleagues. Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift. NeurIPS, 2019.
19. Siddiqi. Credit Risk Scorecards. Wiley, 2006 (for the population stability index in practice).
20. Machine Learning Group, Universite Libre de Bruxelles. Credit Card Fraud Detection (Kaggle dataset).

Final log: keep 12 to 15 verified entries. Add any better sources you find.

---

## 15. Quality gates and definition of done

### 15.1 Tests (pytest, all must pass)

1. Generator reproducibility: same seed gives the same stream.
2. Generator acceptance criteria of 5.3.
3. Drift injector writes the correct event times.
4. Leakage guard: requesting labels newer than window t-D raises an error, and the simulator never triggers it.
5. PSI of identical samples is near zero and increases with shift. KS behaves the same way.
6. Null calibration: on S0 with the tuning seeds, the share of windows above the threshold is close to the target.
7. Metrics: average precision and recall at budget on tiny hand-checked examples.
8. Retrain policy: a label-free alarm at window t schedules a retrain at t plus D plus m, never earlier, and a backstop alarm retrains immediately.
9. Reference rebuild uses out-of-fold scores (check that in-sample scores are not used).
10. Config freeze: the main run records the config hash and the git commit in its output.

### 15.2 Definition of done

1. All P0 items are complete, tests pass, and `python -m telltale.cli run --config configs/main.yaml` reproduces the results from a clean clone.
2. `docs/first_pass_prediction.md` was committed before the first main run (check the git history).
3. The report opens in Word, matches the template layout, has the 16 sections plus the extra subsections of 13.1, has no empty sections, no placeholder text other than the two author placeholders, every figure and table numbered and referred to, every number traceable to `results/summary.json`, and every reference verified.
4. A search for the em dash character across the repo and the report text finds nothing.
5. The PDF has been exported and every page inspected visually.
6. The README has the architecture figure, one results figure, the quick start commands, a limitations paragraph and a short "Why the name" note: a telltale is a small signal that reveals something hidden, like the ribbons on a sail that show how the wind is really flowing, and the label-free signals in this project reveal model degradation before any labels can confirm it.
7. The final message to the author lists: what was built, the headline results, which hypotheses were supported or not, what was cut, template typos that were fixed, and the items that remain the author's to do.

---

## 16. Honesty rules (non-negotiable)

1. Report results as they are. A hypothesis that fails is a finding, not a problem to hide.
2. Parameters are chosen on tuning seeds only. After the `frozen-config` tag, the main configuration does not change. Any deviation is logged and disclosed in the report.
3. Never present the simulation as proof the method works on real banks. Say what the evidence shows and what it cannot show.
4. Never invent team contributions, citations, screenshots or measurements.
