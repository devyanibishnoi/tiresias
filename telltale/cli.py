"""Command line entry points (PRD Section 11.1).

Subcommands are filled in phase by phase as the PRD's build plan (Section 12)
progresses. A subcommand that is not implemented yet prints a clear message
and exits non-zero rather than pretending to succeed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np  # noqa: F401 (used below and by cmd_tune's grid)

import yaml

from telltale.config import FEATURE_NAMES, StreamConfig
from telltale.data.events_io import save_events
from telltale.data.injector import VALID_SCENARIOS, scenario_events
from telltale.data.stream import generate_stream
from telltale.metrics import recall_at_budget
from telltale.models import fit_model
from telltale.monitors.backstop import backstop_evidence, calibrate_backstop
from telltale.tuning import compute_evidence_stream, false_alarm_rate_per_100, grid_search

RESULTS_DIR = Path("results")

SAMPLE_SEED = 0
SAMPLE_DIR = Path("data/sim_samples")
FIGURE_DIR = Path("results/figures")

# A representative sample keeps a handful of windows spanning reference,
# pre-onset, just-after-onset, mid-drift and late-drift, and a subsample of
# transactions per window, so the file stays small enough to commit while
# still showing the drift shape (PRD 11: "small compressed representative
# streams, one per scenario").
SAMPLE_WINDOWS = [20, 29, 55, 61, 75, 95, 125, 145]
SAMPLE_N_PER_WINDOW = 300


def cmd_generate_samples(_args: argparse.Namespace) -> None:
    cfg = StreamConfig()
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    (SAMPLE_DIR / "events").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SAMPLE_SEED)

    for scenario in VALID_SCENARIOS:
        severities = ["mild", "moderate", "severe"] if scenario in ("S1",) else ["moderate"]
        for severity in severities:
            stream = generate_stream(scenario, SAMPLE_SEED, severity=severity, cfg=cfg)
            idx = rng.choice(cfg.N, size=SAMPLE_N_PER_WINDOW, replace=False)
            X_sample = stream.X[SAMPLE_WINDOWS][:, idx, :].astype(np.float32)
            y_sample = stream.y[SAMPLE_WINDOWS][:, idx].astype(np.int8)

            out_path = SAMPLE_DIR / f"{scenario}_{severity}_seed{SAMPLE_SEED}.npz"
            np.savez_compressed(
                out_path,
                X=X_sample,
                y=y_sample,
                windows=np.array(SAMPLE_WINDOWS),
            )
            save_events(
                SAMPLE_DIR / "events" / f"{scenario}_{severity}.json",
                scenario_events(scenario, severity),
            )
            print(f"wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")

    _plot_marginals_check(cfg)


def _plot_marginals_check(cfg: StreamConfig) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    s0 = generate_stream("S0", SAMPLE_SEED, cfg=cfg)
    s1 = generate_stream("S1", SAMPLE_SEED, severity="severe", cfg=cfg)
    s4 = generate_stream("S4", SAMPLE_SEED, cfg=cfg)

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    axes[0, 0].hist(s0.X[25, :, 0], bins=40, alpha=0.6, label="reference (window 25)")
    axes[0, 0].hist(s1.X[120, :, 0], bins=40, alpha=0.6, label="S1 severe (window 120)")
    axes[0, 0].set_title(f"{FEATURE_NAMES[0]}: covariate drift")
    axes[0, 0].legend(fontsize=8)

    axes[0, 1].hist(s0.X[25, :, 6], bins=40, alpha=0.6, label="reference (window 25)")
    axes[0, 1].hist(s4.X[120, :, 6], bins=40, alpha=0.6, label="S4 concept (window 120)")
    axes[0, 1].set_title(f"{FEATURE_NAMES[6]}: unchanged under S4")
    axes[0, 1].legend(fontsize=8)

    axes[1, 0].hist(s0.X[25, :, 14], bins=40, alpha=0.6, label="reference (window 25)")
    axes[1, 0].hist(s1.X[120, :, 14], bins=40, alpha=0.6, label="S1 severe (window 120)")
    axes[1, 0].set_title(f"{FEATURE_NAMES[14]}: unchanged under S1")
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].hist(s0.X[25, :, 1], bins=40, alpha=0.6, label="reference (window 25)")
    axes[1, 1].hist(s4.X[120, :, 1], bins=40, alpha=0.6, label="S4 concept (window 120)")
    axes[1, 1].set_title(f"{FEATURE_NAMES[1]}: unchanged under S4")
    axes[1, 1].legend(fontsize=8)

    fig.suptitle("Feature marginals before and after drift (sanity check)")
    fig.tight_layout()
    out_path = FIGURE_DIR / "phase1_feature_marginals_check.png"
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"wrote {out_path}")


def _backstop_null_stream(scenario: str, seed: int, cfg: StreamConfig):
    stream = generate_stream(scenario, seed, cfg=cfg)
    Xtr = stream.X[cfg.train_start : cfg.train_end + 1].reshape(-1, cfg.d)
    ytr = stream.y[cfg.train_start : cfg.train_end + 1].reshape(-1)
    model = fit_model(Xtr, ytr, random_state=0)

    calib_recalls = [
        recall_at_budget(stream.y[w], model.predict_proba(stream.X[w])[:, 1])
        for w in range(cfg.ref_start, cfg.ref_end + 1)
    ]
    calib = calibrate_backstop(calib_recalls)

    evs = []
    for w in range(cfg.eval_start, cfg.T):
        recall_w = recall_at_budget(stream.y[w], model.predict_proba(stream.X[w])[:, 1])
        evs.append(backstop_evidence(recall_w, calib))
    return np.array(evs)


def cmd_tune(_args: argparse.Namespace) -> None:
    cfg = StreamConfig()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("computing null evidence streams on tuning seeds (S0, S6)...")
    combined_arrays, input_arrays, score_arrays, backstop_arrays = [], [], [], []
    for scenario in ["S0", "S6"]:
        for seed in cfg.tuning_seeds:
            es = compute_evidence_stream(scenario, seed, cfg=cfg)
            combined_arrays.append(es.combined_evidence)
            input_arrays.append(es.input_evidence)
            score_arrays.append(es.score_evidence)
            backstop_arrays.append(_backstop_null_stream(scenario, seed, cfg))

    slack_grid = [round(x, 2) for x in np.arange(0.2, 3.01, 0.2)]
    height_grid = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20]

    # PRD 6.5's hard requirement is at most 1 per 100 windows; target half of
    # that here so the choice has a safety margin on the evaluation seeds,
    # which the tuning seeds never see.
    safety_target = 0.5
    combined_valid = grid_search(combined_arrays, slack_grid, height_grid, target_fa_per_100=safety_target)
    backstop_valid = grid_search(backstop_arrays, slack_grid, height_grid, target_fa_per_100=safety_target)

    if not combined_valid or not backstop_valid:
        print("no valid (slack, height) found meeting the 1-per-100 false alarm target")
        sys.exit(1)

    chosen_combined = combined_valid[0]
    chosen_backstop = backstop_valid[0]

    result = {
        "combined_cusum": chosen_combined,
        "backstop_cusum": chosen_backstop,
        "input_only_false_alarm_per_100": false_alarm_rate_per_100(
            input_arrays, chosen_combined["slack"], chosen_combined["height"]
        ),
        "score_only_false_alarm_per_100": false_alarm_rate_per_100(
            score_arrays, chosen_combined["slack"], chosen_combined["height"]
        ),
        "tuning_seeds": list(cfg.tuning_seeds),
    }

    out_path = RESULTS_DIR / "tuning.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out_path}")
    print(json.dumps(result, indent=2))
    print(
        "\nUpdate telltale/simulator.py's TUNED_CUSUM_* / TUNED_BACKSTOP_* constants "
        "if these differ from what is currently hardcoded there."
    )


def cmd_run(args: argparse.Namespace) -> None:
    from telltale.experiments import build_grid, run_grid, save_raw
    from telltale.summarize import save_summary, summarize

    with open(args.config) as f:
        config = yaml.safe_load(f)

    cfg = StreamConfig()
    name = config["name"]
    s1_all_severities = "s1_severity" not in config
    specs = build_grid(config["scenarios"], config["seeds"], config["strategies"], s1_all_severities=s1_all_severities)

    print(f"running {name}: {len(specs)} (scenario, severity, seed, strategy) combinations")
    out = run_grid(specs)
    print(f"done in {out['wall_seconds']:.1f}s")

    out_dir = RESULTS_DIR if name == "main" else RESULTS_DIR / name
    save_raw(out, out_dir=out_dir)

    summary = summarize(out["window_log"], out["events_by_scenario"], cfg=cfg)
    summary_path = out_dir / "summary.json"
    save_summary(summary, summary_path)
    print(f"wrote {summary_path}")

    if name == "pilot":
        _make_pilot_figure(out["window_log"], out_dir)


def _make_pilot_figure(window_log, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    s1 = window_log[(window_log["scenario"] == "S1") & (window_log["strategy"].isin(["B0", "B1", "M1"]))]

    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, g in s1.groupby("strategy"):
        mean_by_t = g.groupby("t")["ap"].mean()
        ax.plot(mean_by_t.index, mean_by_t.values, label=strategy)

    m1 = s1[s1["strategy"] == "M1"]
    alarm_t = m1[m1["alarm_label_free"]]["t"].unique()
    retrain_t = m1[m1["retrain_executed"]]["t"].unique()
    for t in alarm_t:
        ax.axvline(t, color="orange", alpha=0.3, linestyle="--")
    for t in retrain_t:
        ax.axvline(t, color="green", alpha=0.4, linestyle="-")

    ax.set_xlabel("window")
    ax.set_ylabel("average precision (mean over pilot seeds)")
    ax.set_title("Pilot: S1 moderate, performance over time (M1 alarms=orange, retrains=green)")
    ax.legend()
    fig.tight_layout()
    out_path = out_dir / "pilot_performance_over_time.png"
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"wrote {out_path}")


def cmd_profile(_args: argparse.Namespace) -> None:
    from dataclasses import asdict

    from telltale.profiling import run_profile

    result = run_profile()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "profiling.json"
    with open(out_path, "w") as f:
        json.dump(asdict(result), f, indent=2)
    print(f"wrote {out_path}")

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(result.window_sizes, [s * 1000 for s in result.monitor_seconds_per_window], marker="o")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("transactions per window")
    ax.set_ylabel("monitor time (ms)")
    ax.set_title("Scale-up: monitor runtime versus window size")
    fig.tight_layout()
    fig_path = FIGURE_DIR / "scale_up_runtime.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"wrote {fig_path}")


def cmd_make_figures(_args: argparse.Namespace) -> None:
    from telltale.figures import make_architecture_diagram, make_drift_taxonomy, make_label_delay_timeline

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    make_architecture_diagram(FIGURE_DIR / "architecture_diagram.png")
    make_drift_taxonomy(FIGURE_DIR / "drift_taxonomy.png")

    pilot_log_path = Path("results/pilot/per_window_log.csv.gz")
    if pilot_log_path.exists():
        import pandas as pd

        pilot_log = pd.read_csv(pilot_log_path)
        make_label_delay_timeline(pilot_log, StreamConfig(), FIGURE_DIR / "label_delay_timeline.png")
    else:
        print("skipping label-delay timeline: results/pilot/per_window_log.csv.gz not found, run the pilot first")

    print("figures written to", FIGURE_DIR)
    print("remaining data-dependent figures (performance over time, detection delay vs severity, "
          "retrain vs recall, ablation bars, false alarm rates, S4 failure, sensitivity, scale-up) "
          "are built once the main run and profiling exist; see telltale/figures.py")


def _not_implemented(name: str):
    def _run(_args: argparse.Namespace) -> None:
        print(f"telltale.cli {name}: not implemented yet (see PRD.md Section 12 for the build plan)")
        sys.exit(1)

    return _run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m telltale.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate-samples").set_defaults(func=cmd_generate_samples)
    sub.add_parser("tune").set_defaults(func=cmd_tune)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.set_defaults(func=cmd_run)

    sub.add_parser("profile").set_defaults(func=cmd_profile)
    sub.add_parser("make-figures").set_defaults(func=cmd_make_figures)
    sub.add_parser("real-check").set_defaults(func=_not_implemented("real-check"))

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
