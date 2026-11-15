"""Pure unit tests (no warehouse needed)."""
import numpy as np
import pandas as pd

from commerce_intel.analytics.experiment import n_per_arm_mean, n_per_arm_proportion
from commerce_intel.analytics.forecast import _wape
from commerce_intel.config import PALETTE, RAW_FILES


def test_sample_size_monotone_in_mde():
    assert n_per_arm_proportion(0.07, 0.10) > n_per_arm_proportion(0.07, 0.20) > n_per_arm_proportion(0.07, 0.50)
    assert n_per_arm_mean(160, 220, 0.05) > n_per_arm_mean(160, 220, 0.10)


def test_sample_size_textbook_value():
    # 10% -> 12% (two-sided, alpha .05, power .8) is ~3,800 per arm in standard tables
    n = n_per_arm_proportion(0.10, 0.20)
    assert 3500 < n < 4100


def test_wape():
    a = np.array([100.0, 200.0]); f = np.array([110.0, 180.0])
    assert abs(_wape(a, f) - 30 / 300) < 1e-12


def test_palette_is_fixed_order_and_unique():
    assert PALETTE[0] == "#2a78d6" and len(set(PALETTE)) == 8


def test_raw_manifest_complete():
    assert len(RAW_FILES) == 11 and RAW_FILES["olist_orders_dataset.csv"] == 99441
