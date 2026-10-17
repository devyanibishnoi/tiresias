"""Metrics (PRD Section 8). Fraud is rare, so accuracy is never used."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score

ALERT_BUDGET = 0.02  # top 2 percent of transactions by score, per window


def average_precision(y_true: np.ndarray, scores: np.ndarray) -> float:
    if y_true.sum() == 0:
        return float("nan")
    return float(average_precision_score(y_true, scores))


def recall_at_budget(y_true: np.ndarray, scores: np.ndarray, budget: float = ALERT_BUDGET) -> float:
    """Share of frauds caught if the top `budget` share of transactions by
    score are flagged in this window."""
    n = len(scores)
    if y_true.sum() == 0:
        return float("nan")
    k = max(1, int(round(n * budget)))
    top_idx = np.argpartition(-scores, k - 1)[:k]
    caught = y_true[top_idx].sum()
    return float(caught / y_true.sum())


def time_averaged_recall(per_window_recall: np.ndarray) -> float:
    return float(np.nanmean(per_window_recall))


def gap_closed(method_recall: float, b0_recall: float, b2_recall: float) -> float:
    denom = b2_recall - b0_recall
    if abs(denom) < 1e-9:
        return float("nan")
    return float((method_recall - b0_recall) / denom)
