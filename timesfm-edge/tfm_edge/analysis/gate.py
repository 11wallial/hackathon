"""The gate. Criteria are fixed here, in code, before any result exists.

Test A passes iff, on the TRADABLE (open-to-open) realised return:
    (1) the Bonferroni-adjusted lower confidence bound of the candidate's hit
        rate exceeds the break-even hit rate implied by the 1x cost model, and
    (2) the candidate's point hit rate exceeds every directional baseline
        (last_sign, ar1) and the best constant-sign rate.
Whether (1) also holds at 2x costs is reported, and a pass that dies at 2x is
labelled fragile.

Test B passes iff:
    (1) mean absolute coverage error over the four central intervals
        (20/40/60/80%) is at most `max_mean_abs_coverage_error` (default 5 pts), and
    (2) mean pinball loss is lower than both the GARCH(1,1) and EWMA baselines.

Verdicts:
    PROCEED         A passes (B reported either way)
    VOL_MODEL_ONLY  A fails, B passes: you have a volatility model, not a signal
    STOP            both fail
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateVerdict:
    test_a_pass: bool
    test_a_pass_2x: bool
    test_b_pass: bool
    verdict: str
    reasons: list[str]


def evaluate_gate(candidate: dict, baselines: dict, break_even_1x: float, break_even_2x: float,
                  best_const: float, max_mace: float) -> GateVerdict:
    reasons = []
    hr = candidate["hit_oo"]
    lo_adj = hr["ci_lo_adj"]
    a1 = lo_adj > break_even_1x
    a2 = lo_adj > break_even_2x
    reasons.append(f"adjusted lower bound {lo_adj:.4f} vs break-even {break_even_1x:.4f} (1x) / {break_even_2x:.4f} (2x): {'clears' if a1 else 'fails'} 1x, {'clears' if a2 else 'fails'} 2x")
    beats = True
    for name in ("last_sign", "ar1"):
        if name in baselines:
            b = baselines[name]["hit_oo"]["hit_rate"]
            ok = hr["hit_rate"] > b
            beats &= ok
            reasons.append(f"hit rate {hr['hit_rate']:.4f} vs {name} {b:.4f}: {'beats' if ok else 'does not beat'}")
    ok = hr["hit_rate"] > best_const
    beats &= ok
    reasons.append(f"hit rate {hr['hit_rate']:.4f} vs best constant sign {best_const:.4f}: {'beats' if ok else 'does not beat'}")
    test_a = bool(a1 and beats)

    cal = candidate["calibration"]
    b1 = cal["mean_abs_coverage_error"] <= max_mace
    pb = cal["pinball_loss"]
    b2 = all(pb < baselines[n]["calibration"]["pinball_loss"] for n in ("garch", "ewma") if n in baselines)
    reasons.append(f"mean abs coverage error {cal['mean_abs_coverage_error']:.4f} (limit {max_mace}): {'ok' if b1 else 'fails'}")
    reasons.append(f"pinball {pb:.6f} vs garch {baselines.get('garch', {}).get('calibration', {}).get('pinball_loss', float('nan')):.6f}, ewma {baselines.get('ewma', {}).get('calibration', {}).get('pinball_loss', float('nan')):.6f}: {'beats both' if b2 else 'does not beat both'}")
    test_b = bool(b1 and b2)

    if test_a:
        verdict = "PROCEED" if a2 else "PROCEED_FRAGILE"
    elif test_b:
        verdict = "VOL_MODEL_ONLY"
    else:
        verdict = "STOP"
    return GateVerdict(test_a, bool(a2 and beats), test_b, verdict, reasons)
