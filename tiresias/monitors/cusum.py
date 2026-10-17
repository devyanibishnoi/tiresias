"""One-sided CUSUM (PRD Section 6.5, Page 1954): accumulate the excess of
evidence over a slack value, never let the sum fall below zero, alarm when
the sum passes a height h. After an alarm, reset to zero and ignore new
alarms for a cooldown window.
"""

from __future__ import annotations

DEFAULT_COOLDOWN = 3


class CUSUM:
    def __init__(self, slack: float, height: float, cooldown: int = DEFAULT_COOLDOWN):
        self.slack = slack
        self.height = height
        self.cooldown = cooldown
        self.S = 0.0
        self._cooldown_remaining = 0

    def update(self, evidence: float) -> bool:
        """Advance the CUSUM by one window's evidence. Returns True if an
        alarm fires on this step."""
        self.S = max(0.0, self.S + evidence - self.slack)

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return False

        if self.S > self.height:
            self.S = 0.0
            self._cooldown_remaining = self.cooldown
            return True

        return False
