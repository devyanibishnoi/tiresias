"""Label vault: releases the labels of window t-D only at time t.

Any attempt to read labels for a window that has not matured yet raises
LeakageError. This is the enforcement point for PRD Section 0 rule 4 and
Section 15.1 item 4 (the leakage guard).
"""

from __future__ import annotations

import numpy as np


class LeakageError(RuntimeError):
    pass


class LabelVault:
    def __init__(self, y: np.ndarray, label_delay: int):
        """y: (T, N) hidden ground-truth labels for the whole stream.
        label_delay: D, the number of windows a label stays hidden."""
        self._y = y
        self.label_delay = label_delay

    def get(self, window: int, now: int) -> np.ndarray:
        """Return the labels for `window`, as observed at time `now`.

        Raises LeakageError if `window` has not matured by `now` (i.e. if
        now - window < label_delay).
        """
        if now - window < self.label_delay:
            raise LeakageError(
                f"window {window} labels requested at t={now}, "
                f"but they only mature at t={window + self.label_delay}"
            )
        if window < 0 or window >= self._y.shape[0]:
            raise IndexError(f"window {window} out of range")
        return self._y[window]

    def matured_windows(self, now: int) -> list[int]:
        """All window indices whose labels have matured as of `now`."""
        return [w for w in range(min(now + 1, self._y.shape[0])) if now - w >= self.label_delay]
