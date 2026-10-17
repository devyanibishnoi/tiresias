"""Score and confidence monitor (PRD Section 6.4): PSI of the log-odds
score, the alert-rate ratio against a fixed operating threshold, and mean
predictive entropy relative to the reference.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from telltale.monitors.stats import psi, psi_fast

EPS = 1e-6


def log_odds(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def predictive_entropy(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def operating_threshold(reference_scores: np.ndarray, budget: float) -> float:
    """Score cutoff so that `budget` share of the reference is flagged.
    Fixed at calibration time, not recomputed per window."""
    return float(np.quantile(reference_scores, 1 - budget))


@dataclass
class ScoreDriftRaw:
    psi_log_odds: float
    alert_rate: float
    alert_ratio: float
    mean_entropy: float
    entropy_ratio: float


def score_drift_raw(
    reference_scores: np.ndarray,
    window_scores: np.ndarray,
    threshold: float,
    reference_alert_rate: float,
    reference_mean_entropy: float,
    log_odds_bins: tuple | None = None,
) -> ScoreDriftRaw:
    """log_odds_bins, if given, is the (edges, ref_frac) pair precomputed
    once per reference by telltale.monitors.stats.prepare_bins, avoiding a
    quantile recomputation on every window."""
    if log_odds_bins is not None:
        edges, ref_frac = log_odds_bins
        psi_lo = psi_fast(edges, ref_frac, log_odds(window_scores))
    else:
        psi_lo = psi(log_odds(reference_scores), log_odds(window_scores))

    alert_rate = float((window_scores > threshold).mean())
    alert_ratio = alert_rate / reference_alert_rate if reference_alert_rate > 0 else alert_rate

    mean_ent = float(predictive_entropy(window_scores).mean())
    entropy_ratio = mean_ent / reference_mean_entropy if reference_mean_entropy > 0 else mean_ent

    return ScoreDriftRaw(
        psi_log_odds=psi_lo,
        alert_rate=alert_rate,
        alert_ratio=alert_ratio,
        mean_entropy=mean_ent,
        entropy_ratio=entropy_ratio,
    )
