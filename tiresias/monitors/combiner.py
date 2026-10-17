"""Evidence combiner (PRD Section 6.5): ties the input drift monitor and the
score monitor to calibrated null thresholds and produces a single evidence
value per window, E_t = max(input evidence, score evidence). Also exposes
the input-only and score-only evidence streams for the M1a/M1b ablation.

Reference scores must come from the same model whose scores are later
compared against them. Before the first retrain, the deployed model (fit on
the training windows) scoring the held-out calibration windows is already
honest out-of-sample, so no extra cross-validation is needed there. After a
retrain, the new reference is built from the same matured windows the model
was just refit on, which does need the blocked out-of-fold scores from
tiresias.models.Retrainer (PRD 6.6): using the retrained model's own
in-sample predictions on its own training window would be overconfident and
would flag drift immediately after every retrain even with none present.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from tiresias.monitors.calibration import (
    N_NULL_DRAWS,
    SignalThresholds,
    bootstrap_window_index_matrix,
    psi_null_draws,
    ratio_null_draws,
    threshold_from_null,
)
from tiresias.monitors.input_drift import (
    FeatureBins,
    InputDriftResult,
    input_drift_null_draws,
    input_drift_value_fast,
    prepare_input_drift_reference,
)
from tiresias.monitors.score_drift import log_odds, operating_threshold, predictive_entropy, score_drift_raw
from tiresias.monitors.stats import prepare_bins

SIGNAL_NAMES = ["input_drift", "psi_log_odds", "alert_ratio", "entropy_ratio"]


@dataclass
class Reference:
    X: np.ndarray
    scores: np.ndarray  # scores aligned row-wise with X, honest out-of-sample
    budget: float
    operating_threshold: float
    alert_rate: float
    mean_entropy: float
    thresholds: SignalThresholds = field(default_factory=SignalThresholds)
    input_bins: FeatureBins | None = None
    log_odds_bins: tuple | None = None


def build_reference(
    X: np.ndarray,
    scores: np.ndarray,
    budget: float,
    window_n: int,
    rng: np.random.Generator,
    n_draws: int = N_NULL_DRAWS,
) -> Reference:
    thresh = operating_threshold(scores, budget)
    alert_rate = float((scores > thresh).mean())
    mean_entropy = float(predictive_entropy(scores).mean())

    ref = Reference(
        X=X,
        scores=scores,
        budget=budget,
        operating_threshold=thresh,
        alert_rate=alert_rate,
        mean_entropy=mean_entropy,
    )

    pool_size = len(scores)
    idx_matrix = bootstrap_window_index_matrix(pool_size, window_n, n_draws, rng)

    log_odds_scores = log_odds(scores)
    entropy_pool = predictive_entropy(scores)
    alert_indicator = (scores > thresh).astype(float)

    draws_input = input_drift_null_draws(X, idx_matrix)
    draws_psi = psi_null_draws(log_odds_scores, idx_matrix)
    draws_alert = ratio_null_draws(alert_indicator, idx_matrix, alert_rate)
    draws_entropy = ratio_null_draws(entropy_pool, idx_matrix, mean_entropy)

    ref.thresholds.thresholds = {
        "input_drift": threshold_from_null(draws_input),
        "psi_log_odds": threshold_from_null(draws_psi),
        "alert_ratio": threshold_from_null(draws_alert),
        "entropy_ratio": threshold_from_null(draws_entropy),
    }

    ref.input_bins = prepare_input_drift_reference(X)
    ref.log_odds_bins = prepare_bins(log_odds_scores)
    return ref


@dataclass
class WindowEvidence:
    input_evidence: float
    score_evidence: float
    combined: float
    input_result: InputDriftResult
    score_raw: object


def compute_window_evidence(reference: Reference, window_X: np.ndarray, window_scores: np.ndarray) -> WindowEvidence:
    input_result = input_drift_value_fast(reference.input_bins, window_X)
    input_evidence = reference.thresholds.evidence("input_drift", input_result.value)

    score_raw = score_drift_raw(
        reference.scores,
        window_scores,
        reference.operating_threshold,
        reference.alert_rate,
        reference.mean_entropy,
        log_odds_bins=reference.log_odds_bins,
    )
    score_evidence = max(
        reference.thresholds.evidence("psi_log_odds", score_raw.psi_log_odds),
        reference.thresholds.evidence("alert_ratio", score_raw.alert_ratio),
        reference.thresholds.evidence("entropy_ratio", score_raw.entropy_ratio),
    )

    return WindowEvidence(
        input_evidence=input_evidence,
        score_evidence=score_evidence,
        combined=max(input_evidence, score_evidence),
        input_result=input_result,
        score_raw=score_raw,
    )
