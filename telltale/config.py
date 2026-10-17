"""Default stream and experiment parameters (PRD Section 5.1)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StreamConfig:
    T: int = 150
    N: int = 2000
    d: int = 20
    base_fraud_rate: float = 0.02
    train_start: int = 0
    train_end: int = 19
    ref_start: int = 20
    ref_end: int = 29
    eval_start: int = 30
    eval_end: int = 149
    label_delay: int = 7
    retrain_window: int = 20
    maturity_wait: int = 3
    fixed_schedule_K: int = 20
    tuning_seeds: tuple = tuple(range(100, 105))
    eval_seeds: tuple = tuple(range(0, 20))


# Features 0-13: continuous. 14-15: skewed positive (amount-like).
# 16-17: cyclic (hour sin/cos). 18-19: categorical-like integer codes.
N_CONTINUOUS = 14
N_SKEWED = 2
N_CYCLIC = 2
N_CATEGORICAL = 2

FEATURE_NAMES = (
    [f"cont_{i}" for i in range(N_CONTINUOUS)]
    + ["amount_1", "amount_2"]
    + ["hour_sin", "hour_cos"]
    + ["cat_1", "cat_2"]
)

# Fixed informative feature sets used by the fraud-generating function.
# Set A drives the label in the stable regime and in every covariate-drift
# scenario. Set B is swapped in for pure concept drift (S4) and mixed drift
# (S5): the inputs keep the same marginal distribution, only the mapping to
# the label changes.
INFORMATIVE_SET_A = [0, 1, 2, 3, 4, 5]
INFORMATIVE_SET_B = [6, 7, 8, 9, 10, 11]
WEIGHTS_A = [0.9, -0.8, 0.7, 0.6, -0.5, 0.5]
WEIGHTS_B = [0.85, -0.75, 0.65, -0.6, 0.55, -0.5]

# Features whose marginal is shifted by covariate-drift scenarios (S1,S2,S3).
COVARIATE_DRIFT_FEATURES = [0, 1, 2, 3]
