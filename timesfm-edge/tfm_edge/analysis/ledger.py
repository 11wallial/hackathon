"""Multiple-testing ledger. Every distinct configuration variant that is *evaluated
for directional edge* is recorded here, permanently. The count N feeds the
Bonferroni-adjusted confidence bound used by the gate.

Rules:
  - The ledger is append-only across runs. Deleting it to reset N is p-hacking.
  - Identical variants re-run (same variant hash) count once.
  - Baselines evaluated *alongside* a candidate are not separate hypotheses:
    they are comparators, not candidates for trading. The candidate forecaster of
    each run is the hypothesis. If you run a baseline *as* the candidate, it counts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import false_discovery_control


class Ledger:
    def __init__(self, path: str):
        self.path = Path(path)
        self.entries: dict[str, dict] = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text())

    def count(self) -> int:
        return len(self.entries)

    def record(self, variant_hash: str, variant_key: dict, result: dict | None = None) -> int:
        """Register the variant BEFORE evaluating it, so N includes the current test.
        Returns the count including this variant."""
        now = datetime.now(timezone.utc).isoformat()
        e = self.entries.get(variant_hash)
        if e is None:
            e = {"variant": variant_key, "first_run": now, "run_count": 0, "results": []}
            self.entries[variant_hash] = e
        e["last_run"] = now
        e["run_count"] += 1
        if result is not None:
            e["results"].append(result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2, sort_keys=True))
        return self.count()

    def holm_bh_summary(self, alpha: float) -> dict:
        """Which recorded variants survive Holm (FWER) and Benjamini-Hochberg (FDR)
        across everything ever tested. Uses each variant's latest tradable-hit p-value."""
        items = [(h, e["results"][-1]["p_value"]) for h, e in self.entries.items()
                 if e["results"] and e["results"][-1].get("p_value") is not None]
        if not items:
            return {"n": 0, "holm_survivors": [], "bh_survivors": []}
        hashes, ps = zip(*items)
        import numpy as np
        ps = np.array(ps, dtype=float)
        order = np.argsort(ps)
        m = len(ps)
        holm = []
        for rank, i in enumerate(order):
            if ps[i] <= alpha / (m - rank):
                holm.append(hashes[i])
            else:
                break
        bh_adj = false_discovery_control(ps, method="bh")
        bh = [hashes[i] for i in range(m) if bh_adj[i] <= alpha]
        return {"n": m, "holm_survivors": holm, "bh_survivors": bh}
