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

from tiresias.config import StreamConfig

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
            "retrain_count_per_seed": {int(k): v for k, v in retrain_count_per_seed.to_dict().items()},
            "time_averaged_recall_per_seed": {int(k): v for k, v in time_avg_recall_per_seed.to_dict().items()},
        }

    # Detection delay and false alarms, per (scenario, severity, strategy)
    for (scenario, severity, strategy), g in window_log.groupby(group_cols):
        events = events_by_scenario.get(f"{scenario}_{severity}", [])
        onsets = [e["window"] for e in events if e["kind"] == "onset"]

        # Keyed by seed (using the first onset event only, when there is
        # more than one) so label-free and backstop delays can be paired
        # for a Wilcoxon test (H1): a flat, possibly-unequal-length list of
        # delays loses which seed each value came from, so pairing by
        # position would silently misalign if a seed is missing an alarm.
        delay_by_seed_lf: dict = {}
        delay_by_seed_bs: dict = {}
        for seed, g_seed in g.groupby("seed"):
            g_seed = g_seed.sort_values("t")
            for onset in onsets[:1]:
                d_lf = _first_alarm_after(g_seed, onset, "alarm_label_free")
                d_bs = _first_alarm_after(g_seed, onset, "alarm_backstop")
                if d_lf is not None:
                    delay_by_seed_lf[int(seed)] = d_lf - onset
                if d_bs is not None:
                    delay_by_seed_bs[int(seed)] = d_bs - onset

        delays_label_free = list(delay_by_seed_lf.values())
        delays_backstop = list(delay_by_seed_bs.values())
        paired_seeds = sorted(set(delay_by_seed_lf) & set(delay_by_seed_bs))
        paired_lf = [delay_by_seed_lf[s] for s in paired_seeds]
        paired_bs = [delay_by_seed_bs[s] for s in paired_seeds]

        key = f"{scenario}|{severity}|{strategy}"
        summary["detection"][key] = {
            "n_events": len(onsets),
            "label_free_delay_median": float(np.median(delays_label_free)) if delays_label_free else None,
            "label_free_delay_values": delays_label_free,
            "backstop_delay_median": float(np.median(delays_backstop)) if delays_backstop else None,
            "backstop_delay_values": delays_backstop,
            "delay_by_seed_lf": delay_by_seed_lf,
            "delay_by_seed_bs": delay_by_seed_bs,
            "paired_seeds": paired_seeds,
            "paired_lf": paired_lf,
            "paired_bs": paired_bs,
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


def paired_wilcoxon(a: list, b: list) -> dict:
    """Paired Wilcoxon signed-rank test, a vs b, plus a simple effect size
    (matched-pairs rank-biserial correlation). Returns None fields if there
    are too few pairs or every pair is tied (scipy raises in both cases)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b) or len(a) < 2:
        return {"n": len(a), "p_value": None, "statistic": None, "effect_size": None}
    diffs = a - b
    if np.all(diffs == 0):
        return {"n": len(a), "p_value": 1.0, "statistic": 0.0, "effect_size": 0.0}
    try:
        res = sp_stats.wilcoxon(a, b)
        n_nonzero = np.sum(diffs != 0)
        effect = float(2 * res.statistic / (n_nonzero * (n_nonzero + 1)) - 1) if n_nonzero > 0 else None
        return {"n": len(a), "p_value": float(res.pvalue), "statistic": float(res.statistic), "effect_size": effect}
    except ValueError as e:
        return {"n": len(a), "p_value": None, "statistic": None, "effect_size": None, "error": str(e)}


def judge_hypotheses(summary: dict, cfg: StreamConfig | None = None) -> dict:
    """PRD Section 2.3's H1-H5, judged only from results/summary.json
    numbers, never adjusted after seeing them (PRD rule)."""
    cfg = cfg or StreamConfig()
    verdicts = {}

    # H1: on S1/S2/S3, label-free alarms at least D/2 windows earlier
    # (median) than the backstop, paired Wilcoxon over seeds.
    h1_scenarios = [("S1", "mild"), ("S1", "moderate"), ("S1", "severe"), ("S2", "moderate"), ("S3", "moderate")]
    h1_results = {}
    for scenario, severity in h1_scenarios:
        key = f"{scenario}|{severity}|M1"
        d = summary["detection"].get(key)
        if not d or not d["paired_seeds"]:
            continue
        lead_times = [bs - lf for lf, bs in zip(d["paired_lf"], d["paired_bs"])]
        test = paired_wilcoxon(d["paired_bs"], d["paired_lf"])
        h1_results[f"{scenario}_{severity}"] = {
            "median_lead_time": float(np.median(lead_times)),
            "target": cfg.label_delay / 2,
            "meets_target": bool(float(np.median(lead_times)) >= cfg.label_delay / 2),
            "wilcoxon": test,
        }
    verdicts["H1"] = {
        "per_scenario": h1_results,
        "supported": bool(h1_results and all(r["meets_target"] for r in h1_results.values())),
    }

    # H3: M1 retrain count <= 60% of B1's, time-averaged recall within 3%
    # relative, averaged over scenarios (moderate severity where S1 has
    # multiple severities, to keep one number per scenario).
    scenarios = sorted({k.split("|")[0] for k in summary["groups"]})
    retrain_ratios, recall_ratios = [], []
    for scenario in scenarios:
        m1 = summary["groups"].get(f"{scenario}|moderate|M1")
        b1 = summary["groups"].get(f"{scenario}|moderate|B1")
        if m1 and b1 and b1["retrain_count_mean"] > 0:
            retrain_ratios.append(m1["retrain_count_mean"] / b1["retrain_count_mean"])
        if m1 and b1 and b1["time_averaged_recall_mean"]:
            recall_ratios.append(m1["time_averaged_recall_mean"] / b1["time_averaged_recall_mean"])
    h3_supported = bool(
        retrain_ratios
        and recall_ratios
        and float(np.mean(retrain_ratios)) <= 0.60
        and abs(1 - float(np.mean(recall_ratios))) <= 0.03
    )
    verdicts["H3"] = {
        "mean_retrain_ratio": float(np.mean(retrain_ratios)) if retrain_ratios else None,
        "mean_recall_ratio": float(np.mean(recall_ratios)) if recall_ratios else None,
        "supported": h3_supported,
    }

    # H4: S4 label-free fails to alarm (low detection rate is the expected,
    # desired result); backstop detects within D + 5 windows.
    h4 = summary["detection"].get("S4|moderate|M1", {})
    n_seeds_s4 = len(summary["groups"].get("S4|moderate|M1", {}).get("retrain_count_per_seed", {}))
    verdicts["H4"] = {
        "label_free_alarm_count": len(h4.get("label_free_delay_values", [])),
        "n_seeds": n_seeds_s4,
        "backstop_median_delay": h4.get("backstop_delay_median"),
        "backstop_target": cfg.label_delay + 5,
        "supported": bool(h4.get("backstop_delay_values") and h4.get("backstop_delay_median") is not None
                           and h4["backstop_delay_median"] <= cfg.label_delay + 5),
    }

    # H5: false alarm rate on S0 and S6 at or below 1 per 100 windows.
    h5_rates = {}
    for scenario in ["S0", "S6"]:
        for strategy in ["M0", "M1", "M1a", "M1b", "B3"]:
            key = f"{scenario}|moderate|{strategy}"
            fa = summary["false_alarms"].get(key)
            if fa and fa["rate_per_100"] is not None:
                h5_rates[key] = fa["rate_per_100"]
    verdicts["H5"] = {
        "rates": h5_rates,
        "supported": bool(h5_rates and all(r <= 1.0 for r in h5_rates.values())),
    }

    return verdicts


def save_summary(summary: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
