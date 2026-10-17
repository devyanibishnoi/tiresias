"""Shared statistics: population stability index and the KS statistic.

Used both by the input/score drift monitors (PRD Section 6.3, 6.4) and by the
generator acceptance tests (PRD Section 5.3), which check that scenario S4
leaves every feature's PSI near the null level and that S6 visibly moves it.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats


def bin_edges(reference: np.ndarray, n_bins: int = 10) -> np.ndarray:
    quantiles = np.linspace(0, 1, n_bins + 1)
    edges = np.quantile(reference, quantiles)
    edges[0] = -np.inf
    edges[-1] = np.inf
    edges = np.unique(edges)
    return edges if len(edges) > 2 else np.array([-np.inf, 0.0, np.inf])


def digitize(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Bin index (0 to len(edges)-2) of each value under `edges`."""
    return np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(edges) - 2)


def psi_from_fractions(ref_frac: np.ndarray, cur_frac: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """PSI given bin fractions. Works row-wise if cur_frac has shape
    (n_draws, n_bins); ref_frac broadcasts as (n_bins,)."""
    rf = ref_frac + eps
    cf = cur_frac + eps
    return np.sum((cf - rf) * np.log(cf / rf), axis=-1)


def psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10, eps: float = 1e-4) -> float:
    """Population stability index of current against reference."""
    edges = bin_edges(reference, n_bins)
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    ref_frac = ref_counts / ref_counts.sum()
    cur_frac = cur_counts / cur_counts.sum()

    return float(psi_from_fractions(ref_frac, cur_frac, eps))


def ks_statistic(reference: np.ndarray, current: np.ndarray) -> float:
    return float(sp_stats.ks_2samp(reference, current).statistic)


def prepare_bins(reference: np.ndarray, n_bins: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """Precompute bin edges and reference fractions once, so repeated PSI
    calls against a fixed reference (every window, until the next retrain)
    do not recompute quantile edges from scratch every time."""
    edges = bin_edges(reference, n_bins)
    counts = np.bincount(digitize(reference, edges), minlength=len(edges) - 1).astype(float)
    return edges, counts / counts.sum()


def psi_fast(edges: np.ndarray, ref_frac: np.ndarray, current: np.ndarray, eps: float = 1e-4) -> float:
    counts = np.bincount(digitize(current, edges), minlength=len(ref_frac)).astype(float)
    cur_frac = counts / counts.sum()
    return float(psi_from_fractions(ref_frac, cur_frac, eps))
