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
- Tried automating the Word-to-PDF export and a visual page check with `pywin32`'s Word COM
  automation (Word is installed and registered on this machine). Two attempts both left
  `WINWORD.EXE` running indefinitely with no output and no PDF produced, even with
  `DisplayAlerts = 0` and a read-only open; likely this sandboxed shell cannot properly interact
  with GUI-adjacent COM automation, similar to the earlier finding that it only exposes about 2
  real CPU cores despite reporting 12. Gave up on automating this step; PDF export is a one-click
  "Save As PDF" in Word and is left for the author to do themselves after reviewing the final
  document, alongside the other author-only items in PRD Section 13.4.
- Three real bugs found and fixed while building `report/build_report.py`'s markdown-to-docx
  inserter, each caught by actually inspecting the generated document's paragraph structure rather
  than trusting that it ran without an exception: (1) multi-line bulleted list items in the source
  markdown (soft-wrapped across several physical lines) were only capturing the first line, with
  continuation lines becoming stray separate paragraphs; fixed by accumulating continuation lines
  until the next bullet marker, heading, table or blank line. (2) A stale search-boundary bug: the
  index of the "next section heading" was computed once before any content was inserted, but each
  insertion shifts every later paragraph's index, so by the time a later subsection needed that
  boundary it excluded the exact paragraph being searched for, producing a duplicate "5.2
  Objectives" heading instead of reusing the template's own line. Fixed by re-resolving the
  boundary by text search on every lookup instead of caching an index. (3) The function that clears
  a section's leading placeholder text had no concept of "this paragraph is itself a subsection
  heading, not instructional filler", so for section 6 (whose Heading 1 has no separate placeholder
  paragraph before "6.1. Use Cases") it blanked out "6.1. Use Cases" itself, then every piece of
  real content got inserted after the wrong anchor. Fixed by sharing one `_is_structural` check
  (numbered "N.N" prefix or a real Heading style) between both placeholder-clearing functions.
- Found a fourth bug while end-to-end smoke testing section 13 (which combines several pieces:
  the metrics list, representative data files, the results-dependent scenario table, and the code
  snippets): calling `fill_section` once per piece for the SAME top-level heading re-triggers
  placeholder clearing against content the previous call already inserted, duplicating or
  scrambling it. Restructured so every top-level heading gets exactly one `fill_section` call, by
  concatenating all of a section's markdown pieces into one string first
  (`build_results_markdown`, `insert_results_figures` in `report/build_report.py`). While fixing
  this, also split `docs/report_sections/13_1_metrics_and_data_files.md` into separate
  `13_1_metrics.md` and `13_4_data_files.md` files so the concatenation order could match the
  numeric section order (13.1, 13.2, 13.3, 13.4, 13.5) instead of the accidental 13.1, 13.4, 13.2,
  13.3 order the original combined file produced. Separately: tables inserted via `add_table_after`
  do not show up when iterating `doc.paragraphs` (python-docx only walks `<w:p>` elements, not
  `<w:tbl>`), which looked like a missing-table bug during debugging until checked via the
  document body's raw XML children in order; worth remembering for any future python-docx
  debugging in this project.
- Full smoke test of `report/build_report.py` against the pilot's `summary.json` and
  `per_window_log.csv.gz` (temporarily copied to the main run's expected paths, then removed) ran
  clean end to end: 0 leftover template placeholders outside the two that are supposed to wait
  (Abstract, Conclusion), correct section numbering throughout, all tables and code snippets in
  place. The report builder is considered structurally done; what remains is real numbers once the
  main run finishes.
- Main run (`configs/main.yaml`, 720 scenario/severity/seed/strategy combinations) completed in
  6132.6 seconds (about 1.7 hours), matching the projection in docs/decisions.md. It was launched
  with the pre-`paired_seeds` version of `telltale/summarize.py` (from before the session-limit
  interruption earlier), so `results/summary.json` was regenerated by re-aggregating the already-
  computed `results/per_window_log.csv.gz` and `results/events_by_scenario.json` with the current
  code; no need to rerun the simulation itself.
- H1, H3, H4 held clearly; H2's ablation showed the combined signal adds no detection-delay benefit
  over either signal alone on S1 moderate (all three already detect at 0-window median delay) but
  does inherit the score signal's higher false alarm rate. H5 did not fully hold: the full
  framework (M1) and the score-only variant (M1b) measured 1.08 false alarms per 100 windows on S0,
  above the PRD's 1.0 ceiling, while the input-only variant (M1a), the backstop alone (B3) and the
  label-free-only strategy (M0) all stayed comfortably under target. Investigated via the S4
  failure figure: a backstop-triggered retrain whose training window still straddles the
  concept-drift boundary measurably destabilises the monitor's own reference afterward, producing a
  real (not spurious) evidence spike; the same mechanism plausibly explains part of M1/M1b's
  elevated false alarm rate on S0, since both run the backstop and therefore retrain more often
  than M0. Reported as a genuine finding in the report, not adjusted after the fact.
- Three figure bugs found and fixed while reviewing the generated plots before trusting them in the
  report: (1) `make_ablation_bars`'s false-alarm subplot was titled "S0/S6 average" but actually
  computed from S1's own short pre-onset window (30 windows), which is sparse enough that it showed
  all-zero bars regardless of the real S0/S6 rates; fixed to average S0 and S6 directly. (2) the S4
  failure figure's title claimed label-free evidence "stays flat", which is not accurate: it spikes
  well above threshold during the backstop-retrain transition period (even though it stays flat
  before and shortly after the backstop's own retrain, which is what actually matters for H4);
  fixed the title and added an annotated marker at the first backstop retrain so the figure
  explains the spike instead of contradicting its own caption. (3) the Abstract paragraph had
  literal `\n` characters embedded from the source markdown file's line-wrapping; OOXML text runs
  do not interpret `\n` as a line break, so without collapsing it to spaces the wrap points would
  have shown as stray artifacts in the rendered paragraph.
- Full report built from real results (`report/build_report.py`): 282 paragraphs, 16 tables, 0
  leftover template placeholders, 0 em dashes, all 16 sections present in order. `report/out/
  telltale_report.docx` is the current candidate for the final deliverable.
- `docs/first_pass_prediction.md` (10 to 12 numeric predictions with ranges and reasoning) written
  and committed before the pilot or main run, per PRD Section 10.2. Phase 3 is done.
- Phase 4 pilot run (S0, S1 moderate, 5 seeds, strategies B0/B1/M1, `configs/pilot.yaml`) completed
  in about 193 seconds. Results in `results/pilot/`. Early signal: M1 detected moderate covariate
  drift with 0 windows of label-free delay on every pilot seed (backstop needed a median of 8.5),
  and matched B1's time-averaged recall within about 1.3 percent relative while retraining about
  1.6 times on average against B1's fixed 6. Consistent with predictions 1, 8 and 9 in
  `docs/first_pass_prediction.md`, though 5 seeds and one scenario is not enough to call it a
  result. Phase 4 is done.
