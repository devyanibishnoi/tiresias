## 13.4 Representative Data Simulation Files

| File / directory | Contents | Approx. size |
|---|---|---|
| `data/sim_samples/<scenario>_<severity>_seed0.npz` | A small representative sample per scenario (10 files: S0 through S7, S1 at all three severities): 8 fixed windows (reference, pre-onset, just-after-onset, mid-drift, late-drift) with a 300-transaction subsample each | About 166 KB per file |
| `data/sim_samples/events/<scenario>_<severity>.json` | Ground truth drift event times (onset/offset windows, drift type) for the matching sample | A few KB each |
| `results/per_window_log.csv.gz` | One row per (scenario, severity, seed, strategy, window): AP, recall, evidence values, alarm flags, retrain flags, from the main run | See Section 13.2 |
| `results/retrains.csv` | One row per retrain event across the main run: window, source (label_free / backstop / fixed / oracle), scenario, severity, seed, strategy | See Section 13.2 |
| `results/summary.json` | Every aggregated number the report cites: time-averaged recall and AP with confidence intervals, retrain counts, detection delays, false alarm rates, grouped by (scenario, severity, strategy) | See Section 13.2 |
| `results/tuning.json` | The CUSUM/backstop parameter grid search output from Phase 3 (chosen slack/height, measured false alarm rate on the tuning seeds) | A few KB |
| `results/profiling.json` | Monitor runtime and memory at window sizes from 1,000 to 1,000,000 transactions, plus retrain timing with and without the out-of-fold reference rebuild | A few KB |
| `results/pilot/` | The Phase 4 pilot run's own per-window log, retrains, summary, figure and note | About 237 KB total |

A full stream (150 windows x 2000 rows x 20 features) is about 24 MB uncompressed, which is why
`data/sim_samples/` keeps a deliberately small representative subsample per scenario rather than a
full copy of every run (see `docs/decisions.md`).
