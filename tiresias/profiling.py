"""Timing and scale-up measurements (PRD Section 9 item 7, Section 13.2
component sheet, Section 14.5 scale-up note).
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass

import numpy as np

from tiresias.config import StreamConfig
from tiresias.data.stream import generate_stream
from tiresias.metrics import ALERT_BUDGET
from tiresias.models import Retrainer, fit_model
from tiresias.monitors.combiner import build_reference, compute_window_evidence

WINDOW_SIZES = [1_000, 2_000, 10_000, 50_000, 200_000, 1_000_000]


@dataclass
class ProfileResult:
    window_sizes: list
    monitor_seconds_per_window: list
    monitor_memory_peak_kb: list
    retrain_seconds_with_oof: float
    retrain_seconds_without_oof: float
    throughput_tx_per_second: list


def profile_monitor_at_size(n: int, d: int = 20, n_reps: int = 5) -> tuple[float, float]:
    rng = np.random.default_rng(0)
    X_ref = rng.normal(size=(2000, d))
    scores_ref = rng.uniform(0, 1, size=2000)
    ref_rng = np.random.default_rng(1)
    reference = build_reference(X_ref, scores_ref, budget=ALERT_BUDGET, window_n=2000, rng=ref_rng)

    X_window = rng.normal(size=(n, d))
    scores_window = rng.uniform(0, 1, size=n)

    tracemalloc.start()
    t0 = time.time()
    for _ in range(n_reps):
        compute_window_evidence(reference, X_window, scores_window)
    elapsed = (time.time() - t0) / n_reps
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return elapsed, peak / 1024.0


def profile_retrain(cfg: StreamConfig | None = None) -> tuple[float, float]:
    cfg = cfg or StreamConfig()
    stream = generate_stream("S0", seed=0, cfg=cfg)
    recent = list(range(cfg.ref_start, cfg.ref_start + cfg.retrain_window))
    X_recent = stream.X[recent].reshape(-1, cfg.d)
    y_recent = stream.y[recent].reshape(-1)
    window_ids = np.repeat(np.array(recent), cfg.N)

    t0 = time.time()
    Retrainer(random_state=0).fit(X_recent, y_recent, window_ids, need_oof=True)
    with_oof = time.time() - t0

    t0 = time.time()
    Retrainer(random_state=0).fit(X_recent, y_recent, window_ids, need_oof=False)
    without_oof = time.time() - t0

    return with_oof, without_oof


def run_profile() -> ProfileResult:
    seconds, memory, throughput = [], [], []
    for n in WINDOW_SIZES:
        reps = 5 if n <= 50_000 else 2
        elapsed, peak_kb = profile_monitor_at_size(n, n_reps=reps)
        seconds.append(elapsed)
        memory.append(peak_kb)
        throughput.append(n / elapsed if elapsed > 0 else float("inf"))
        print(f"window_size={n}: {elapsed*1000:.1f} ms/window, {peak_kb:.0f} KB peak, {n/elapsed:.0f} tx/s")

    with_oof, without_oof = profile_retrain()
    print(f"retrain with OOF (6 fits): {with_oof:.2f}s, without OOF (1 fit): {without_oof:.2f}s")

    return ProfileResult(
        window_sizes=WINDOW_SIZES,
        monitor_seconds_per_window=seconds,
        monitor_memory_peak_kb=memory,
        retrain_seconds_with_oof=with_oof,
        retrain_seconds_without_oof=without_oof,
        throughput_tx_per_second=throughput,
    )
