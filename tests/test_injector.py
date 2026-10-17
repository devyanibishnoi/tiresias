"""Drift injector event-time correctness, PRD Section 15.1 item 3."""

from tiresias.data.injector import scenario_events, scenario_window_params


def test_s0_has_no_events():
    assert scenario_events("S0") == []


def test_s1_onset_at_60():
    events = scenario_events("S1", "moderate")
    assert len(events) == 1
    assert events[0].window == 60
    assert events[0].kind == "onset"
    assert events[0].drift_type == "sudden"


def test_s2_onset_at_60_gradual():
    events = scenario_events("S2", "moderate")
    assert events[0].window == 60
    assert events[0].drift_type == "gradual"


def test_s3_recurring_schedule():
    events = scenario_events("S3", "moderate")
    windows_kinds = [(e.window, e.kind) for e in events]
    assert windows_kinds == [(50, "onset"), (70, "offset"), (110, "onset")]


def test_s4_onset_concept():
    events = scenario_events("S4")
    assert events[0].window == 60
    assert events[0].drift_type == "concept"


def test_s6_has_no_drift_events():
    assert scenario_events("S6") == []


def test_s7_prevalence_window():
    events = scenario_events("S7")
    assert [(e.window, e.kind) for e in events] == [(60, "onset"), (81, "offset")]


def test_s1_mean_shift_zero_before_onset_nonzero_after():
    before = scenario_window_params("S1", 59, "severe")
    after = scenario_window_params("S1", 60, "severe")
    assert (before.mean_shift == 0).all()
    assert (after.mean_shift != 0).any()


def test_s2_gradual_shift_grows_then_caps():
    p60 = scenario_window_params("S2", 60, "moderate")
    p75 = scenario_window_params("S2", 75, "moderate")
    p90 = scenario_window_params("S2", 90, "moderate")
    p120 = scenario_window_params("S2", 120, "moderate")
    mag = lambda p: abs(p.mean_shift).sum()
    assert mag(p60) < mag(p75) < mag(p90)
    assert mag(p90) == mag(p120)


def test_s3_off_period_has_no_shift():
    off = scenario_window_params("S3", 85, "severe")
    assert (off.mean_shift == 0).all()
