"""Full synthetic stream assembly: ties the feature generator and the drift
injector together into a (T, N, d) feature array and a (T, N) hidden label
array, plus the ground truth drift events for the scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from telltale.config import INFORMATIVE_SET_A, INFORMATIVE_SET_B, StreamConfig, WEIGHTS_A, WEIGHTS_B
from telltale.data.generator import calibrate_intercept, fraud_logit, make_window_features, sigmoid
from telltale.data.injector import DriftEvent, scenario_events, scenario_window_params

_CALIBRATION_SEED = 999999


@lru_cache(maxsize=None)
def _intercept_for(informative_key: str, target_rate: float) -> float:
    idx, weights = (INFORMATIVE_SET_A, WEIGHTS_A) if informative_key == "A" else (INFORMATIVE_SET_B, WEIGHTS_B)
    return calibrate_intercept(_CALIBRATION_SEED, idx, weights, target_rate)


@dataclass
class StreamResult:
    X: np.ndarray  # (T, N, d)
    y: np.ndarray  # (T, N) int
    events: list[DriftEvent]
    scenario: str
    severity: str
    seed: int
    cfg: StreamConfig = field(repr=False, default_factory=StreamConfig)


def generate_stream(scenario: str, seed: int, severity: str = "moderate", cfg: StreamConfig | None = None) -> StreamResult:
    cfg = cfg or StreamConfig()
    rng = np.random.default_rng(seed)

    X = np.empty((cfg.T, cfg.N, cfg.d), dtype=float)
    y = np.empty((cfg.T, cfg.N), dtype=int)

    base_rate_A = _intercept_for("A", cfg.base_fraud_rate)
    base_rate_B = _intercept_for("B", cfg.base_fraud_rate)
    double_rate_A = _intercept_for("A", min(0.95, cfg.base_fraud_rate * 2))

    for t in range(cfg.T):
        params = scenario_window_params(scenario, t, severity)
        Xt = make_window_features(rng, cfg.N, mean_shift=params.mean_shift, amount_scale=params.amount_scale)

        if params.informative_idx is INFORMATIVE_SET_B:
            intercept = base_rate_B
        elif params.prevalence_override == "double":
            intercept = double_rate_A
        else:
            intercept = base_rate_A

        logit = fraud_logit(Xt, params.informative_idx, params.weights, intercept)
        if params.noise_std > 0:
            logit = logit + rng.normal(0.0, params.noise_std, size=cfg.N)
        p = sigmoid(logit)
        yt = (rng.random(cfg.N) < p).astype(int)

        X[t] = Xt
        y[t] = yt

    events = scenario_events(scenario, severity)
    return StreamResult(X=X, y=y, events=events, scenario=scenario, severity=severity, seed=seed, cfg=cfg)
