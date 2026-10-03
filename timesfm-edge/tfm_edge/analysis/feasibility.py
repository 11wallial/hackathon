"""Feasibility arithmetic: what does a setup need from the model?

The Phase 1 gate answers "does this model have an edge here". This module answers
the prior question: "if it had a plausible edge, would this setup make money?"
Running it first tells you whether a configuration is worth spending inference on.

THE MODEL
---------
Standardised forecast z ~ N(0,1), realised bar return r = sigma_r (IC z + sqrt(1-IC^2) e).
IC is the Pearson correlation between forecast and realised return.

Take a position only when |z| > tau, sized +/-1, held one bar.

    trade fraction          f(tau)  = 2(1 - Phi(tau))
    conditional signal size M(tau)  = E[|z| | |z|>tau] = phi(tau) / (1 - Phi(tau))
    gross return per trade          = sigma_r * IC * M(tau)
    cost per trade                  = c_rt * turnover
    mean per bar                    = f * (sigma_r IC M - c_rt turnover)
    variance per bar                ~ f * sigma_r^2          (position is +/-1 or 0)

    Sharpe per bar = sqrt(f(tau)) * (IC * M(tau) - k * turnover)      where k = c_rt / sigma_r

Everything collapses to ONE number, k, the cost-to-volatility ratio. It is the whole
game. The naive every-bar break-even hit rate the harness reports is just

    p* = 0.5 + k / (2 * sqrt(2/pi)) = 0.5 + 0.6267 k

so a setup with k = 0.38 (BTC 1h at taker fees) needs 0.74 and a setup with k = 0.01
(index futures on daily bars) needs 0.506. Same model, same edge, opposite verdict.

BREADTH
-------
Trading N instruments whose residual returns are independent multiplies the Sharpe by
sqrt(N_eff) without needing a better model. This is Grinold's fundamental law, and it
is the only lever that improves BOTH profitability and statistical power. Halving the
years needed to prove an edge is worth more than doubling the edge.

CAVEATS THAT MATTER
-------------------
- Selection on |z| raises E[signed return], NOT E[|r|]. For a weak directional signal
  the realised move size is dominated by noise and barely shifts with the forecast, so
  do not expect the "trade only big forecasts" filter to find bigger moves. It
  concentrates the *edge*, not the *volatility*.
- turnover < 1 requires a persistent signal. If consecutive bars want the same side you
  hold rather than round-trip. For an AR(rho) position path E|dw| / 2 ~ sqrt((1-rho)/2).
- IC here is Pearson. The harness reports Spearman; for near-normal data
  rho_spearman ~ 0.955 rho_pearson at small values, so treat them as interchangeable
  at this precision and no further.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

SQRT_2_OVER_PI = np.sqrt(2.0 / np.pi)


def signal_size_given_selected(tau: float | np.ndarray) -> np.ndarray:
    """E[|z| | |z| > tau] for standard normal z. Equals sqrt(2/pi) at tau=0."""
    tau = np.asarray(tau, dtype=float)
    return norm.pdf(tau) / np.maximum(norm.sf(tau), 1e-300)


def trade_fraction(tau: float | np.ndarray) -> np.ndarray:
    return 2.0 * norm.sf(np.asarray(tau, dtype=float))


def naive_break_even_hit_rate(k: float) -> float:
    """Hit rate needed when trading every bar on sign alone. p* = 0.5 + 0.6267 k."""
    return 0.5 + k / (2.0 * SQRT_2_OVER_PI)


def sharpe_per_bar(ic: float, k: float, tau: float | np.ndarray, turnover: float = 1.0) -> np.ndarray:
    f = trade_fraction(tau)
    return np.sqrt(f) * (ic * signal_size_given_selected(tau) - k * turnover)


@dataclass(frozen=True)
class Feasibility:
    label: str
    k: float                    # cost / per-bar volatility, the whole game
    sigma_bar_bps: float
    cost_rt_bps: float
    bars_per_year: float
    breadth: float
    naive_break_even: float     # hit rate needed trading every bar
    best_tau: float
    best_trade_fraction: float
    best_hit_rate_needed: float # hit rate needed among SELECTED bars
    sharpe_at_ic: float         # annualised, including breadth
    ic_for_sharpe_1: float      # IC needed for annualised Sharpe 1.0
    years_to_prove: float       # min track record to reject Sharpe<=0 at 95%

    def as_row(self) -> dict:
        return dataclasses.asdict(self)


def _annualise(sharpe_bar: np.ndarray, bars_per_year: float, breadth: float) -> np.ndarray:
    return sharpe_bar * np.sqrt(bars_per_year * breadth)


def min_track_record_years(sharpe_ann: float, skew: float = -0.5, kurtosis: float = 6.0,
                           alpha: float = 0.05) -> float:
    """Bailey & Lopez de Prado minimum track record length, in years, to conclude the
    annualised Sharpe exceeds zero. Defaults assume the negative skew and fat tails
    typical of a trend/carry return stream, which lengthen the requirement."""
    if sharpe_ann <= 0:
        return float("inf")
    z = norm.ppf(1 - alpha)
    adj = 1.0 - skew * sharpe_ann + (kurtosis - 1.0) / 4.0 * sharpe_ann ** 2
    return float(1.0 + max(adj, 1e-9) * (z / sharpe_ann) ** 2)


def evaluate(label: str, vol_annual: float, bars_per_year: float, cost_rt_bps: float,
             ic: float = 0.03, turnover: float = 1.0, breadth: float = 1.0,
             tau_grid: np.ndarray | None = None) -> Feasibility:
    """Feasibility of one setup at an assumed IC.

    vol_annual: annualised return volatility as a fraction (0.37 = 37%). For a
        cross-sectional book this is the RESIDUAL (market-neutralised) volatility.
    breadth: effective number of independent simultaneous bets. 1 for a single
        instrument; for a cross-sectional book it is far below the instrument count
        because residuals stay correlated.
    """
    sigma_bar = vol_annual / np.sqrt(bars_per_year)
    k = (cost_rt_bps / 1e4) / sigma_bar
    grid = tau_grid if tau_grid is not None else np.linspace(0.0, 4.0, 801)
    sb = sharpe_per_bar(ic, k, grid, turnover)
    best = int(np.argmax(sb))
    tau = float(grid[best])
    sharpe_ann = float(_annualise(sb[best], bars_per_year, breadth))

    # IC needed for annualised Sharpe 1.0, maximising over tau at each candidate IC
    ic_grid = np.geomspace(1e-4, 1.0, 400)
    need = np.inf
    for cand in ic_grid:
        s = _annualise(np.max(sharpe_per_bar(cand, k, grid, turnover)), bars_per_year, breadth)
        if s >= 1.0:
            need = float(cand)
            break

    # among selected bars, the hit rate that breaks even on cost alone
    m = float(signal_size_given_selected(tau))
    return Feasibility(
        label=label, k=float(k), sigma_bar_bps=float(sigma_bar * 1e4), cost_rt_bps=cost_rt_bps,
        bars_per_year=bars_per_year, breadth=breadth,
        naive_break_even=naive_break_even_hit_rate(k),
        best_tau=tau, best_trade_fraction=float(trade_fraction(tau)),
        best_hit_rate_needed=0.5 + (k * turnover) / (2.0 * m),
        sharpe_at_ic=sharpe_ann, ic_for_sharpe_1=need,
        years_to_prove=min_track_record_years(sharpe_ann),
    )


# Instrument presets. Costs are round-trip in bps of notional and INCLUDE crossing the
# spread both ways; volatilities are annualised and approximate. These are estimates to
# rank setups, not quotes: verify against your own venue and sample before trusting one.
PRESETS: dict[str, dict] = {
    "btc_perp_1h_taker":   dict(vol_annual=0.37, bars_per_year=8760, cost_rt_bps=15.0),
    "btc_perp_1h_maker":   dict(vol_annual=0.37, bars_per_year=8760, cost_rt_bps=4.0),
    "btc_perp_4h_taker":   dict(vol_annual=0.37, bars_per_year=2190, cost_rt_bps=15.0),
    "btc_perp_1d_taker":   dict(vol_annual=0.37, bars_per_year=365,  cost_rt_bps=15.0),
    "es_1h":               dict(vol_annual=0.16, bars_per_year=5796, cost_rt_bps=0.9),
    "es_1d":               dict(vol_annual=0.16, bars_per_year=252,  cost_rt_bps=0.9),
    "mes_1d":              dict(vol_annual=0.16, bars_per_year=252,  cost_rt_bps=1.25),
    "eurusd_1d":           dict(vol_annual=0.07, bars_per_year=252,  cost_rt_bps=0.9),
    "spy_1d":              dict(vol_annual=0.16, bars_per_year=252,  cost_rt_bps=1.7),
    # cross-sectional books: vol is the residual after removing the market factor,
    # breadth is the effective independent bet count, well below the instrument count
    "crypto_xs_1d_60":     dict(vol_annual=0.60, bars_per_year=365, cost_rt_bps=15.0, breadth=12.0),
    "crypto_xs_weekly_60": dict(vol_annual=0.60, bars_per_year=52,  cost_rt_bps=15.0, breadth=12.0),
    "equity_xs_1d_500":    dict(vol_annual=0.25, bars_per_year=252, cost_rt_bps=3.0,  breadth=25.0),
}


def survey(ic: float = 0.03, turnover: float = 1.0, presets: dict | None = None) -> list[Feasibility]:
    src = presets if presets is not None else PRESETS
    return [evaluate(name, ic=ic, turnover=turnover, **spec) for name, spec in src.items()]


def format_survey(rows: list[Feasibility], ic: float) -> str:
    out = [
        f"Feasibility survey at IC = {ic:.3f} (Pearson, forecast vs next-bar return)",
        "",
        "| setup | k = cost/vol | naive break-even | best trade frac | hit rate needed (selected) | Sharpe @ IC | IC for Sharpe 1 | years to prove |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: -x.sharpe_at_ic):
        ic1 = "-" if not np.isfinite(r.ic_for_sharpe_1) else f"{r.ic_for_sharpe_1:.3f}"
        yrs = "never" if not np.isfinite(r.years_to_prove) else f"{r.years_to_prove:.0f}"
        out.append(
            f"| {r.label} | {r.k:.3f} | {r.naive_break_even:.3f} | {r.best_trade_fraction:.2f} | "
            f"{r.best_hit_rate_needed:.3f} | {r.sharpe_at_ic:.2f} | {ic1} | {yrs} |"
        )
    return "\n".join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Which setups can pay for themselves?")
    ap.add_argument("--ic", type=float, default=0.03, help="assumed Pearson IC")
    ap.add_argument("--turnover", type=float, default=1.0, help="fraction of a full round trip paid per traded bar")
    ap.add_argument("--plot", help="write the feasibility figure to this path")
    a = ap.parse_args(argv)
    print(format_survey(survey(a.ic, a.turnover), a.ic))
    if a.plot:
        plot_surface(a.plot, a.ic)
        print(f"\nfigure: {a.plot}")


# Chart palette: validated categorical slots 1-3 plus ink/surface tokens. Text never
# wears a series colour; the coloured mark beside it carries identity.
_SURFACE, _INK, _INK_2, _GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
_SERIES = ("#2a78d6", "#eb6834", "#1baf7a")


def plot_surface(path, ic: float = 0.03, curve_setups=("btc_perp_1h_taker", "es_1d", "equity_xs_1d_500")):
    """Two panels: the hurdle every setup sets, and what selection can do about it."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(survey(ic), key=lambda r: r.naive_break_even)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.2), facecolor=_SURFACE,
                                   gridspec_kw={"width_ratios": [1.15, 1]})
    for ax in (ax1, ax2):
        ax.set_facecolor(_SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(_GRID)
        ax.tick_params(colors=_INK_2, labelsize=9, length=0)

    y = np.arange(len(rows))
    ax1.barh(y, [r.naive_break_even for r in rows], height=0.62, color=_SERIES[0], zorder=3)
    ax1.axvline(0.5, color=_INK_2, lw=1, ls=(0, (4, 3)), zorder=4)
    ax1.text(0.5, len(rows) - 0.2, "  coin flip", color=_INK_2, fontsize=9, va="center")
    for i, r in enumerate(rows):
        ax1.text(r.naive_break_even + 0.004, i, f"{r.naive_break_even:.3f}", va="center",
                 fontsize=9, color=_INK)
    ax1.set_yticks(y, [r.label for r in rows], fontsize=9)
    ax1.set_xlim(0.49, 0.79)
    ax1.set_xlabel("hit rate needed to break even, trading every bar", color=_INK_2, fontsize=10)
    ax1.set_title("The hurdle is set by the setup, not the model",
                  color=_INK, fontsize=12, loc="left", pad=12)
    ax1.grid(axis="x", color=_GRID, lw=0.8, zorder=0)
    ax1.set_axisbelow(True)

    taus = np.linspace(0, 3.0, 300)
    fracs = trade_fraction(taus)
    lo, hi = -1.6, 1.6
    for c, name, off in zip(_SERIES, curve_setups, [(10, 10), (0, 12), (0, 12)]):
        spec = PRESETS[name]
        r = evaluate(name, ic=ic, **spec)
        sb = sharpe_per_bar(ic, r.k, taus) * np.sqrt(spec["bars_per_year"] * spec.get("breadth", 1.0))
        ax2.plot(fracs, np.clip(sb, lo, hi), color=c, lw=2, zorder=3)
        j = int(np.argmax(sb))
        if lo < sb[j] < hi:
            ax2.plot(fracs[j], sb[j], "o", ms=8, color=c, mec=_SURFACE, mew=2, zorder=4)
            tag = f"best {sb[j]:.2f}, never positive" if sb[j] <= 0 else f"peak Sharpe {sb[j]:.2f}"
            ax2.annotate(f"{name}\n{tag}", (fracs[j], sb[j]), textcoords="offset points",
                         xytext=off, fontsize=9, color=_INK, ha="center")
        else:
            ax2.annotate(f"{name}\nfalls to {sb.min():.0f}, off scale", (0.62, lo + 0.12),
                         fontsize=9, color=_INK, ha="center")
    ax2.axhline(0, color=_INK_2, lw=1, zorder=2)
    ax2.set_ylim(lo, hi)
    ax2.set_xlabel("fraction of bars traded (looser threshold to the right)", color=_INK_2, fontsize=10)
    ax2.set_ylabel("annualised Sharpe", color=_INK_2, fontsize=10)
    ax2.set_title(f"Same edge (IC = {ic:.2f}), three setups", color=_INK, fontsize=12, loc="left", pad=12)
    ax2.grid(color=_GRID, lw=0.8, zorder=0)
    ax2.set_axisbelow(True)
    ax2.legend([plt.Line2D([], [], color=c, lw=2) for c in _SERIES], list(curve_setups),
               frameon=False, fontsize=9, labelcolor=_INK_2, loc="upper right")

    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=_SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    main()
