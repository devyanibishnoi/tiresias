"""Leakage guard, PRD Section 15.1 item 4."""

import numpy as np
import pytest

from tiresias.data.label_vault import LabelVault, LeakageError


def test_matured_label_is_readable():
    y = np.arange(30).reshape(30, 1)
    vault = LabelVault(y, label_delay=7)
    assert vault.get(window=10, now=17) == 10


def test_early_access_raises():
    y = np.arange(30).reshape(30, 1)
    vault = LabelVault(y, label_delay=7)
    with pytest.raises(LeakageError):
        vault.get(window=10, now=16)


def test_matured_windows_list():
    y = np.arange(20).reshape(20, 1)
    vault = LabelVault(y, label_delay=7)
    assert vault.matured_windows(now=10) == list(range(4))
