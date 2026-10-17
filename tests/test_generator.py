"""Generator acceptance tests, PRD Section 5.3. All checks are run over the
tuning seeds only (100-104), aggregated by mean, never the evaluation seeds.
"""

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from tiresias.config import StreamConfig
from tiresias.data.events_io import load_events, save_events
from tiresias.data.injector import scenario_events
from tiresias.data.stream import generate_stream
from tiresias.models import fit_model
from tiresias.monitors.stats import psi

CFG = StreamConfig()
TUNING_SEEDS = CFG.tuning_seeds


def _ap(stream, model, t_lo, t_hi):
    X = stream.X[t_lo : t_hi + 1].reshape(-1, CFG.d)
    y = stream.y[t_lo : t_hi + 1].reshape(-1)
    p = model.predict_proba(X)[:, 1]
    return average_precision_score(y, p)


def _fit_model(seed):
    s0 = generate_stream("S0", seed, cfg=CFG)
    Xtr = s0.X[CFG.train_start : CFG.train_end + 1].reshape(-1, CFG.d)
    ytr = s0.y[CFG.train_start : CFG.train_end + 1].reshape(-1)
    model = fit_model(Xtr, ytr, random_state=0)
    return model, s0


@pytest.fixture(scope="module")
def fitted_models():
    return {seed: _fit_model(seed) for seed in TUNING_SEEDS}


def test_reproducibility_same_seed_same_stream():
    s1 = generate_stream("S1", seed=100, severity="moderate", cfg=CFG)
    s2 = generate_stream("S1", seed=100, severity="moderate", cfg=CFG)
    assert np.array_equal(s1.X, s2.X)
    assert np.array_equal(s1.y, s2.y)


def test_stable_period_average_precision_in_range(fitted_models):
    aps = []
    for seed, (model, s0) in fitted_models.items():
        aps.append(_ap(s0, model, CFG.ref_start, CFG.ref_end))
    mean_ap = np.mean(aps)
    assert 0.60 <= mean_ap <= 0.85, f"stable mean AP {mean_ap:.3f} out of range"


def _relative_drop(fitted_models, scenario, severity=None, window_lo=90, window_hi=149):
    drops = []
    for seed, (model, s0) in fitted_models.items():
        ap_stable = _ap(s0, model, CFG.ref_start, CFG.ref_end)
        kwargs = {"severity": severity} if severity else {}
        s = generate_stream(scenario, seed, cfg=CFG, **kwargs)
        ap_drift = _ap(s, model, window_lo, window_hi)
        drops.append((ap_stable - ap_drift) / ap_stable)
    return np.mean(drops)


def test_s1_severity_ordering_and_targets(fitted_models):
    mild = _relative_drop(fitted_models, "S1", "mild")
    moderate = _relative_drop(fitted_models, "S1", "moderate")
    severe = _relative_drop(fitted_models, "S1", "severe")

    assert 0.03 <= mild <= 0.15, f"mild drop {mild:.3f} not about 5-10 percent"
    assert mild < moderate < severe, (mild, moderate, severe)
    assert severe >= 0.25, f"severe drop {severe:.3f} below 25 percent floor"


def test_s4_concept_drift_unchanged_marginals_but_lower_ap(fitted_models):
    seed = TUNING_SEEDS[0]
    model, s0 = fitted_models[seed]
    s4 = generate_stream("S4", seed, cfg=CFG)

    for feat in range(CFG.d):
        ref = s0.X[CFG.ref_start : CFG.ref_end + 1, :, feat].ravel()
        cur = s4.X[90:150, :, feat].ravel()
        value = psi(ref, cur)
        assert value < 0.25, f"feature {feat} PSI {value:.3f} too high for S4 (should be near null)"

    ap_drop = _relative_drop(fitted_models, "S4")
    assert ap_drop >= 0.25, f"S4 AP drop {ap_drop:.3f} below 25 percent floor"


def test_s6_seasonality_visible_but_low_performance_impact(fitted_models):
    seed = TUNING_SEEDS[0]
    model, s0 = fitted_models[seed]
    s6 = generate_stream("S6", seed, cfg=CFG)

    # Check a single window near the seasonal peak (period 7, peak near t=93)
    # rather than pooling many windows, since the sinusoid averages to zero
    # net shift over a full period.
    ref = s0.X[CFG.ref_start : CFG.ref_end + 1, :, 14].ravel()
    cur = s6.X[93, :, 14].ravel()
    assert psi(ref, cur) > 0.1, "S6 should visibly move the amount feature marginal"

    ap_change = _relative_drop(fitted_models, "S6")
    assert abs(ap_change) <= 0.05, f"S6 performance impact {ap_change:.3f} exceeds 5 percent"


def test_event_times_round_trip(tmp_path):
    events = scenario_events("S3", "moderate")
    path = tmp_path / "s3_events.json"
    save_events(path, events)
    loaded = load_events(path)
    assert loaded == events
