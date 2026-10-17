"""CUSUM parameter tuning (PRD Section 6.5, Phase 3): choose slack and
height on the tuning seeds so the false alarm rate on S0 and S6 is at most 1
per 100 windows.

Evidence is computed once per (scenario, seed) with a fixed initial model
and reference (no retrains: S0 and S6 have no true drift, so a false-alarm
calibration run should not need one), then many (slack, height) pairs are
tried cheaply by replaying a plain CUSUM over the same cached evidence
array instead of re-running the simulator per grid point.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tiresias.config import StreamConfig
from tiresias.data.stream import generate_stream
from tiresias.metrics import ALERT_BUDGET
from tiresias.models import fit_model
from tiresias.monitors.combiner import build_reference, compute_window_evidence
from tiresias.monitors.cusum import CUSUM


@dataclass
class EvidenceStream:
    scenario: str
    seed: int
    input_evidence: np.ndarray
    score_evidence: np.ndarray
    combined_evidence: np.ndarray


def compute_evidence_stream(scenario: str, seed: int, cfg: StreamConfig, severity: str = "moderate") -> EvidenceStream:
    stream = generate_stream(scenario, seed, severity=severity, cfg=cfg)

    Xtr = stream.X[cfg.train_start : cfg.train_end + 1].reshape(-1, cfg.d)
    ytr = stream.y[cfg.train_start : cfg.train_end + 1].reshape(-1)
    model = fit_model(Xtr, ytr, random_state=0)

    Xref = stream.X[cfg.ref_start : cfg.ref_end + 1].reshape(-1, cfg.d)
    scores_ref = model.predict_proba(Xref)[:, 1]
    rng = np.random.default_rng(seed * 1000 + 1)
    reference = build_reference(Xref, scores_ref, budget=ALERT_BUDGET, window_n=cfg.N, rng=rng)

    input_ev, score_ev, combined_ev = [], [], []
    for t in range(cfg.ref_end + 1, cfg.T):
        Xt = stream.X[t]
        scores_t = model.predict_proba(Xt)[:, 1]
        ev = compute_window_evidence(reference, Xt, scores_t)
        input_ev.append(ev.input_evidence)
        score_ev.append(ev.score_evidence)
        combined_ev.append(ev.combined)

    return EvidenceStream(
        scenario=scenario,
        seed=seed,
        input_evidence=np.array(input_ev),
        score_evidence=np.array(score_ev),
        combined_evidence=np.array(combined_ev),
    )


def false_alarm_rate_per_100(evidence_arrays: list[np.ndarray], slack: float, height: float) -> float:
    total_alarms = 0
    total_windows = 0
    for arr in evidence_arrays:
        cusum = CUSUM(slack, height)
        total_alarms += sum(cusum.update(e) for e in arr)
        total_windows += len(arr)
    return 100.0 * total_alarms / total_windows


def mean_alarm_count(evidence_arrays: list[np.ndarray], slack: float, height: float) -> float:
    counts = []
    for arr in evidence_arrays:
        cusum = CUSUM(slack, height)
        counts.append(sum(cusum.update(e) for e in arr))
    return float(np.mean(counts))


def grid_search(
    null_evidence_arrays: list[np.ndarray],
    slack_grid: list[float],
    height_grid: list[float],
    target_fa_per_100: float = 1.0,
) -> list[dict]:
    """Every (slack, height) pair meeting the false alarm target, sorted by
    height ascending (smaller height -> faster detection, all else equal),
    then slack ascending."""
    results = []
    for slack in slack_grid:
        for height in height_grid:
            rate = false_alarm_rate_per_100(null_evidence_arrays, slack, height)
            results.append({"slack": slack, "height": height, "false_alarm_per_100": rate})
    valid = [r for r in results if r["false_alarm_per_100"] <= target_fa_per_100]
    valid.sort(key=lambda r: (r["height"], r["slack"]))
    return valid
