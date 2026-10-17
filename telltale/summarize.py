"""Aggregation: turns the raw per-window log into the summary numbers PRD
Section 8's metrics ask for, grouped by (scenario, severity, strategy).
Used by both the pilot and the main run; the main run's output is what
`results/summary.json` is built from (PRD Section 9, "every number the
report cites").
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from telltale.config import StreamConfig

NO_DRIFT_SCENARIOS = {"S0", "S6"}


def _ci95(values: np.ndarray) -> tuple[float, float]:
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return (float("nan"), float("nan"))
    m = values.mean()
    se = sp_stats.sem(values)
    half = se * sp_stats.t.ppf(0.975, len(values) - 1)
    return (float(m - half), float(m + half))


def _first_alarm_after(df_seed: pd.DataFrame, event_window: int, column: str) -> int | None:
    after = df_seed[(df_seed["t"] >= event_window) & (df_seed[column])]
    if after.empty:
        return None
    return int(after["t"].min())


def summarize(window_log: pd.DataFrame, events_by_scenario: dict, cfg: StreamConfig | None = None) -> dict:
    cfg = cfg or StreamConfig()
    summary: dict = {"groups": {}, "detection": {}, "false_alarms": {}}

    group_cols = ["scenario", "severity", "strategy"]
    for (scenario, severity, strategy), g in window_log.groupby(group_cols):
        eval_g = g[g["t"] >= cfg.eval_start]

        time_avg_recall_per_seed = eval_g.groupby("seed")["recall"].mean()
        mean_ap_per_seed = eval_g.groupby("seed")["ap"].mean()
        retrain_count_per_seed = eval_g.groupby("seed")["retrain_executed"].sum()

        key = f"{scenario}|{severity}|{strategy}"
        ci_recall = _ci95(time_avg_recall_per_seed.values)
        ci_ap = _ci95(mean_ap_per_seed.values)

        summary["groups"][key] = {
            "scenario": scenario,
            "severity": severity,
            "strategy": strategy,
            "n_seeds": int(g["seed"].nunique()),
            "time_averaged_recall_mean": float(np.nanmean(time_avg_recall_per_seed.values)),
            "time_averaged_recall_ci95": ci_recall,
            "mean_ap_mean": float(np.nanmean(mean_ap_per_seed.values)),
            "mean_ap_ci95": ci_ap,
            "retrain_count_mean": float(retrain_count_per_seed.mean()),
            "retrain_count_per_seed": retrain_count_per_seed.to_dict(),
        }

    # Detection delay and false alarms, per (scenario, severity, strategy)
    for (scenario, severity, strategy), g in window_log.groupby(group_cols):
        events = events_by_scenario.get(f"{scenario}_{severity}", [])
        onsets = [e["window"] for e in events if e["kind"] == "onset"]

        delays_label_free, delays_backstop = [], []
        for seed, g_seed in g.groupby("seed"):
            g_seed = g_seed.sort_values("t")
            for onset in onsets:
                d_lf = _first_alarm_after(g_seed, onset, "alarm_label_free")
                d_bs = _first_alarm_after(g_seed, onset, "alarm_backstop")
                if d_lf is not None:
                    delays_label_free.append(d_lf - onset)
                if d_bs is not None:
                    delays_backstop.append(d_bs - onset)

        key = f"{scenario}|{severity}|{strategy}"
        summary["detection"][key] = {
            "n_events": len(onsets),
            "label_free_delay_median": float(np.median(delays_label_free)) if delays_label_free else None,
            "label_free_delay_values": delays_label_free,
            "backstop_delay_median": float(np.median(delays_backstop)) if delays_backstop else None,
            "backstop_delay_values": delays_backstop,
        }

        if scenario in NO_DRIFT_SCENARIOS:
            no_drift_g = g[g["t"] >= cfg.eval_start]
        else:
            no_drift_g = g[(g["t"] >= cfg.eval_start) & (g["t"] < min(onsets, default=cfg.T))]

        n_windows = len(no_drift_g)
        n_alarms = int(no_drift_g["alarm_label_free"].sum() + no_drift_g["alarm_backstop"].sum())
        summary["false_alarms"][key] = {
            "n_windows": n_windows,
            "n_alarms": n_alarms,
            "rate_per_100": (100.0 * n_alarms / n_windows) if n_windows else None,
        }

    return summary


def save_summary(summary: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
