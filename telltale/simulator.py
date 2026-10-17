"""The window loop and the label vault wiring (PRD Section 6.1, 6.6).

At each window t, in order: (1) the stream already holds X_t and the hidden
y_t, (2) the currently deployed model scores X_t, (3) true performance on
window t is recorded for evaluation only, (4) the label vault would release
window t-D's labels, (5) monitors compute signals from X_t and the scores
only (never from y_t), (6) the policy decides, (7) any retrain that is due
runs on matured windows only, (8) everything is logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from telltale.config import StreamConfig
from telltale.data.injector import DriftEvent
from telltale.data.label_vault import LabelVault
from telltale.data.stream import generate_stream
from telltale.metrics import ALERT_BUDGET, average_precision, recall_at_budget
from telltale.models import Retrainer, fit_model
from telltale.monitors.backstop import backstop_evidence, calibrate_backstop
from telltale.monitors.combiner import build_reference, compute_window_evidence
from telltale.monitors.cusum import CUSUM
from telltale.policies import STRATEGIES, StrategyConfig


@dataclass
class SimulationResult:
    records: list
    retrain_times: list  # list of (window, source)
    scenario: str
    severity: str
    seed: int
    strategy: str
    events: list = field(default_factory=list)


def simulate(
    scenario: str,
    seed: int,
    strategy_name: str,
    severity: str = "moderate",
    cfg: StreamConfig | None = None,
    cusum_slack: float = 0.5,
    cusum_height: float = 3.0,
    backstop_slack: float = 0.5,
    backstop_height: float = 3.0,
    model_seed: int = 0,
) -> SimulationResult:
    cfg = cfg or StreamConfig()
    strategy: StrategyConfig = STRATEGIES[strategy_name]
    stream = generate_stream(scenario, seed, severity=severity, cfg=cfg)
    label_vault = LabelVault(stream.y, cfg.label_delay)

    Xtr = stream.X[cfg.train_start : cfg.train_end + 1].reshape(-1, cfg.d)
    ytr = stream.y[cfg.train_start : cfg.train_end + 1].reshape(-1)
    model = fit_model(Xtr, ytr, random_state=model_seed)

    reference = None
    backstop_calib = None
    needs_monitor = strategy.use_label_free or strategy.use_backstop

    if needs_monitor:
        Xref = stream.X[cfg.ref_start : cfg.ref_end + 1].reshape(-1, cfg.d)
        scores_ref = model.predict_proba(Xref)[:, 1]
        rng_cal = np.random.default_rng(seed * 1000 + 1)
        reference = build_reference(Xref, scores_ref, budget=ALERT_BUDGET, window_n=cfg.N, rng=rng_cal)

    if strategy.use_backstop:
        calib_recalls = []
        for w in range(cfg.ref_start, cfg.ref_end + 1):
            Xw, yw = stream.X[w], stream.y[w]
            sw = model.predict_proba(Xw)[:, 1]
            calib_recalls.append(recall_at_budget(yw, sw))
        backstop_calib = calibrate_backstop(calib_recalls)

    cusum_combined = CUSUM(cusum_slack, cusum_height) if strategy.use_label_free else None
    backstop_cusum = CUSUM(backstop_slack, backstop_height) if strategy.use_backstop else None

    retrainer = Retrainer(random_state=model_seed + 1)
    retrain_count = 0
    retrain_times: list = []

    pending_retrain_at = None
    pending_source = None
    scores_served: dict[int, np.ndarray] = {}

    oracle_schedule = []
    if strategy.oracle:
        for ev in stream.events:
            if ev.kind == "onset":
                oracle_schedule.append(ev.window + cfg.label_delay + cfg.maturity_wait)
        oracle_schedule = sorted(oracle_schedule)
    oracle_idx = 0

    next_fixed_due = (cfg.train_end + 1 + cfg.fixed_schedule_K) if strategy.fixed_schedule else None

    records = []

    for t in range(cfg.T):
        Xt, yt = stream.X[t], stream.y[t]
        scores_t = model.predict_proba(Xt)[:, 1]
        scores_served[t] = scores_t

        ap_t = average_precision(yt, scores_t)
        recall_t = recall_at_budget(yt, scores_t)

        alarm_label_free = False
        input_ev = score_ev = combined_ev = float("nan")

        if strategy.use_label_free and t > cfg.ref_end:
            ev = compute_window_evidence(reference, Xt, scores_t)
            input_ev, score_ev = ev.input_evidence, ev.score_evidence
            if strategy.use_input and strategy.use_score:
                combined_ev = ev.combined
            elif strategy.use_input:
                combined_ev = ev.input_evidence
            else:
                combined_ev = ev.score_evidence
            alarm_label_free = cusum_combined.update(combined_ev)

        if alarm_label_free and pending_retrain_at is None:
            pending_retrain_at = t + cfg.label_delay + cfg.maturity_wait
            pending_source = "label_free"

        alarm_backstop = False
        if strategy.use_backstop:
            newly_matured = t - cfg.label_delay
            if newly_matured >= cfg.ref_start and newly_matured in scores_served:
                y_mat = label_vault.get(newly_matured, t)
                recall_mat = recall_at_budget(y_mat, scores_served[newly_matured])
                if not np.isnan(recall_mat):
                    bs_ev = backstop_evidence(recall_mat, backstop_calib)
                    alarm_backstop = backstop_cusum.update(bs_ev)

        if alarm_backstop:
            pending_retrain_at = t
            pending_source = "backstop"

        if strategy.fixed_schedule and next_fixed_due is not None and t == next_fixed_due:
            pending_retrain_at = t
            pending_source = "fixed"
            next_fixed_due = t + cfg.fixed_schedule_K if t + cfg.fixed_schedule_K < cfg.T else None

        if strategy.oracle and oracle_idx < len(oracle_schedule) and t == oracle_schedule[oracle_idx]:
            pending_retrain_at = t
            pending_source = "oracle"
            oracle_idx += 1

        retrain_executed = False
        retrain_source_this_step = None
        if pending_retrain_at is not None and t == pending_retrain_at:
            retrain_source_this_step = pending_source
            matured = label_vault.matured_windows(t)
            recent = matured[-cfg.retrain_window :]
            if len(recent) >= 1:
                X_recent = stream.X[recent].reshape(-1, cfg.d)
                y_recent = stream.y[recent].reshape(-1)
                window_ids_recent = np.repeat(np.array(recent), cfg.N)
                result = retrainer.fit(X_recent, y_recent, window_ids_recent)
                model = result.model
                retrain_count += 1
                retrain_times.append((t, pending_source))

                if needs_monitor:
                    rng_cal = np.random.default_rng(seed * 1000 + 1 + retrain_count)
                    reference = build_reference(
                        result.X, result.oof_scores, budget=ALERT_BUDGET, window_n=cfg.N, rng=rng_cal
                    )
                    if cusum_combined is not None:
                        cusum_combined.S = 0.0

                if strategy.use_backstop:
                    calib_recalls = []
                    for w in recent:
                        idx = window_ids_recent == w
                        calib_recalls.append(recall_at_budget(y_recent[idx], result.oof_scores[idx]))
                    backstop_calib = calibrate_backstop(calib_recalls)
                    backstop_cusum.S = 0.0

                retrain_executed = True
            pending_retrain_at = None
            pending_source = None

        records.append(
            dict(
                t=t,
                ap=ap_t,
                recall=recall_t,
                input_evidence=input_ev,
                score_evidence=score_ev,
                combined_evidence=combined_ev,
                alarm_label_free=alarm_label_free,
                alarm_backstop=alarm_backstop,
                retrain_executed=retrain_executed,
                retrain_source=retrain_source_this_step,
            )
        )

    return SimulationResult(
        records=records,
        retrain_times=retrain_times,
        scenario=scenario,
        severity=severity,
        seed=seed,
        strategy=strategy_name,
        events=stream.events,
    )
