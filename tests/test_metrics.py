"""Metrics on tiny hand-checked examples, PRD Section 15.1 item 7."""

import numpy as np

from tiresias.metrics import average_precision, recall_at_budget


def test_recall_at_budget_perfect_ranking():
    y = np.array([0, 0, 0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.3, 0.4, 0.9, 0.8])
    # budget picks top 2 of 6 -> top 2 scores are the two frauds -> recall 1.0
    assert recall_at_budget(y, scores, budget=2 / 6) == 1.0


def test_recall_at_budget_worst_ranking():
    y = np.array([0, 0, 0, 0, 1, 1])
    scores = np.array([0.9, 0.8, 0.7, 0.6, 0.1, 0.05])
    assert recall_at_budget(y, scores, budget=2 / 6) == 0.0


def test_average_precision_perfect_ranking_is_one():
    y = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    assert average_precision(y, scores) == 1.0


def test_average_precision_handles_no_positives():
    y = np.array([0, 0, 0])
    scores = np.array([0.1, 0.5, 0.9])
    assert np.isnan(average_precision(y, scores))
