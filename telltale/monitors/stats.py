"""Shared statistics: population stability index and the KS statistic.

Used both by the input/score drift monitors (PRD Section 6.3, 6.4) and by the
generator acceptance tests (PRD Section 5.3), which check that scenario S4
leaves every feature's PSI near the null level and that S6 visibly moves it.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats


def _bin_edges(reference: np.ndarray, n_bins: int = 10) -> np.ndarray:
    quantiles = np.linspace(0, 1, n_bins + 1)
    edges = np.quantile(reference, quantiles)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return np.unique(edges) if len(np.unique(edges)) > 2 else np.array([-np.inf, 0.0, np.inf])


def psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10, eps: float = 1e-4) -> float:
    """Population stability index of current against reference."""
    edges = _bin_edges(reference, n_bins)
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    ref_frac = ref_counts / ref_counts.sum() + eps
    cur_frac = cur_counts / cur_counts.sum() + eps

    return float(np.sum((cur_frac - ref_frac) * np.log(cur_frac / ref_frac)))


def ks_statistic(reference: np.ndarray, current: np.ndarray) -> float:
    return float(sp_stats.ks_2samp(reference, current).statistic)
