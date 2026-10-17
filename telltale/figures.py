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


def make_performance_over_time(window_log: pd.DataFrame, scenario: str, severity: str, out_path: Path) -> None:
    g = window_log[(window_log["scenario"] == scenario) & (window_log["severity"] == severity)]
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, gg in g.groupby("strategy"):
        mean_by_t = gg.groupby("t")["ap"].mean()
        ax.plot(mean_by_t.index, mean_by_t.values, label=strategy, lw=1.3)

    m1 = g[g["strategy"] == "M1"]
    for t in m1[m1["alarm_label_free"]]["t"].unique():
        ax.axvline(t, color="orange", alpha=0.15, linestyle="--")
    for t in m1[m1["retrain_executed"]]["t"].unique():
        ax.axvline(t, color="green", alpha=0.2, linestyle="-")

    ax.set_xlabel("window")
    ax.set_ylabel("average precision (mean over seeds)")
    ax.set_title(f"Performance over time, {scenario} {severity} (M1 alarms=orange, retrains=green)")
    ax.legend(fontsize=8, ncol=4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_detection_delay_vs_severity(summary: dict, out_path: Path) -> None:
    severities = ["mild", "moderate", "severe"]
    strategies = ["M0", "M1"]
    fig, ax = plt.subplots(figsize=(7, 5))
    for strategy in strategies:
        delays = []
        for sev in severities:
            key = f"S1|{sev}|{strategy}"
            d = summary["detection"].get(key, {}).get("label_free_delay_median")
            delays.append(d if d is not None else float("nan"))
        ax.plot(severities, delays, marker="o", label=strategy)
    ax.set_xlabel("S1 severity")
    ax.set_ylabel("median label-free detection delay (windows)")
    ax.set_title("Detection delay versus drift severity")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_retrain_vs_recall(summary: dict, scenarios: list, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    strategies = ["B0", "B1", "B2", "B3", "M0", "M1", "M1a", "M1b"]
    for strategy in strategies:
        xs, ys = [], []
        for scenario in scenarios:
            severity = "moderate"
            key = f"{scenario}|{severity}|{strategy}"
            g = summary["groups"].get(key)
            if g:
                xs.append(g["retrain_count_mean"])
                ys.append(g["time_averaged_recall_mean"])
        if xs:
            ax.scatter(xs, ys, label=strategy, s=40)
    ax.set_xlabel("mean retrain count")
    ax.set_ylabel("mean time-averaged recall at budget")
    ax.set_title("Cost versus performance, averaged over scenarios")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_ablation_bars(summary: dict, scenario: str, severity: str, out_path: Path) -> None:
    strategies = ["M1a", "M1b", "M1"]
    labels = ["input-only", "score-only", "combined"]
    delays, fas = [], []
    for strategy in strategies:
        dkey = f"{scenario}|{severity}|{strategy}"
        delays.append(summary["detection"].get(dkey, {}).get("label_free_delay_median") or 0)
        fas.append(summary["false_alarms"].get(dkey, {}).get("rate_per_100") or 0)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].bar(labels, delays, color="#4c72b0")
    axes[0].set_ylabel("median detection delay (windows)")
    axes[0].set_title(f"Detection delay, {scenario} {severity}")
    axes[1].bar(labels, fas, color="#dd8452")
    axes[1].set_ylabel("false alarms per 100 windows")
    axes[1].set_title("False alarm rate (S0/S6 average)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_false_alarm_rates(summary: dict, out_path: Path) -> None:
    strategies = ["M0", "M1", "M1a", "M1b", "B3"]
    s0_rates, s6_rates = [], []
    for strategy in strategies:
        s0_rates.append(summary["false_alarms"].get(f"S0|moderate|{strategy}", {}).get("rate_per_100") or 0)
        s6_rates.append(summary["false_alarms"].get(f"S6|moderate|{strategy}", {}).get("rate_per_100") or 0)

    x = np.arange(len(strategies))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - 0.2, s0_rates, width=0.4, label="S0")
    ax.bar(x + 0.2, s6_rates, width=0.4, label="S6")
    ax.axhline(1.0, color="red", linestyle="--", lw=1, label="PRD target (1/100)")
    ax.set_xticks(x)
    ax.set_xticklabels(strategies)
    ax.set_ylabel("alarms per 100 windows")
    ax.set_title("False alarm rate, no-drift scenarios")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"wrote {out_path}")


def make_s4_failure_figure(window_log: pd.DataFrame, out_path: Path) -> None:
    g = window_log[(window_log["scenario"] == "S4") & (window_log["strategy"].isin(["M1", "B3"]))]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    for strategy, gg in g.groupby("strategy"):
        mean_by_t = gg.groupby("t")["ap"].mean()
        axes[0].plot(mean_by_t.index, mean_by_t.values, label=strategy)
    axes[0].axvline(60, color="black", linestyle="--", alpha=0.6, label="true onset")
    axes[0].set_ylabel("average precision")
    axes[0].legend()
    axes[0].set_title("S4 (pure concept drift): performance collapses while label-free evidence stays flat")

    m1 = g[g["strategy"] == "M1"]
    mean_ev = m1.groupby("t")["combined_evidence"].mean()
    axes[1].plot(mean_ev.index, mean_ev.values, color="purple", label="M1 combined evidence")
    axes[1].axhline(1.0, color="gray", linestyle=":", label="edge of normal")
    axes[1].axvline(60, color="black", linestyle="--", alpha=0.6)
    axes[1].set_xlabel("window")
    axes[1].set_ylabel("label-free evidence")
    axes[1].legend()

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
