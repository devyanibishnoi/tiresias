"""Input drift monitor (PRD Section 6.3): per-feature PSI and KS against the
reference, aggregated as the mean of the five largest PSI values. Also
reports which features drove the value, for the decision log.

Bin edges and reference fractions are precomputed once per reference (see
FeatureBins) and reused for every window until the next retrain. Recomputing
quantile edges and the KS statistic (scipy's ks_2samp, which sorts both
samples) on every window for all 20 features was the dominant cost of a full
run: KS is only needed for the per-feature diagnostics PRD 6.3 asks for when
explaining an alarm, not for the evidence value itself, so it is computed
lazily rather than on every window.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tiresias.monitors.calibration import psi_null_draws
from tiresias.monitors.stats import ks_statistic, prepare_bins, psi, psi_fast

N_TOP_FEATURES = 5


@dataclass
class FeatureBins:
    edges: list
    ref_frac: list


def prepare_input_drift_reference(reference_X: np.ndarray) -> FeatureBins:
    d = reference_X.shape[1]
    edges, ref_frac = [], []
    for f in range(d):
        e, fr = prepare_bins(reference_X[:, f])
        edges.append(e)
        ref_frac.append(fr)
    return FeatureBins(edges=edges, ref_frac=ref_frac)


@dataclass
class InputDriftResult:
    value: float  # mean of the N_TOP_FEATURES largest per-feature PSI
    per_feature_psi: np.ndarray
    per_feature_ks: np.ndarray | None
    top_features: list  # feature indices driving the value, largest first


def input_drift_value(reference_X: np.ndarray, window_X: np.ndarray) -> InputDriftResult:
    """Slow path: recomputes everything from raw arrays, including KS. Used
    by tests and one-off diagnostics, not inside the simulator's hot loop."""
    d = reference_X.shape[1]
    psis = np.array([psi(reference_X[:, f], window_X[:, f]) for f in range(d)])
    kss = np.array([ks_statistic(reference_X[:, f], window_X[:, f]) for f in range(d)])

    order = np.argsort(psis)[::-1]
    top = order[:N_TOP_FEATURES]
    value = float(psis[top].mean())

    return InputDriftResult(value=value, per_feature_psi=psis, per_feature_ks=kss, top_features=list(top))


def input_drift_value_fast(bins: FeatureBins, window_X: np.ndarray) -> InputDriftResult:
    """Hot path used by the simulator: PSI only, against precomputed bins.
    Call input_drift_value (or add_ks_diagnostics below) if KS is needed,
    e.g. when logging the reasons for an alarm."""
    d = window_X.shape[1]
    psis = np.array([psi_fast(bins.edges[f], bins.ref_frac[f], window_X[:, f]) for f in range(d)])

    order = np.argsort(psis)[::-1]
    top = order[:N_TOP_FEATURES]
    value = float(psis[top].mean())

    return InputDriftResult(value=value, per_feature_psi=psis, per_feature_ks=None, top_features=list(top))


def input_drift_null_draws(reference_X: np.ndarray, idx_matrix: np.ndarray, n_top: int = N_TOP_FEATURES) -> np.ndarray:
    """Vectorised null draws of the input-drift value (mean of the top
    n_top per-feature PSI), one draw per row of idx_matrix."""
    d = reference_X.shape[1]
    per_feature = np.stack([psi_null_draws(reference_X[:, f], idx_matrix) for f in range(d)], axis=1)
    per_feature.sort(axis=1)
    return per_feature[:, -n_top:].mean(axis=1)
