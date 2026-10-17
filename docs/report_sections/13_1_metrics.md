## 13.1 Defined Performance Metrics List

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
