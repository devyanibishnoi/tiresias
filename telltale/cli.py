"""Command line entry points (PRD Section 11.1).

Subcommands are filled in phase by phase as the PRD's build plan (Section 12)
progresses. A subcommand that is not implemented yet prints a clear message
and exits non-zero rather than pretending to succeed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from telltale.config import FEATURE_NAMES, StreamConfig
from telltale.data.events_io import save_events
from telltale.data.injector import VALID_SCENARIOS, scenario_events
from telltale.data.stream import generate_stream

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


def _not_implemented(name: str):
    def _run(_args: argparse.Namespace) -> None:
        print(f"telltale.cli {name}: not implemented yet (see PRD.md Section 12 for the build plan)")
        sys.exit(1)

    return _run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m telltale.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate-samples").set_defaults(func=cmd_generate_samples)
    sub.add_parser("tune").set_defaults(func=_not_implemented("tune"))

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.set_defaults(func=_not_implemented("run"))

    sub.add_parser("profile").set_defaults(func=_not_implemented("profile"))
    sub.add_parser("make-figures").set_defaults(func=_not_implemented("make-figures"))
    sub.add_parser("real-check").set_defaults(func=_not_implemented("real-check"))

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
