"""Null calibration sanity check, PRD Section 15.1 item 6: on S0 with the
tuning seeds, the share of windows above each raw signal's threshold should
be close to the 1 percent target the threshold was built for.
"""

import numpy as np

from tiresias.config import StreamConfig
from tiresias.data.stream import generate_stream
from tiresias.metrics import ALERT_BUDGET
from tiresias.models import fit_model
from tiresias.monitors.combiner import build_reference, compute_window_evidence

CFG = StreamConfig()


def test_raw_signal_exceedance_rate_near_one_percent():
    seed = CFG.tuning_seeds[0]
    s0 = generate_stream("S0", seed, cfg=CFG)

    Xtr = s0.X[CFG.train_start : CFG.train_end + 1].reshape(-1, CFG.d)
    ytr = s0.y[CFG.train_start : CFG.train_end + 1].reshape(-1)
    model = fit_model(Xtr, ytr, random_state=0)

    Xref = s0.X[CFG.ref_start : CFG.ref_end + 1].reshape(-1, CFG.d)
    scores_ref = model.predict_proba(Xref)[:, 1]
    rng = np.random.default_rng(seed)
    reference = build_reference(Xref, scores_ref, budget=ALERT_BUDGET, window_n=CFG.N, rng=rng)

    exceed = {"input_drift": 0, "psi_log_odds": 0, "alert_ratio": 0, "entropy_ratio": 0}
    n_windows = 0
    for t in range(CFG.eval_start, CFG.T):
        Xt = s0.X[t]
        scores_t = model.predict_proba(Xt)[:, 1]
        ev = compute_window_evidence(reference, Xt, scores_t)
        n_windows += 1
        if reference.thresholds.evidence("input_drift", ev.input_result.value) > 1.0:
            exceed["input_drift"] += 1
        if reference.thresholds.evidence("psi_log_odds", ev.score_raw.psi_log_odds) > 1.0:
            exceed["psi_log_odds"] += 1
        if reference.thresholds.evidence("alert_ratio", ev.score_raw.alert_ratio) > 1.0:
            exceed["alert_ratio"] += 1
        if reference.thresholds.evidence("entropy_ratio", ev.score_raw.entropy_ratio) > 1.0:
            exceed["entropy_ratio"] += 1

    for name, count in exceed.items():
        rate = count / n_windows
        assert rate <= 0.15, f"{name} exceedance rate {rate:.3f} far above the 1 percent target"
