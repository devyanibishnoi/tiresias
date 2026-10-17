"""Strategies compared (PRD Section 7). A strategy is just a bundle of flags
telling the simulator which signals to monitor and which trigger decides
when to retrain; every strategy shares the same model class, retrain
window, label vault and cooldown (PRD: "They differ only in when they
retrain").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    use_label_free: bool = False
    use_input: bool = False
    use_score: bool = False
    use_backstop: bool = False
    fixed_schedule: bool = False
    oracle: bool = False


STRATEGIES: dict[str, StrategyConfig] = {
    "B0": StrategyConfig("B0"),
    "B1": StrategyConfig("B1", fixed_schedule=True),
    "B2": StrategyConfig("B2", oracle=True),
    "B3": StrategyConfig("B3", use_backstop=True),
    "M0": StrategyConfig("M0", use_label_free=True, use_input=True, use_score=True, use_backstop=False),
    "M1": StrategyConfig("M1", use_label_free=True, use_input=True, use_score=True, use_backstop=True),
    "M1a": StrategyConfig("M1a", use_label_free=True, use_input=True, use_score=False, use_backstop=True),
    "M1b": StrategyConfig("M1b", use_label_free=True, use_input=False, use_score=True, use_backstop=True),
}
