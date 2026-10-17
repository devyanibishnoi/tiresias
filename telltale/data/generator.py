"""Synthetic transaction stream generator.

Produces one window of transactions at a time. Feature generation is kept
separate from the fraud-labeling function so that drift injectors can shift
either the inputs (covariate drift) or the label-generating function
(concept drift) independently, as required by PRD Section 5.
"""

from __future__ import annotations

import numpy as np

from telltale.config import (
    N_CATEGORICAL,
    N_CONTINUOUS,
    N_CYCLIC,
    N_SKEWED,
)

# A fixed correlation structure for the 14 continuous features so that the
# generator is not just independent noise. Built once, used for every window.
_RNG_CORR = np.random.default_rng(12345)
_A = _RNG_CORR.normal(0, 0.3, size=(N_CONTINUOUS, N_CONTINUOUS))
_COV_CONTINUOUS = _A @ _A.T + np.eye(N_CONTINUOUS) * 0.7
_D_INV_SQRT = 1.0 / np.sqrt(np.diag(_COV_CONTINUOUS))
_CORR_CONTINUOUS = _COV_CONTINUOUS * np.outer(_D_INV_SQRT, _D_INV_SQRT)


def make_window_features(
    rng: np.random.Generator,
    n: int,
    mean_shift: np.ndarray | None = None,
    amount_scale: float = 1.0,
) -> np.ndarray:
    """Draw N transactions worth of features for one window.

    mean_shift: optional length N_CONTINUOUS array of per-feature mean shifts
        (in standard deviations) applied to the continuous block, used by the
        drift injector for covariate drift.
    amount_scale: multiplicative factor applied to the two amount-like
        features, used by the drift injector for benign seasonality.
    """
    mean = np.zeros(N_CONTINUOUS) if mean_shift is None else np.asarray(mean_shift, dtype=float)
    continuous = rng.multivariate_normal(mean, _CORR_CONTINUOUS, size=n)

    amount_1 = rng.lognormal(mean=np.log(50.0), sigma=0.8, size=n) * amount_scale
    amount_2 = rng.lognormal(mean=np.log(20.0), sigma=1.0, size=n) * amount_scale

    hour = rng.uniform(0, 24, size=n)
    hour_sin = np.sin(2 * np.pi * hour / 24.0)
    hour_cos = np.cos(2 * np.pi * hour / 24.0)

    cat_1 = rng.integers(0, 5, size=n).astype(float)
    cat_2 = rng.integers(0, 10, size=n).astype(float)

    skewed = np.column_stack([amount_1, amount_2])
    cyclic = np.column_stack([hour_sin, hour_cos])
    categorical = np.column_stack([cat_1, cat_2])

    assert skewed.shape[1] == N_SKEWED
    assert cyclic.shape[1] == N_CYCLIC
    assert categorical.shape[1] == N_CATEGORICAL

    return np.concatenate([continuous, skewed, cyclic, categorical], axis=1)


def fraud_logit(
    X: np.ndarray,
    informative_idx: list[int],
    weights: list[float],
    intercept: float,
) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    return X[:, informative_idx] @ w + intercept


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def calibrate_intercept(
    rng_seed: int,
    informative_idx: list[int],
    weights: list[float],
    target_rate: float,
    n_calib: int = 200_000,
) -> float:
    """Bisect on the intercept so that P(fraud) matches target_rate under the
    stable (no-shift) feature distribution."""
    rng = np.random.default_rng(rng_seed)
    X = make_window_features(rng, n_calib)

    lo, hi = -15.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        p = sigmoid(fraud_logit(X, informative_idx, weights, mid)).mean()
        if p > target_rate:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0
