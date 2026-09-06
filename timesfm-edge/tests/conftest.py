import numpy as np
import pytest

from tfm_edge.data import synthetic


@pytest.fixture(scope="session")
def rw_bars():
    return synthetic.generate("random_walk", 6000, seed=7)


@pytest.fixture(scope="session")
def ar1_bars():
    return synthetic.generate("ar1", 12000, seed=8, phi=0.15)
