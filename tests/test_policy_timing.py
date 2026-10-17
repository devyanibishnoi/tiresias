"""Retrain policy timing, PRD Section 15.1 item 8: a label-free alarm at
window t schedules a retrain at t + D + m, never earlier; a backstop alarm
retrains immediately. Uses a smaller N (rows per window) than the main
config purely to keep this test fast; the window schedule (T, onset points,
label delay) is untouched since those are the behaviour under test.
"""

from dataclasses import replace

from tiresias.config import StreamConfig
from tiresias.simulator import simulate

FAST_CFG = replace(StreamConfig(), N=300)


def test_label_free_retrain_never_earlier_than_t_plus_d_plus_m():
    result = simulate("S1", seed=0, strategy_name="M0", severity="severe", cfg=FAST_CFG)

    alarm_windows = [r["t"] for r in result.records if r["alarm_label_free"]]
    retrain_windows = sorted(t for t, _ in result.retrain_times)

    assert alarm_windows, "expected at least one label-free alarm on severe S1"

    # Only the first alarm in each "pending" cycle sets the due time; later
    # alarms before that retrain fires keep the earlier due time (PRD 6.6:
    # "keep the earlier pending retrain"), so check the first alarm against
    # the first retrain it causes, then jump past that retrain and repeat.
    alarms_remaining = list(alarm_windows)
    retrains_remaining = list(retrain_windows)
    while alarms_remaining and retrains_remaining:
        t_alarm = alarms_remaining[0]
        due = t_alarm + FAST_CFG.label_delay + FAST_CFG.maturity_wait
        caused_retrain = next((t for t in retrains_remaining if t >= t_alarm), None)
        if caused_retrain is None:
            break
        assert caused_retrain >= due - 1e-9, (t_alarm, due, caused_retrain)
        alarms_remaining = [t for t in alarms_remaining if t > caused_retrain]
        retrains_remaining = [t for t in retrains_remaining if t > caused_retrain]


def test_backstop_alarm_retrains_immediately():
    result = simulate("S4", seed=0, strategy_name="B3", severity="moderate", cfg=FAST_CFG)

    backstop_alarms = [r["t"] for r in result.records if r["alarm_backstop"]]
    retrain_windows = {t: source for t, source in result.retrain_times}

    assert backstop_alarms, "expected the backstop to catch S4's concept drift"
    for t_alarm in backstop_alarms:
        assert t_alarm in retrain_windows
        assert retrain_windows[t_alarm] == "backstop"


def test_b0_never_retrains():
    result = simulate("S1", seed=0, strategy_name="B0", severity="severe", cfg=FAST_CFG)
    assert result.retrain_times == []


def test_b1_retrains_on_fixed_schedule():
    result = simulate("S0", seed=0, strategy_name="B1", severity="moderate", cfg=FAST_CFG)
    windows = [t for t, _ in result.retrain_times]
    assert windows == sorted(windows)
    for a, b in zip(windows, windows[1:]):
        assert b - a == FAST_CFG.fixed_schedule_K
