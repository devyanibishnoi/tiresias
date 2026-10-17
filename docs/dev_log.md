# Dev log

Dated entries: what went wrong or was decided, and what was done. This is the only source for the
report's Challenges Faced section.

## 2026-10-17

- Started build from PRD.md. Repo root only had PRD.md and the two author Word files. Moved the
  Word files into `docs/inputs/` and copied the template into `report/template.docx`.
- Only Python 3.14 is installed on the author's machine. No `gh` CLI available, so the GitHub repo
  push step will be left to the author (repo already exists at
  https://github.com/devyanibishnoi/telltale.git).
- First version of the covariate-drift injector (S1) shifted the mean of the informative features
  directly in the direction of their weights. This made average precision go UP after drift
  instead of down: the shift raised the ambient fraud rate in the window, and average precision is
  prevalence-sensitive, so a higher local prevalence looked like better detection even though
  nothing about the model's discrimination had changed. Fixed by (a) choosing a zero-sum shift
  direction so the shift does not move the ambient fraud rate, and (b) adding a severity-scaled
  noise term to the logit to model the real damage (observed features explain less once the
  population has moved into a region the model never trained on). See docs/decisions.md.
- Initial `data/sim_samples/` files saved the full stream per scenario (about 21 MB each, 202 MB
  total), far too large for "small compressed representative streams". Replaced with an 8-window,
  300-row-per-window subsample (about 165 KB per scenario).
- Generator acceptance tests (PRD 5.3) all pass on the 5 tuning seeds (100-104); see
  `tests/test_generator.py` and `tests/test_injector.py`. Phase 1 is done.
- Phase 2 build (simulator, label vault, monitors, backstop, retrain policies) initially
  calibrated the score monitor's null threshold from a cross-validated ensemble built independently
  of the deployed model. Pre-drift evidence came out around 50x the alarm threshold, because the
  deployed model's score distribution never matched the unrelated CV ensemble's, drift or not.
  Fixed by using the deployed model's own (legitimately out-of-sample) predictions on the
  calibration windows for the initial reference, reserving the 5-fold blocked out-of-fold
  procedure for post-retrain reference rebuilds only (PRD 6.6 specifically calls for OOF there,
  because the retrained model's own training windows would otherwise be scored in-sample).
- A first end-to-end timing check on one scenario/seed across all 8 strategies projected to about
  26.6 hours for the full main experiment (1440 scenario/seed/strategy runs), driven by the
  `class_weight="balanced"` bug above plus an unoptimised null calibration loop, both now fixed
  (see docs/decisions.md). Still re-measuring the full-scale cost after the fixes before deciding
  whether seeds need to be cut per PRD's cut list (Section 3).
- Phase 2 is functionally complete: generator, injector, label vault, monitors (input drift, score
  drift, calibrator, combiner, backstop, CUSUM), model/retrainer, and all 8 strategies (B0-B3,
  M0, M1, M1a, M1b) run end to end and agree with the PRD's retrain-timing rules (label-free alarms
  defer to t+D+m, backstop retrains immediately, fixed schedule and oracle trigger correctly). 38
  tests pass.
- Phase 3 tuning first attempt failed completely: grid search over a wide (slack, height) range
  found zero parameter combinations keeping the false alarm rate at or below 1 per 100 windows on
  S0 and S6. Diagnosed by printing the mean combined evidence under null: S0 was a sane 0.9 to
  0.92, but S6 was 3.1 to 3.4, meaning the "benign seasonality" scenario was setting off the input
  or score monitor almost constantly. Root cause was the null calibration's bootstrap resampling
  (see docs/decisions.md): it drew individual rows instead of whole windows, so it never saw a
  synthetic "window" with S6's shared per-window seasonal phase, only diluted mixes of many
  phases. Fixed by resampling whole reference windows. After the fix, S0 and S6 both settled to a
  mean evidence around 1.0 to 1.1, and tuning succeeded on the first proper grid search: slack
  1.8, height 2.5 for the combined/input/score CUSUM, slack 2.4, height 1.5 for the backstop, both
  at 0.17 false alarms per 100 windows.
- A side effect of the bad tuning run (before the fix was found) was a projected 26+ hour main
  experiment, since the unusable parameter combinations the grid search WAS forced to accept
  (tried at a much higher height to suppress S6's false floor) would have meant very large CUSUM
  heights and correspondingly more retrains triggered by noise. With the fix, the same
  `test_policy_timing.py` suite that took 341 seconds with the untuned placeholder parameters
  (slack 0.5, height 3.0) now takes 57 seconds with the properly tuned ones, because far fewer
  spurious retrains fire.
- A dedicated null-calibration check (does a fresh S0 window actually exceed its own 99th
  percentile threshold about 1 percent of the time) caught a second calibration bug after the
  whole-window bootstrap fix: resampling whole reference windows verbatim can only produce 10
  distinct outcomes (there are only 10 calibration windows), so the resulting 99th percentile was
  capped near the single most unusual window already on hand and a fresh window exceeded it 60
  percent of the time. Fixed by also resampling rows within each chosen window (bootstrap the
  window choice, then bootstrap that window's rows). Re-ran `python -m telltale.cli tune`
  afterward: combined CUSUM settled at slack 1.0, height 1.0, measured 0 false alarms per 100
  windows on both S0 and S6 on the tuning seeds; backstop stayed at slack 2.2, height 1.0. Full
  test suite (38 tests) now runs in 66 seconds, down from 159 seconds before this fix, because
  even fewer spurious retrains fire.
- Timing re-measured end to end after all Phase 2/3 fixes: all 8 P0 strategies on one
  scenario/seed took about 136 seconds sequentially (down from about 530 seconds before the
  `class_weight` fix and the OOF-skip-for-B1/B2 optimisation). A controlled CPU-bound benchmark
  showed this sandboxed shell only gets genuine parallelism across about 2 real cores despite
  `os.cpu_count()` reporting 12, so `telltale/experiments.py` uses a small worker pool
  (`DEFAULT_MAX_WORKERS = 3`) rather than assuming full-core scaling. Projected the full 20-seed
  main experiment at roughly 3 to 3.5 hours; discussed with the author and cut evaluation seeds to
  10 (PRD Section 3 cut list item 1), projected at roughly 1.5 to 1.75 hours. `telltale/config.py`
  and `configs/main.yaml` updated accordingly.
- `docs/first_pass_prediction.md` (10 to 12 numeric predictions with ranges and reasoning) written
  and committed before the pilot or main run, per PRD Section 10.2. Phase 3 is done.
