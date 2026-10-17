"""PSI and KS behave as expected, PRD Section 15.1 item 5."""

import numpy as np

from telltale.monitors.stats import ks_statistic, psi

RNG = np.random.default_rng(0)


def test_psi_near_zero_for_identical_distribution():
    ref = RNG.normal(0, 1, 5000)
    cur = RNG.normal(0, 1, 5000)
    assert psi(ref, cur) < 0.05


def test_psi_grows_with_shift():
    ref = RNG.normal(0, 1, 5000)
    small = RNG.normal(0.3, 1, 5000)
    large = RNG.normal(1.5, 1, 5000)
    psi_small = psi(ref, small)
    psi_large = psi(ref, large)
    assert psi_small < psi_large


def test_ks_near_zero_for_identical_distribution():
    ref = RNG.normal(0, 1, 5000)
    cur = RNG.normal(0, 1, 5000)
    assert ks_statistic(ref, cur) < 0.05


def test_ks_grows_with_shift():
    ref = RNG.normal(0, 1, 5000)
    small = RNG.normal(0.3, 1, 5000)
    large = RNG.normal(1.5, 1, 5000)
    assert ks_statistic(ref, small) < ks_statistic(ref, large)
