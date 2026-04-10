"""Config loading and validation.

Two layers:
  1. Runtime settings from environment (.env) — see `Settings`
  2. YAML config files in /config — see `load_*` functions

All YAML configs are validated via Pydantic models. A malformed config will
fail loudly with a clear error rather than silently misbehaving downstream.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


# ============================================================================
# Runtime settings (from environment)
# ============================================================================

class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Mode and environment
    mode: str = "shadow"            # shadow | paper | live
    environment: str = "local"      # local | prod
    tz: str = "Asia/Dubai"

    # Database
    database_url: str = "sqlite:///./data/fesi.db"

    # LLM APIs
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    voyage_api_key: str = ""

    # Market data
    polygon_api_key: str = ""
    tiingo_api_key: str = ""

    # Broker
    ibkr_api_username: str = ""
    ibkr_api_password: str = ""
    ibkr_account_id: str = ""
    ibkr_paper: bool = True

    # Notifications
    pushover_user_key: str = ""
    pushover_app_token: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # API (Phase 2)
    api_token: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_host: str = "0.0.0.0"
    # Railway sets PORT, fall back to API_PORT for local dev, then 8000
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "API_PORT"),
    )


def get_settings() -> Settings:
    """Load settings fresh (re-reads env). Use this in tests after monkeypatching."""
    return Settings()


settings = get_settings()


# ============================================================================
# YAML config models
# ============================================================================

class SectorConfig(BaseModel):
    display_name: str
    description: str
    sub_sectors: list[str]
    default_impact_ceiling: int = Field(ge=1, le=5)
    typical_timeframes: list[str]
    sources_critical: list[str] = []
    notes: str = ""


class CatalystConfig(BaseModel):
    display_name: str
    sectors: list[str]
    typical_impact: int = Field(ge=1, le=5)
    typical_timeframe: str
    direction: str  # bullish | bearish | neutral
    patterns: list[str] = []
    baseline_hit_rate: float | None = None
    notes: str = ""


class PositionRisk(BaseModel):
    max_per_trade_usd: float
    max_concurrent_positions: int
    max_per_sector_pct: int
    max_per_ticker_lifetime_usd: float


class CapitalRisk(BaseModel):
    monthly_deployment_cap_usd: float
    reserve_pct: int


class CircuitBreakers(BaseModel):
    daily_loss_halt_pct: int
    weekly_loss_halt_pct: int
    consecutive_loss_count: int


class ExecutionRisk(BaseModel):
    default_mode: str
    shadow_first_n_trades: int
    live_first_n_trades_require_approval: int
    kill_switch_enabled: bool


class AccountRisk(BaseModel):
    type: str
    margin: bool
    options: bool
    shorts: bool
    currency: str


class RiskConfig(BaseModel):
    position: PositionRisk
    capital: CapitalRisk
    circuit_breakers: CircuitBreakers
    execution: ExecutionRisk
    account: AccountRisk


class SourceConfig(BaseModel):
    display_name: str
    type: str
    cost: str  # free | paid
    monthly_usd: float = 0
    trust: int = Field(ge=1, le=5)
    rate_limit_per_minute: int = 60
    base_url: str = ""
    sectors: list[str]
    active: bool
    notes: str = ""


class WatchlistTicker(BaseModel):
    symbol: str
    exchange: str
    name: str
    sector: str
    sub_sector: str = ""
    thesis: str
    alert_min_conviction: int = Field(ge=1, le=5, default=3)
    aliases: list[str] = Field(
        default_factory=list,
        description="Other names or former tickers this company has been known as. "
                    "Used by the classifier to match news headlines.",
    )
    notes: str = ""


# ============================================================================
# Loaders
# ============================================================================

def _load_yaml(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def load_sectors() -> dict[str, SectorConfig]:
    raw = _load_yaml("sectors.yaml")
    return {name: SectorConfig(**body) for name, body in raw["sectors"].items()}


def load_catalysts() -> dict[str, CatalystConfig]:
    raw = _load_yaml("catalysts.yaml")
    return {name: CatalystConfig(**body) for name, body in raw["catalysts"].items()}


def load_risk() -> RiskConfig:
    raw = _load_yaml("risk.yaml")
    return RiskConfig(**raw)


def load_sources() -> dict[str, SourceConfig]:
    raw = _load_yaml("sources.yaml")
    return {name: SourceConfig(**body) for name, body in raw["sources"].items()}


def load_watchlist() -> list[WatchlistTicker]:
    raw = _load_yaml("watchlist.yaml")
    return [WatchlistTicker(**t) for t in raw["tickers"]]


def load_all() -> dict[str, Any]:
    """Load and validate all YAML configs. Raises on validation failure."""
    return {
        "sectors": load_sectors(),
        "catalysts": load_catalysts(),
        "risk": load_risk(),
        "sources": load_sources(),
        "watchlist": load_watchlist(),
    }
