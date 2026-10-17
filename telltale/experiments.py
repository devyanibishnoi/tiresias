"""Runs, aggregation and statistics (PRD Section 9, Section 11).

Dispatches the (scenario, severity, seed, strategy) grid across worker
processes (each simulate() call is independent, CPU-bound, and the machine
has cores sitting idle during a single sequential run) and writes:
  - results/per_window_log.csv.gz: one row per (run, window).
  - results/retrains.csv: one row per retrain event.
  - results/summary.json: aggregated numbers the report cites.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


def _limit_worker_threads() -> None:
    """Each worker process runs one simulate() call at a time, so it should
    use exactly one thread for BLAS/OpenMP; without this, every worker's
    numpy/scikit-learn tries to use all cores internally, and N worker
    processes each spawning full-width thread pools oversubscribes the
    machine and makes process-level parallelism far less effective than it
    should be (measured: 8 workers gave only about a 2x speedup instead of
    something close to 8x). Must be set before numpy is imported in the
    worker, which is why this runs as the ProcessPoolExecutor initializer."""
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"

from telltale.config import StreamConfig
from telltale.policies import STRATEGIES
from telltale.simulator import simulate

RESULTS_DIR = Path("results")

# S1 is the only scenario run at all three severities in the main grid (PRD
# Section 9 item 2); every other scenario runs once at "moderate".
S1_SEVERITIES = ["mild", "moderate", "severe"]
P0_STRATEGIES = ["B0", "B1", "B2", "B3", "M0", "M1", "M1a", "M1b"]


@dataclass(frozen=True)
class RunSpec:
    scenario: str
    severity: str
    seed: int
    strategy: str


def build_grid(
    scenarios: list[str],
    seeds: list[int],
    strategies: list[str] = P0_STRATEGIES,
    s1_all_severities: bool = True,
) -> list[RunSpec]:
    specs = []
    for scenario in scenarios:
        if scenario == "S1" and s1_all_severities:
            severities = S1_SEVERITIES
        else:
            severities = ["moderate"]
        for severity in severities:
            for seed in seeds:
                for strategy in strategies:
                    specs.append(RunSpec(scenario, severity, seed, strategy))
    return specs


def _run_one(spec: RunSpec) -> dict:
    result = simulate(spec.scenario, spec.seed, spec.strategy, severity=spec.severity, cfg=StreamConfig())
    df = pd.DataFrame(result.records)
    df["scenario"] = spec.scenario
    df["severity"] = spec.severity
    df["seed"] = spec.seed
    df["strategy"] = spec.strategy

    retrains = pd.DataFrame(result.retrain_times, columns=["t", "source"])
    retrains["scenario"] = spec.scenario
    retrains["severity"] = spec.severity
    retrains["seed"] = spec.seed
    retrains["strategy"] = spec.strategy

    events = [
        {"window": e.window, "kind": e.kind, "drift_type": e.drift_type}
        for e in result.events
    ]

    return {
        "window_log": df,
        "retrains": retrains,
        "events": events,
        "spec": spec,
    }


# os.cpu_count() reports 12 on this machine, but a controlled CPU-bound
# benchmark (sum of squares, no I/O) showed only about 2x speedup from 8
# worker processes, meaning the sandboxed shell this runs in only has
# genuine parallelism across roughly 2 real cores regardless of what the OS
# reports. More workers than that mostly add process-switching overhead.
DEFAULT_MAX_WORKERS = 3


def run_grid(specs: list[RunSpec], max_workers: int | None = DEFAULT_MAX_WORKERS, progress_every: int = 20) -> dict:
    t0 = time.time()
    window_logs, retrain_logs = [], []
    events_by_scenario: dict[str, list] = {}
    n = len(specs)
    done = 0

    with ProcessPoolExecutor(max_workers=max_workers, initializer=_limit_worker_threads) as pool:
        futures = {pool.submit(_run_one, spec): spec for spec in specs}
        for fut in as_completed(futures):
            out = fut.result()
            window_logs.append(out["window_log"])
            retrain_logs.append(out["retrains"])
            key = out["spec"].scenario + "_" + out["spec"].severity
            if key not in events_by_scenario:
                events_by_scenario[key] = out["events"]
            done += 1
            if done % progress_every == 0 or done == n:
                elapsed = time.time() - t0
                print(f"[{done}/{n}] runs done, {elapsed:.1f}s elapsed, ~{elapsed / done * (n - done):.1f}s remaining")

    window_log_df = pd.concat(window_logs, ignore_index=True)
    retrain_df = pd.concat(retrain_logs, ignore_index=True)
    return {
        "window_log": window_log_df,
        "retrains": retrain_df,
        "events_by_scenario": events_by_scenario,
        "wall_seconds": time.time() - t0,
    }


def save_raw(run_output: dict, out_dir: Path = RESULTS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_output["window_log"].to_csv(out_dir / "per_window_log.csv.gz", index=False, compression="gzip")
    run_output["retrains"].to_csv(out_dir / "retrains.csv", index=False)
    with open(out_dir / "events_by_scenario.json", "w") as f:
        json.dump(run_output["events_by_scenario"], f, indent=2)
