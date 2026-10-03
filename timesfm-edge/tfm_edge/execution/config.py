"""Bot configuration. Strict: an unknown key is an error, never silently ignored.

A typo in a risk limit (`daily_loss_limt: 0.01`) that falls back to the default is exactly
the kind of failure that is invisible until it matters, so every section rejects keys it
does not know.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import RunConfig, load_config
from ..decision.book import BookConfig
from ..risk.limits import RiskConfig

BROKER_KINDS = ("paper", "alpaca_paper", "alpaca_live")


@dataclass(frozen=True)
class BrokerConfig:
    kind: str = "paper"                 # paper | alpaca_paper | alpaca_live
    key_env: str = "APCA_API_KEY_ID"    # NAMES of environment variables; secrets never live in a file
    secret_env: str = "APCA_API_SECRET_KEY"
    order_tif: str = "opg"              # opg = market-on-open, the closest match to the backtest's fill
    base_url: str | None = None         # override, used by tests; None picks the right Alpaca host
    request_timeout_s: float = 20.0


@dataclass(frozen=True)
class LiveGuard:
    """What stands between this code and real money. All of it can be overridden, and each
    override is a deliberate, named act that gets logged on every run."""
    require_approval: bool = True            # a human approves each day's plan in the UI
    min_paper_days: int = 5                  # sessions of paper/alpaca_paper trading before live
    acknowledge_gate_not_passed: bool = False   # live without a passing real-data Phase 1 report
    acknowledge_short_paper_run: bool = False   # live with fewer than min_paper_days of paper
    max_divergence_z: float = 3.0            # paper-vs-backtest divergence beyond this blocks live


@dataclass(frozen=True)
class Schedule:
    plan_after_et: str = "16:20"         # plan any time after this, until execute_before_et next day
    execute_at_et: str = "09:00"         # submit approved orders at this time
    execute_cutoff_et: str = "09:25"     # a plan not executed by now is expired, never run late
    reconcile_at_et: tuple = ("09:40", "16:15")


@dataclass(frozen=True)
class BotConfig:
    name: str
    run_config: str                      # Phase 1 style yaml: data source, symbols, forecaster, costs
    capital: float
    risk: RiskConfig
    book: BookConfig = field(default_factory=BookConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    live: LiveGuard = field(default_factory=LiveGuard)
    schedule: Schedule = field(default_factory=Schedule)
    smoothing_halflife: float = 5.0      # EWMA on scores, in sessions (the Phase 1 sweep's knob)
    score_warmup_days: int = 20          # past sessions replayed to warm the EWMA, deterministically
    beta_window: int = 750               # sessions used to estimate betas
    vol_window: int = 60                 # sessions used for the stop-distance volatility
    data_years: float = 6.0              # history fetched per symbol
    data_max_age_hours: float = 6.0      # refetch bars older than this
    min_coverage: float = 0.90           # fraction of symbols that must have today's bar
    state_dir: str = "state"
    base_dir: str = "."                  # where relative paths resolve; set by the loader

    def db_path_for(self, kind: str) -> str:
        """One ledger per broker kind, so paper history can never contaminate a live ledger."""
        return str(Path(self.base_dir) / self.state_dir / kind / "bot.sqlite")

    @property
    def db_path(self) -> str:
        return self.db_path_for(self.broker.kind)

    @property
    def kill_file(self) -> str:
        """One KILL file for every mode: `touch state/KILL` halts paper and live alike, from any shell,
        even if the UI or the database is wedged."""
        return str(Path(self.base_dir) / self.state_dir / "KILL")

    def run(self) -> RunConfig:
        return load_config(Path(self.base_dir) / self.run_config)

    @property
    def is_live(self) -> bool:
        return self.broker.kind == "alpaca_live"


def _build(cls, d: dict[str, Any] | None, where: str):
    d = dict(d or {})
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}; valid keys are {sorted(known)}")
    if "reconcile_at_et" in d:
        d["reconcile_at_et"] = tuple(d["reconcile_at_et"])
    return cls(**d)


def load_bot_config(path: str | Path, base_dir: str | Path | None = None) -> BotConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    top = {f.name for f in dataclasses.fields(BotConfig)} - {"base_dir"}
    unknown = set(raw) - top
    if unknown:
        raise ValueError(f"{path.name}: unknown top-level key(s) {sorted(unknown)}")
    for need in ("run_config", "capital", "risk"):
        if need not in raw:
            raise ValueError(f"{path.name}: '{need}' is required")
    risk = raw["risk"]
    if "max_capital" not in risk:
        raise ValueError(f"{path.name}: risk.max_capital is required, with no default. It is the hard "
                         f"ceiling on money the bot may deploy, so you have to choose it.")
    cfg = BotConfig(
        name=raw.get("name", path.stem),
        run_config=raw["run_config"],
        capital=float(raw["capital"]),
        risk=_build(RiskConfig, risk, "risk"),
        book=_build(BookConfig, raw.get("book"), "book"),
        broker=_build(BrokerConfig, raw.get("broker"), "broker"),
        live=_build(LiveGuard, raw.get("live"), "live"),
        schedule=_build(Schedule, raw.get("schedule"), "schedule"),
        **{k: raw[k] for k in ("smoothing_halflife", "score_warmup_days", "beta_window", "vol_window",
                               "data_years", "data_max_age_hours", "min_coverage", "state_dir") if k in raw},
        base_dir=str(base_dir if base_dir is not None else path.resolve().parent.parent),
    )
    problems = validate(cfg)
    if problems:
        raise ValueError(f"{path.name}: " + "; ".join(problems))
    return cfg


def validate(cfg: BotConfig) -> list[str]:
    out: list[str] = []
    if cfg.broker.kind not in BROKER_KINDS:
        out.append(f"broker.kind must be one of {BROKER_KINDS}")
    if cfg.broker.order_tif not in ("opg", "day"):
        out.append("broker.order_tif must be 'opg' or 'day'")
    if cfg.capital <= 0:
        out.append("capital must be positive")
    if cfg.capital > cfg.risk.max_capital:
        out.append(f"capital {cfg.capital:,.0f} exceeds risk.max_capital {cfg.risk.max_capital:,.0f}")
    if cfg.risk.max_gross_exposure < cfg.book.gross:
        out.append(f"risk.max_gross_exposure {cfg.risk.max_gross_exposure} is below book.gross {cfg.book.gross}")
    if cfg.risk.max_name_weight < cfg.book.max_name_weight:
        out.append("risk.max_name_weight is below book.max_name_weight: the book would fail its own risk check")
    if not 0 < cfg.risk.daily_loss_limit < 1:
        out.append("risk.daily_loss_limit must be a fraction between 0 and 1")
    if not 0 < cfg.book.top_fraction <= 0.5:
        out.append("book.top_fraction must be in (0, 0.5]")
    return out
