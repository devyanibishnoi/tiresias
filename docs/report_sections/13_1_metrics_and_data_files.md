# 13.1 (part) Defined Performance Metrics List

Required by the rubric's third row (Defined Performance Metrics List), mapped into report Section
13.1 per PRD 13.1. All of PRD Section 8's metrics:

| Metric | Definition |
|---|---|
| Average precision (AP) per window | Area under the precision-recall curve on window t, computed with the hidden labels (evaluation only) |
| Recall at alert budget | Share of frauds caught when the top 2 percent of transactions by score are flagged in each window |
| Time-averaged recall at budget | Mean of recall at budget over the evaluation windows |
| Gap closed | (method minus B0) divided by (B2 minus B0), on time-averaged recall at budget |
| Detection delay | Windows from a true event's onset to the first alarm after it, per event, per alarm type (label-free, backstop) |
| Detection rate | Share of events detected within 10 windows |
| False alarm rate | Alarms per 100 windows in segments with no active drift (S0, S6, and the pre-onset period of other scenarios) |
| Early-warning lead time | Backstop alarm window minus label-free alarm window, per event |
| Exposure | Windows between event onset and deployment of a corrected model |
| Retrain count | Number of retrains executed over the stream |
| Compute cost | Retrain count times measured seconds per retrain, plus monitoring seconds |

Accuracy is never reported as a main metric: at a 2 percent base fraud rate, a model that flags
nothing still scores about 98 percent accuracy, which says nothing useful about fraud detection.

# 13.4 (part) Representative Data Simulation Files

| File / directory | Contents | Approx. size |
|---|---|---|
| `data/sim_samples/<scenario>_<severity>_seed0.npz` | A small representative sample per scenario (10 files: S0 through S7, S1 at all three severities): 8 fixed windows (reference, pre-onset, just-after-onset, mid-drift, late-drift) with a 300-transaction subsample each | About 166 KB per file |
| `data/sim_samples/events/<scenario>_<severity>.json` | Ground truth drift event times (onset/offset windows, drift type) for the matching sample | A few KB each |
| `results/per_window_log.csv.gz` | One row per (scenario, severity, seed, strategy, window): AP, recall, evidence values, alarm flags, retrain flags, from the main run | See Section 13 (filled once the main run completes) |
| `results/retrains.csv` | One row per retrain event across the main run: window, source (label_free / backstop / fixed / oracle), scenario, severity, seed, strategy | See Section 13 |
| `results/summary.json` | Every aggregated number the report cites: time-averaged recall and AP with confidence intervals, retrain counts, detection delays, false alarm rates, grouped by (scenario, severity, strategy) | See Section 13 |
| `results/tuning.json` | The CUSUM/backstop parameter grid search output from Phase 3 (chosen slack/height, measured false alarm rate on the tuning seeds) | A few KB |
| `results/profiling.json` | Monitor runtime and memory at window sizes from 1,000 to 1,000,000 transactions, plus retrain timing with and without the out-of-fold reference rebuild | A few KB |
| `results/pilot/` | The Phase 4 pilot run's own per-window log, retrains, summary, figure and note | About 237 KB total |

A full stream (150 windows x 2000 rows x 20 features) is about 24 MB uncompressed, which is why
`data/sim_samples/` keeps a deliberately small representative subsample per scenario rather than a
full copy of every run (see `docs/decisions.md`).
