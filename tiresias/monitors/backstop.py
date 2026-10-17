"""Delayed-label backstop (PRD Section 6.6): recall at the alert budget on a
matured window, converted to a z-score against the calibration windows, fed
into its own one-sided CUSUM that looks for a sustained drop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tiresias.metrics import recall_at_budget


@dataclass
class BackstopCalibration:
    mean_recall: float
    std_recall: float


def calibrate_backstop(calibration_recalls: list[float]) -> BackstopCalibration:
    arr = np.asarray(calibration_recalls, dtype=float)
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 1e-6
    return BackstopCalibration(mean_recall=float(arr.mean()), std_recall=max(std, 1e-6))


def backstop_evidence(observed_recall: float, calib: BackstopCalibration) -> float:
    """Positive only when recall has dropped below the calibration mean."""
    z = (observed_recall - calib.mean_recall) / calib.std_recall
    return max(0.0, -z)
