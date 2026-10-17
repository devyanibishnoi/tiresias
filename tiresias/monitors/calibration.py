"""Null calibration (PRD Section 6.2).

For each raw signal, the null distribution is built by repeatedly drawing a
window of size N from the reference pool and computing the signal against
the fixed reference. The raw threshold is the 99th percentile under the
null; evidence is the signal value divided by its threshold, so 1.0 means
"at the edge of normal" on a common scale across every signal.

All four signals (input-drift PSI, score PSI, alert ratio, entropy ratio)
are bootstrapped from one shared (n_draws, window_n) index matrix so the
whole calibration is a handful of vectorised numpy passes instead of a
Python loop of 1000+ iterations per signal. A naive per-draw loop measured
over two minutes per reference rebuild, which is infeasible: a full main
run needs several thousand rebuilds (every retrain, every strategy, every
seed, every scenario).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from tiresias.monitors.stats import bin_edges, digitize, psi_from_fractions

N_NULL_DRAWS = 300
NULL_PERCENTILE = 99


def bootstrap_index_matrix(pool_size: int, window_n: int, n_draws: int, rng: np.random.Generator) -> np.ndarray:
    return rng.integers(0, pool_size, size=(n_draws, window_n))


def bootstrap_window_index_matrix(pool_size: int, window_n: int, n_draws: int, rng: np.random.Generator) -> np.ndarray:
    """Draw whole reference windows (PRD 6.2: "drawing windows of size N
    from the reference"), not individually shuffled rows, then resample rows
    within the chosen window with replacement.

    Picking a window and returning it byte-for-byte would cap the null
    distribution at as many distinct outcomes as there are reference windows
    (only 10, the calibration windows 20-29), which badly understates the
    99th percentile: a verbatim historical window can never be more extreme
    than the most extreme window already on hand, but a genuinely new window
    drawn from the same distribution can, and routinely did in testing (a
    fresh S0 window exceeded the resulting threshold about 60 percent of the
    time instead of about 1 percent, see docs/dev_log.md). Resampling rows
    within the chosen window keeps the shared within-window structure a pure
    row-level bootstrap washes out (S6's seasonal phase, PRD 6.2's wording)
    while still giving the null genuine tail variability."""
    n_windows = pool_size // window_n
    chosen = rng.integers(0, n_windows, size=n_draws)
    within_window_offsets = rng.integers(0, window_n, size=(n_draws, window_n))
    return chosen[:, None] * window_n + within_window_offsets


def psi_null_draws(pool_values: np.ndarray, idx_matrix: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """Null PSI draws for one continuous signal, against the pool itself."""
    edges = bin_edges(pool_values, n_bins)
    bin_idx = digitize(pool_values, edges)
    n_bins_actual = len(edges) - 1

    ref_counts = np.bincount(bin_idx, minlength=n_bins_actual).astype(float)
    ref_frac = ref_counts / ref_counts.sum()

    drawn_bins = bin_idx[idx_matrix]  # (n_draws, window_n)
    counts = np.stack([(drawn_bins == b).sum(axis=1) for b in range(n_bins_actual)], axis=1)
    cur_frac = counts / idx_matrix.shape[1]

    return psi_from_fractions(ref_frac, cur_frac)


def ratio_null_draws(pool_values: np.ndarray, idx_matrix: np.ndarray, reference_mean: float, agg: str = "mean") -> np.ndarray:
    """Null draws of (statistic of the drawn sample) / reference_mean, for
    alert rate and mean entropy."""
    drawn = pool_values[idx_matrix]  # (n_draws, window_n)
    stat = drawn.mean(axis=1)
    if reference_mean <= 0:
        return stat
    return stat / reference_mean


def threshold_from_null(draws: np.ndarray, pct: float = NULL_PERCENTILE) -> float:
    return float(np.percentile(draws, pct))


@dataclass
class SignalThresholds:
    """One threshold per named raw signal, with evidence() to convert a raw
    value to the common 0-to-inf evidence scale."""

    thresholds: dict = field(default_factory=dict)

    def evidence(self, name: str, raw_value: float) -> float:
        t = self.thresholds[name]
        if t <= 0:
            return 0.0
        return max(0.0, raw_value / t)
