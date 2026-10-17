"""Drift injector: per-window parameters and ground truth events for S0-S7.

Each scenario is a pure function of the window index t. It returns the
feature-mean shift (covariate drift), the amount seasonality scale (benign
seasonality) and which informative-feature set and weights generate the
label (concept drift). The simulator applies these to the generator in
telltale/data/generator.py. Ground truth event times are produced alongside
so detection delay can be computed exactly without touching the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from telltale.config import (
    COVARIATE_DRIFT_FEATURES,
    COVARIATE_DRIFT_NOISE_STD,
    COVARIATE_SHIFT_DIRECTION,
    INFORMATIVE_SET_A,
    INFORMATIVE_SET_B,
    N_CONTINUOUS,
    SEVERITY_SIGMA,
    WEIGHTS_A,
    WEIGHTS_B,
)

VALID_SCENARIOS = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]


@dataclass
class WindowParams:
    mean_shift: np.ndarray
    amount_scale: float
    informative_idx: list
    weights: list
    prevalence_override: float | None = None
    noise_std: float = 0.0


@dataclass
class DriftEvent:
    window: int
    kind: str  # "onset" or "offset"
    drift_type: str  # "sudden", "gradual", "recurring", "concept", "mixed", "prevalence"
    scenario: str
    severity: str | None = None


def _shift_vector(magnitude: float) -> np.ndarray:
    v = np.zeros(N_CONTINUOUS)
    for idx, direction in zip(COVARIATE_DRIFT_FEATURES, COVARIATE_SHIFT_DIRECTION):
        v[idx] = magnitude * direction
    return v


def scenario_window_params(
    scenario: str,
    t: int,
    severity: str = "moderate",
) -> WindowParams:
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}")

    sigma = SEVERITY_SIGMA[severity]
    base = WindowParams(
        mean_shift=np.zeros(N_CONTINUOUS),
        amount_scale=1.0,
        informative_idx=INFORMATIVE_SET_A,
        weights=WEIGHTS_A,
    )

    if scenario == "S0":
        return base

    if scenario == "S1":
        if t >= 60:
            base.mean_shift = _shift_vector(sigma)
            base.noise_std = COVARIATE_DRIFT_NOISE_STD[severity]
        return base

    if scenario == "S2":
        if t >= 60:
            frac = min(1.0, (t - 60) / 30.0)
            base.mean_shift = _shift_vector(sigma * frac)
            base.noise_std = COVARIATE_DRIFT_NOISE_STD[severity] * frac
        return base

    if scenario == "S3":
        on = (50 <= t <= 69) or (110 <= t <= 129)
        if on:
            base.mean_shift = _shift_vector(sigma)
            base.noise_std = COVARIATE_DRIFT_NOISE_STD[severity]
        return base

    if scenario == "S4":
        if t >= 60:
            base.informative_idx = INFORMATIVE_SET_B
            base.weights = WEIGHTS_B
        return base

    if scenario == "S5":
        if t >= 60:
            base.mean_shift = _shift_vector(sigma)
            base.noise_std = COVARIATE_DRIFT_NOISE_STD[severity]
            base.informative_idx = INFORMATIVE_SET_B
            base.weights = WEIGHTS_B
        return base

    if scenario == "S6":
        base.amount_scale = 1.0 + 0.3 * np.sin(2 * np.pi * t / 7.0)
        return base

    if scenario == "S7":
        if 60 <= t <= 80:
            base.prevalence_override = "double"
        return base

    raise AssertionError("unreachable")


def scenario_events(scenario: str, severity: str = "moderate") -> list[DriftEvent]:
    if scenario == "S0":
        return []
    if scenario == "S1":
        return [DriftEvent(60, "onset", "sudden", scenario, severity)]
    if scenario == "S2":
        return [DriftEvent(60, "onset", "gradual", scenario, severity)]
    if scenario == "S3":
        return [
            DriftEvent(50, "onset", "recurring", scenario, severity),
            DriftEvent(70, "offset", "recurring", scenario, severity),
            DriftEvent(110, "onset", "recurring", scenario, severity),
        ]
    if scenario == "S4":
        return [DriftEvent(60, "onset", "concept", scenario, severity)]
    if scenario == "S5":
        return [DriftEvent(60, "onset", "mixed", scenario, severity)]
    if scenario == "S6":
        return []
    if scenario == "S7":
        return [
            DriftEvent(60, "onset", "prevalence", scenario, severity),
            DriftEvent(81, "offset", "prevalence", scenario, severity),
        ]
    raise ValueError(f"unknown scenario {scenario}")
