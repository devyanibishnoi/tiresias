from tiresias.monitors.cusum import CUSUM


def test_no_alarm_under_slack():
    c = CUSUM(slack=1.0, height=3.0)
    for _ in range(20):
        alarm = c.update(0.5)
        assert not alarm
    assert c.S == 0.0


def test_alarm_when_sum_exceeds_height():
    c = CUSUM(slack=0.5, height=2.0)
    alarms = [c.update(1.5) for _ in range(5)]
    assert any(alarms)


def test_cooldown_suppresses_immediate_second_alarm():
    c = CUSUM(slack=0.0, height=1.0, cooldown=3)
    first = c.update(5.0)
    assert first
    second = c.update(5.0)
    assert not second  # cooldown window


def test_sum_never_goes_negative():
    c = CUSUM(slack=1.0, height=10.0)
    for _ in range(5):
        c.update(0.0)
    assert c.S == 0.0
