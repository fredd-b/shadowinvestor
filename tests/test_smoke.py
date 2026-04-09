"""Smoke tests — sanity that the package is wired up and configs are valid."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def test_import_package():
    import fesi
    assert fesi.__version__


def test_import_submodules():
    import fesi.cli  # noqa: F401
    import fesi.config  # noqa: F401
    import fesi.db  # noqa: F401
    import fesi.ingest.base  # noqa: F401


def test_load_all_configs():
    from fesi.config import load_all
    cfg = load_all()

    # Sectors — must include all 6 + the dedicated China biotech category
    assert "biotech_pharma" in cfg["sectors"]
    assert "china_biotech_us_pipeline" in cfg["sectors"]
    assert "ai_infrastructure" in cfg["sectors"]
    assert "crypto_to_ai_pivot" in cfg["sectors"]
    assert "commodities_critical_minerals" in cfg["sectors"]
    assert "binary_event_other" in cfg["sectors"]

    # Catalysts — should have a healthy library
    assert len(cfg["catalysts"]) >= 20
    assert "fda_approval" in cfg["catalysts"]
    assert "out_licensing_deal" in cfg["catalysts"]
    assert "miner_hpc_hosting_contract" in cfg["catalysts"]
    assert "mine_first_production" in cfg["catalysts"]

    # Risk — Fred's hard constraints
    risk = cfg["risk"]
    assert risk.account.type == "cash"
    assert risk.account.margin is False
    assert risk.account.options is False
    assert risk.account.shorts is False
    assert risk.position.max_per_trade_usd == 2000
    assert risk.capital.monthly_deployment_cap_usd == 10000
    assert risk.execution.default_mode == "shadow"

    # Watchlist — at least the seeds
    assert len(cfg["watchlist"]) >= 15
    symbols = {t.symbol for t in cfg["watchlist"]}
    assert "ONC" in symbols
    assert "9926.HK" in symbols   # Akeso — China biotech HK-listed
    assert "NXE" in symbols       # NexGen uranium

    # Sources — at least the free regulatory ones must be active
    active = [s for s in cfg["sources"].values() if s.active]
    active_keys = {k for k, s in cfg["sources"].items() if s.active}
    assert len(active) >= 3
    assert "fda_openfda" in active_keys
    assert "sec_edgar" in active_keys
    assert "clinicaltrials_gov" in active_keys


def test_initial_migration_applies_cleanly(tmp_path):
    """The initial schema SQL file should apply cleanly to a fresh DB."""
    project_root = Path(__file__).parent.parent
    sql_path = project_root / "src" / "fesi" / "migrations" / "001_initial_schema.sql"
    assert sql_path.exists(), f"missing migration file: {sql_path}"
    sql = sql_path.read_text()

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        for expected in [
            "raw_items", "tickers", "signals", "decisions",
            "trades", "outcomes", "prices", "embeddings",
            "catalyst_priors", "digests",
        ]:
            assert expected in tables, f"missing table: {expected}"
    finally:
        conn.close()
