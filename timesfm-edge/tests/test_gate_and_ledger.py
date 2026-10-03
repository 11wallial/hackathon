import json

from tfm_edge.analysis.gate import evaluate_gate
from tfm_edge.analysis.ledger import Ledger


def _cand(hr, lo_adj, mace=0.02, pb=1.0):
    return {"hit_oo": {"hit_rate": hr, "ci_lo_adj": lo_adj}, "calibration": {"mean_abs_coverage_error": mace, "pinball_loss": pb}}


def _bases(pb_garch=1.1, pb_ewma=1.1):
    return {"last_sign": _cand(0.50, 0.49), "ar1": _cand(0.51, 0.50),
            "garch": {"calibration": {"pinball_loss": pb_garch}, "hit_oo": {"hit_rate": float("nan")}},
            "ewma": {"calibration": {"pinball_loss": pb_ewma}, "hit_oo": {"hit_rate": float("nan")}}}


def test_gate_verdicts():
    g = evaluate_gate(_cand(0.60, 0.58), _bases(), 0.55, 0.60, 0.51, 0.05)
    assert g.verdict == "PROCEED_FRAGILE" and g.test_a_pass and not g.test_a_pass_2x
    g = evaluate_gate(_cand(0.65, 0.62), _bases(), 0.55, 0.60, 0.51, 0.05)
    assert g.verdict == "PROCEED" and g.test_a_pass_2x
    g = evaluate_gate(_cand(0.52, 0.505), _bases(), 0.55, 0.60, 0.51, 0.05)
    assert g.verdict == "VOL_MODEL_ONLY"
    g = evaluate_gate(_cand(0.52, 0.505, pb=1.2), _bases(), 0.55, 0.60, 0.51, 0.05)
    assert g.verdict == "STOP"
    # clears break-even but fails to beat a baseline: not a pass
    g = evaluate_gate(_cand(0.56, 0.555), {**_bases(), "ar1": _cand(0.57, 0.56)}, 0.55, 0.60, 0.51, 0.05)
    assert not g.test_a_pass


def test_ledger_counts_distinct_variants_once(tmp_path):
    p = tmp_path / "ledger.json"
    L = Ledger(str(p))
    assert L.record("a", {"x": 1}) == 1
    assert L.record("a", {"x": 1}, {"p_value": 0.5}) == 1
    assert L.record("b", {"x": 2}, {"p_value": 0.001}) == 2
    L2 = Ledger(str(p))   # persists across processes
    assert L2.count() == 2 and L2.entries["a"]["run_count"] == 2
    s = L2.holm_bh_summary(0.05)
    assert s["holm_survivors"] == ["b"]
    assert json.loads(p.read_text())["b"]["results"][0]["p_value"] == 0.001
