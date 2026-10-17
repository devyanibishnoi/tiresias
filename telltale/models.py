"""Model construction and the retrainer (PRD Section 6.7, 6.6, 6.2)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

MAX_ITER = 60
N_OOF_FOLDS = 5


def make_model(random_state: int) -> HistGradientBoostingClassifier:
    """One fixed model configuration, used by every strategy. Class
    imbalance (fraud is about 2 percent of every window) is handled by not
    reweighting at all: the metrics this project reports (average precision,
    recall at a fixed alert budget, PRD Section 8) already account for rarity
    by construction, and `class_weight="balanced"` (or an equivalent
    `sample_weight` array) measured about 6 to 10 seconds of fixed overhead
    per `.fit()` call regardless of data size on this machine's scikit-learn
    1.9.1 / Python 3.14 build, against about 0.3 to 0.6 seconds unweighted.
    At the scale of the main experiment (thousands of retrains across
    seeds, scenarios and strategies) that overhead alone would have made the
    run infeasible; see docs/decisions.md and docs/dev_log.md."""
    return HistGradientBoostingClassifier(
        max_iter=MAX_ITER,
        random_state=random_state,
    )


def fit_model(X: np.ndarray, y: np.ndarray, random_state: int) -> HistGradientBoostingClassifier:
    model = make_model(random_state)
    model.fit(X, y)
    return model


def out_of_fold_scores(
    X: np.ndarray,
    y: np.ndarray,
    window_ids: np.ndarray,
    random_state: int,
    n_folds: int = N_OOF_FOLDS,
) -> np.ndarray:
    """Out-of-fold predicted fraud probability, blocked by window so every
    row of a window lands in exactly one fold. Used to build an honest
    reference distribution: scores from the model that will actually be
    deployed are in-sample and overconfident (PRD 6.6)."""
    unique_windows = np.unique(window_ids)
    rng = np.random.default_rng(random_state)
    shuffled = rng.permutation(unique_windows)
    folds = np.array_split(shuffled, min(n_folds, len(unique_windows)))

    oof = np.zeros(len(y), dtype=float)
    for i, fold_windows in enumerate(folds):
        test_mask = np.isin(window_ids, fold_windows)
        train_mask = ~test_mask
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            continue
        fold_model = fit_model(X[train_mask], y[train_mask], random_state=random_state * 100 + i)
        oof[test_mask] = fold_model.predict_proba(X[test_mask])[:, 1]
    return oof


@dataclass
class RetrainResult:
    """Output of one retrain: the newly deployed model, plus the raw
    material (features and out-of-fold scores of the same window block) a
    caller needs to rebuild the monitor reference (PRD 6.2, 6.6)."""

    model: HistGradientBoostingClassifier
    X: np.ndarray
    oof_scores: np.ndarray
    window_ids: np.ndarray


class Retrainer:
    def __init__(self, random_state: int = 0):
        self.random_state = random_state
        self._retrain_count = 0

    def fit(self, X_recent: np.ndarray, y_recent: np.ndarray, window_ids_recent: np.ndarray) -> RetrainResult:
        """Refit the deployed model on the W most recent matured windows and
        compute out-of-fold scores on the same block, honest material for a
        new reference (never the retrained model's own in-sample scores)."""
        seed = self.random_state + self._retrain_count
        model = fit_model(X_recent, y_recent, random_state=seed)
        oof = out_of_fold_scores(X_recent, y_recent, window_ids_recent, random_state=seed)
        self._retrain_count += 1
        return RetrainResult(model=model, X=X_recent, oof_scores=oof, window_ids=window_ids_recent)
