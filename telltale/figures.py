"""Report figures that do not depend on the main run's results: the
architecture diagram, the drift taxonomy sketch, and the label-delay
timeline (built from the pilot run). Data-dependent figures (performance
over time on the full main run, detection delay vs severity, retrain count
vs recall, ablation bars, false alarm rates, the S4 failure figure,
sensitivity, scale-up) are built once `results/summary.json` exists; see
`telltale/cli.py`'s `cmd_make_figures` for what still needs to be added
there once the main run completes.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from telltale.config import StreamConfig


def _box(ax, xy, w, h, text, fc="#dbe7f3"):
    rect = mpatches.FancyBboxPatch(
        xy, w, h, boxstyle="round,pad=0.02", linewidth=1, edgecolor="black", facecolor=fc
    )
    ax.add_patch(rect)
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=8, wrap=True)


def _arrow(ax, p0, p1):
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="->", lw=1.2))


def make_architecture_diagram(out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("telltale architecture (PRD Section 4.1)", fontsize=11)

    _box(ax, (0.3, 8.6), 2.0, 0.9, "Stream source\n+ drift injector\n(scenario S0-S7)")
    _box(ax, (3.0, 8.6), 2.0, 0.9, "Window t\nfeatures X_t\nlabels y_t (hidden)")
    _box(ax, (3.0, 6.9), 2.0, 0.9, "Deployed model\nscores window t")
    _box(ax, (6.0, 6.9), 2.0, 0.9, "Label vault\nreleases y_(t-D) only")
    _box(ax, (0.6, 5.0), 2.1, 0.9, "Input drift monitor\nPSI + KS per feature")
    _box(ax, (2.9, 5.0), 2.1, 0.9, "Score / confidence monitor\nPSI, alert ratio, entropy")
    _box(ax, (6.0, 5.0), 2.3, 0.9, "Delayed-label backstop\nrecall on matured windows")
    _box(ax, (1.5, 3.3), 3.0, 0.9, "Evidence combiner\nnull-normalised, CUSUM")
    _box(ax, (1.0, 1.6), 5.5, 0.9, "Retrain policy\nlabel-free: defer to t+D+m   backstop: now")
    _box(ax, (1.0, 0.2), 5.5, 0.9, "Retrainer: refit on W matured windows,\nrebuild reference with out-of-fold scores")

    _arrow(ax, (2.3, 9.05), (3.0, 9.05))
    _arrow(ax, (4.0, 8.6), (4.0, 7.8))
    _arrow(ax, (5.0, 8.9), (6.0, 7.5))
    _arrow(ax, (3.5, 6.9), (1.65, 5.9))
    _arrow(ax, (4.3, 6.9), (3.95, 5.9))
    _arrow(ax, (7.0, 6.9), (7.15, 5.9))
    _arrow(ax, (1.65, 5.0), (2.5, 4.2))
    _arrow(ax, (3.95, 5.0), (3.0, 4.2))
    _arrow(ax, (3.0, 3.3), (3.5, 2.5))
    _arrow(ax, (7.15, 5.0), (5.0, 2.1))
    _arrow(ax, (3.75, 1.6), (3.75, 1.1))
    _arrow(ax, (6.5, 0.65), (8.8, 0.65))
    _box(ax, (8.8, 0.3), 1.0, 0.7, "new\nmodel", fc="#d9f0d3")

    ax.text(0.2, 9.8, "Side outputs: decision log, per-window true performance (eval only), timing log", fontsize=8, style="italic")

    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_drift_taxonomy(out_path: Path) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(12, 3), sharey=True)
    t = np.linspace(0, 100, 400)

    sudden = np.where(t < 50, 0.0, 1.0)
    gradual = np.clip((t - 50) / 30, 0, 1)
    recurring = np.where((t >= 30) & (t < 55), 1.0, np.where((t >= 75) & (t < 100), 1.0, 0.0))
    concept = np.where(t < 50, 0.0, 1.0)  # same marginal shift magnitude shown, labelled differently

    titles = ["Sudden (S1)", "Gradual (S2)", "Recurring (S3)", "Concept (S4): inputs unchanged"]
    series = [sudden, gradual, recurring, concept]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for ax, s, title, c in zip(axes, series, titles, colors):
        ax.plot(t, s, color=c, lw=2)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("window")
        ax.set_ylim(-0.1, 1.3)
    axes[0].set_ylabel("input drift magnitude\n(S4: label-function change instead)")
    axes[3].text(50, 1.1, "marginals flat:\nonly P(y|x) moves", fontsize=7, ha="center", color="#d62728")

    fig.suptitle("Drift taxonomy: what changes and when (PRD Figure 3)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_label_delay_timeline(pilot_log: pd.DataFrame, cfg: StreamConfig, out_path: Path) -> None:
    m1 = pilot_log[(pilot_log["scenario"] == "S1") & (pilot_log["strategy"] == "M1") & (pilot_log["seed"] == 0)]
    m1 = m1.sort_values("t")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(m1["t"], m1["ap"], color="#1f77b4", lw=1.5, label="average precision")

    onset = 60
    alarm = m1[m1["alarm_label_free"]]["t"].min()
    maturity = alarm + cfg.label_delay + cfg.maturity_wait if pd.notna(alarm) else None
    retrain_rows = m1[m1["retrain_executed"]]
    retrain = retrain_rows["t"].min() if not retrain_rows.empty else None
    retrain_source = retrain_rows.iloc[0]["retrain_source"] if not retrain_rows.empty else None

    retrain_label = f"retrain ({retrain_source})" if retrain_source else "retrain"
    if retrain_source == "backstop":
        # the backstop can preempt the deferred label-free retrain and fire
        # first (PRD 6.6: "if the backstop fires first, it takes over"), so
        # the retrain can legitimately land before the label-free maturity
        # point; label it as what actually triggered it rather than implying
        # a mismatch.
        retrain_label += "\n(preempted the deferred\nlabel-free retrain)"

    markers = [("onset", onset, "black", 0.97), ("label-free alarm", alarm, "orange", 0.80),
               ("labels mature\n(alarm + D + m)", maturity, "purple", 0.97), (retrain_label, retrain, "green", 0.55)]
    for label, x, color, y_frac in markers:
        if pd.notna(x):
            ax.axvline(x, color=color, linestyle="--", alpha=0.7)
            ax.text(x, ax.get_ylim()[1] * y_frac, label, rotation=90, fontsize=7, color=color, va="top", ha="right")

    ax.set_xlabel("window")
    ax.set_ylabel("average precision")
    ax.set_title("Label-delay timeline, one drift event (S1 moderate, pilot seed 0, strategy M1)")
    ax.set_xlim(40, 100)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")
