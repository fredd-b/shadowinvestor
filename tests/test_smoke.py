"""Smoke tests — sanity that the package is wired up and configs are valid."""
from __future__ import annotations


def test_import_package():
    import fesi
    assert fesi.__version__


def test_import_submodules():
    import fesi.cli  # noqa: F401
    import fesi.config  # noqa: F401
    import fesi.db  # noqa: F401
    import fesi.ingest.base  # noqa: F401
    import fesi.store.schema  # noqa: F401


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
    active_keys = {k for k, s in cfg["sources"].items() if s.active}
    assert "fda_openfda" in active_keys
    assert "sec_edgar" in active_keys
    assert "clinicaltrials_gov" in active_keys


def test_init_db_creates_all_tables(tmp_db):
    """init_db() should create every table defined in schema.py, idempotently."""
    from sqlalchemy import inspect
    from fesi.db import get_engine, init_db
    from fesi.store.schema import metadata

    expected = {t.name for t in metadata.sorted_tables}
    inspector = inspect(get_engine())
    actual = set(inspector.get_table_names())

    missing = expected - actual
    assert not missing, f"missing tables after init_db: {missing}"

    # Re-running should be a no-op (no new tables created)
    second = init_db()
    assert second["created"] == []
