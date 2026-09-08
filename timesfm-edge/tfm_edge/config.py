"""Run configuration. Everything that can change a result lives here, so that the
multiple-testing ledger can hash it and count it as a distinct configuration."""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CostModel:
    """All costs are in basis points of notional, per side unless stated.

    round_trip_bps() is what a trade must beat. Every result is also reported at
    2x these numbers; that is not optional (hard constraint 4).
    """
    commission_bps: float = 5.0   # Binance USDS-M perpetual taker, VIP0
    half_spread_bps: float = 0.5  # BTCUSDT perp typical top-of-book half spread
    slippage_bps: float = 2.0     # market-order impact for small size

    def per_side_bps(self) -> float:
        return self.commission_bps + self.half_spread_bps + self.slippage_bps

    def round_trip_bps(self) -> float:
        return 2.0 * self.per_side_bps()

    def round_trip_frac(self) -> float:
        return self.round_trip_bps() / 1e4

    def scaled(self, k: float) -> "CostModel":
        return CostModel(self.commission_bps * k, self.half_spread_bps * k, self.slippage_bps * k)


@dataclass(frozen=True)
class DataConfig:
    source: str = "binance"          # binance | csv | synthetic
    symbol: str = "BTCUSDT"
    market: str = "um"               # um = USDS-M perpetual futures, spot = spot
    bar: str = "1h"
    years: float = 4.0
    csv_path: str | None = None
    # synthetic only
    synthetic_kind: str = "random_walk"   # random_walk | ar1 | garch_only | trend
    synthetic_n: int = 20000
    synthetic_seed: int = 0
    synthetic_phi: float = 0.0       # AR(1) coefficient for kind=ar1
    equity_source: str = "stooq"     # stooq | yahoo, both keyless; used when source=equity
    cache_dir: str = "cache/data"


@dataclass(frozen=True)
class ForecastConfig:
    forecaster: str = "timesfm"      # timesfm | ar1 | zero | last_sign | ewma | garch
    model_id: str = "google/timesfm-2.5-200m-pytorch"  # or google/timesfm-3.0-pytorch
    model_family: str = "auto"       # auto | timesfm3 | timesfm2.5
    input_mode: str = "log_price"    # log_price | log_return
    context_len: int = 512
    horizon: int = 1
    device: str = "cpu"
    batch_size: int = 32
    cache_dir: str = "cache/forecasts"


@dataclass(frozen=True)
class CrossSectionConfig:
    """Cross-sectional (panel) mode. This is the setup that clears the cost hurdle:
    a dollar-neutral book removes the market factor from the target, residualising
    removes it from the model input, and breadth multiplies the Sharpe by roughly the
    square root of the number of independent bets."""
    enabled: bool = False
    n_assets: int = 60
    symbols: list[str] | None = None      # None with source=binance means "top N by volume"
    residualise: str = "beta"             # none | demean | beta
    top_fraction: float = 0.2             # long the top 20%, short the bottom 20%
    gross: float = 1.0                    # total absolute exposure
    synthetic_phi_idio: float = 0.0       # planted idiosyncratic AR(1) for the self-tests
    # CSV of symbol,start_date,end_date giving index membership through time. Without it
    # an equity panel is a list of survivors and the report says so.
    universe_path: str | None = None
    min_names_per_bar: int = 10


@dataclass(frozen=True)
class StrategyConfig:
    """Turnover-aware, selective execution. The naive every-bar sign flip the Phase 1
    diagnostic reports is the worst possible execution of a signal; these are the knobs
    a real implementation has for free."""
    taus: tuple = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5)
    sizings: tuple = ("binary", "linear", "kelly")
    top_fractions: tuple = (0.1, 0.2, 0.3, 0.5)   # cross-sectional mode
    smoothing_halflives: tuple = (0.0, 2.0, 5.0, 10.0)   # EWMA halflife on scores, in bars
    rebalance_intervals: tuple = (1, 5)                  # hold the book this many bars
    dsr_alpha: float = 0.05


@dataclass(frozen=True)
class WalkForwardConfig:
    n_splits: int = 8
    embargo_bars: int = 24           # bars skipped after a test block before training may resume
    min_train_bars: int = 2000
    max_test_points: int | None = None  # subsample test points to cap TimesFM inference cost


@dataclass(frozen=True)
class StatsConfig:
    alpha: float = 0.05
    n_bootstrap: int = 2000
    bootstrap_seed: int = 12345
    # Test B pass criteria, stated before running (see README "Gate criteria")
    max_mean_abs_coverage_error: float = 0.05
    ledger_path: str = "reports/experiment_ledger.json"


@dataclass(frozen=True)
class RunConfig:
    name: str = "default"
    data: DataConfig = field(default_factory=DataConfig)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    walkforward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    cross_section: CrossSectionConfig = field(default_factory=CrossSectionConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    costs: CostModel = field(default_factory=CostModel)
    stats: StatsConfig = field(default_factory=StatsConfig)
    report_dir: str = "reports"

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def variant_key(self) -> dict[str, Any]:
        """The subset of the config that defines a *tested hypothesis*.

        Two runs with the same variant key are the same test and count once in the
        multiple-testing ledger. Bootstrap seeds, report paths and batch sizes are
        excluded; anything that changes the forecast or the target is included.
        """
        return {
            "data": {k: v for k, v in dataclasses.asdict(self.data).items() if k != "cache_dir"},
            "forecast": {k: v for k, v in dataclasses.asdict(self.forecast).items()
                         if k not in ("cache_dir", "batch_size", "device")},
            "walkforward": dataclasses.asdict(self.walkforward),
            "cross_section": dataclasses.asdict(self.cross_section),
        }

    def variant_hash(self) -> str:
        s = json.dumps(self.variant_key(), sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()[:12]


def _build(cls, d: dict[str, Any]):
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    return cls(**d)


def load_config(path: str | Path) -> RunConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return RunConfig(
        name=raw.get("name", Path(path).stem),
        data=_build(DataConfig, raw.get("data", {})),
        forecast=_build(ForecastConfig, raw.get("forecast", {})),
        walkforward=_build(WalkForwardConfig, raw.get("walkforward", {})),
        cross_section=_build(CrossSectionConfig, raw.get("cross_section", {})),
        strategy=_build(StrategyConfig, raw.get("strategy", {})),
        costs=_build(CostModel, raw.get("costs", {})),
        stats=_build(StatsConfig, raw.get("stats", {})),
        report_dir=raw.get("report_dir", "reports"),
    )
