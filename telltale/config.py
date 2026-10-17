"""Default stream and experiment parameters (PRD Section 5.1)."""

from dataclasses import dataclass


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
WEIGHTS_A = [2.85, -2.5, 2.2, 1.9, -1.6, 1.6]
WEIGHTS_B = [2.7, -2.4, 2.05, -1.9, 1.75, -1.6]

# Features whose marginal is shifted by covariate-drift scenarios (S1, S2, S3).
# The per-feature direction is chosen so that the shift is zero-sum against
# WEIGHTS_A (sum of weight_i * direction_i over these four features is 0):
# this is what makes it a pure covariate shift rather than a disguised
# prevalence shift. The model still degrades because it was fit on data that
# never covered this region of feature space, not because the ambient fraud
# rate moved.
COVARIATE_DRIFT_FEATURES = [0, 1, 2, 3]
COVARIATE_SHIFT_DIRECTION = [1.0, 1.125, 1.0, -1.16667]

SEVERITY_SIGMA = {"mild": 0.5, "moderate": 1.0, "severe": 2.0}

# Idiosyncratic logit noise added under covariate drift (S1, S2, S3, S5), by
# severity. Covariate drift moves the observed features into a region where
# the realised label depends more on unobserved factors than the model's
# training distribution assumed, which is what makes it hurt a correctly
# specified ranking model instead of only shifting the decision threshold (or
# the ambient fraud rate, which the shift direction is built to leave alone,
# see COVARIATE_SHIFT_DIRECTION). Tuned on the tuning seeds against the
# generator acceptance criteria of PRD Section 5.3 (see docs/decisions.md):
# mild gives about 5 to 10 percent relative AP drop, moderate falls between
# mild and severe, severe gives at least 25 percent.
COVARIATE_DRIFT_NOISE_STD = {"mild": 0.44, "moderate": 0.85, "severe": 1.1}
