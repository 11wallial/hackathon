"""Purged, embargoed, forward-chained walk-forward.

Sample i has decision index t_i and label window (t_i, t_i + H]. For a test block
starting at decision index t0:

    purge   : training returns with index > t0 - H are dropped, because their
              label windows overlap the first test label (Lopez de Prado, AFML ch.7).
    embargo : an extra `embargo_bars` are dropped before t0. In forward-chained
              validation nothing is trained after the test block, so the classic
              post-test embargo has nothing to act on; we apply it pre-test so that
              a volatility state fitted on bars adjacent to the test block cannot
              carry over (GARCH persistence is ~0.98 on hourly crypto).

Zero-shot models ignore the training fold, but their context windows never extend
past t_i, so the same guarantee holds.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import WalkForwardConfig
from ..features.samples import Samples


@dataclass(frozen=True)
class Fold:
    k: int
    train_return_end: int     # exclusive index into the per-bar return array
    test_sample_idx: np.ndarray  # indices into Samples

    def describe(self, samples: Samples) -> str:
        t = samples.t[self.test_sample_idx]
        return f"fold {self.k}: train returns [0, {self.train_return_end}), test decisions t in [{t.min()}, {t.max()}] ({len(t)} pts)"


def make_folds(samples: Samples, cfg: WalkForwardConfig) -> list[Fold]:
    H = samples.horizon
    eligible = np.where(samples.t >= cfg.min_train_bars)[0]
    if len(eligible) < cfg.n_splits * 10:
        raise ValueError("not enough samples after min_train_bars for the requested splits")
    blocks = np.array_split(eligible, cfg.n_splits)
    folds = []
    for k, blk in enumerate(blocks):
        t0 = int(samples.t[blk[0]])
        train_end = t0 - H - cfg.embargo_bars + 1   # returns r[u] for u <= t0-H-embargo
        if train_end < 100:
            raise ValueError("purge/embargo leaves too little training data")
        if cfg.max_test_points is not None and len(blk) > cfg.max_test_points:
            pick = np.linspace(0, len(blk) - 1, cfg.max_test_points).round().astype(int)
            blk = blk[np.unique(pick)]
        folds.append(Fold(k, train_end, blk))
    return folds


def assert_no_overlap(samples: Samples, fold: Fold) -> None:
    """Every training label window must end strictly before the first test decision."""
    H = samples.horizon
    last_train_label_end = (fold.train_return_end - 1) + H  # decision index u = train_end-1 labels up to u+H
    first_test_decision = int(samples.t[fold.test_sample_idx[0]])
    if last_train_label_end > first_test_decision:
        raise AssertionError(f"fold {fold.k}: training label window reaches {last_train_label_end} > test start {first_test_decision}")
