"""Command line interface for FESI.

Phase 1 commands:
  fesi --version
  fesi status
  fesi init-db
  fesi config-check
  fesi tickers list
  fesi prices fetch <symbol>
  fesi prices fetch-watchlist
  fesi ingest <source>           # source: sec-edgar | fda | clinicaltrials | wires | all
  fesi run-pipeline              # full ingest → decide → digest cycle
  fesi outcomes update           # daily T+N return computation
  fesi schedule run              # start the long-running scheduler
  fesi digest last               # print the most recent digest
"""
from __future__ import annotations

import json
import sys

import click

from fesi import __version__
from fesi.logging import get_logger, setup_logging

log = get_logger(__name__)


@click.group()
@click.option("--log-level", default="INFO", help="Log level")
@click.version_option(version=__version__, prog_name="fesi")
def cli(log_level: str) -> None:
    """FESI — Finance Early Signals & Investor."""
    setup_logging(log_level)


@cli.command("init-db")
def init_db_cmd() -> None:
    """Apply DB migrations and load watchlist."""
    from fesi.db import connect, get_db_path, init_db
    from fesi.store.tickers import load_watchlist_to_db

    result = init_db()
    click.echo(f"Database: {get_db_path()}")
    click.echo(json.dumps(result, indent=2))

    with connect() as conn:
        n = load_watchlist_to_db(conn)
    click.echo(f"Loaded {n} watchlist tickers into the tickers table.")


@cli.command("config-check")
def config_check_cmd() -> None:
    """Load and validate all YAML configs."""
    from fesi.config import load_all
    try:
        cfg = load_all()
    except Exception as exc:
        click.echo(f"Config validation FAILED: {exc}", err=True)
        sys.exit(1)
    click.echo(
        f"OK — loaded {len(cfg['sectors'])} sectors, "
        f"{len(cfg['catalysts'])} catalysts, "
        f"{len(cfg['sources'])} sources, "
        f"{len(cfg['watchlist'])} watchlist tickers"
    )
    active_sources = sum(1 for s in cfg['sources'].values() if s.active)
    click.echo(f"Active sources: {active_sources}/{len(cfg['sources'])}")


@cli.command("status")
def status_cmd() -> None:
    """Show current FESI runtime settings."""
    from fesi.config import get_settings
    from fesi.intelligence.llm import has_anthropic
    s = get_settings()
    click.echo(f"version:     {__version__}")
    click.echo(f"mode:        {s.mode}")
    click.echo(f"environment: {s.environment}")
    click.echo(f"database:    {s.database_url}")
    click.echo(f"timezone:    {s.tz}")
    click.echo(f"anthropic:   {'configured' if has_anthropic() else 'not set (fallback scoring)'}")
    click.echo(f"pushover:    {'configured' if s.pushover_user_key else 'not set'}")
    click.echo(f"telegram:    {'configured' if s.telegram_bot_token else 'not set'}")


# ============================================================================
# Tickers
# ============================================================================

@cli.group()
def tickers() -> None:
    """Tickers commands."""


@tickers.command("list")
def tickers_list() -> None:
    from fesi.db import connect
    from fesi.store.tickers import list_watchlist_tickers
    with connect() as conn:
        rows = list_watchlist_tickers(conn)
    if not rows:
        click.echo("No watchlist tickers loaded. Run `fesi init-db` first.")
        return
    for r in rows:
        click.echo(
            f"{r['symbol']:10s} {r['exchange']:8s} {r['sector']:32s} {r['name']}"
        )


# ============================================================================
# Prices
# ============================================================================

@cli.group()
def prices() -> None:
    """Price data commands."""


@prices.command("fetch")
@click.argument("symbol")
@click.option("--days", default=90, help="Days of history to fetch")
def prices_fetch(symbol: str, days: int) -> None:
    from fesi.db import connect
    from fesi.store.prices import fetch_yfinance_history
    with connect() as conn:
        result = fetch_yfinance_history(conn, symbol, days=days)
    click.echo(json.dumps(result, indent=2))


@prices.command("fetch-watchlist")
@click.option("--days", default=90, help="Days of history to fetch")
def prices_fetch_watchlist(days: int) -> None:
    from fesi.db import connect
    from fesi.store.prices import fetch_yfinance_history
    from fesi.store.tickers import list_watchlist_tickers
    with connect() as conn:
        tickers_list = list_watchlist_tickers(conn)
        results = []
        with click.progressbar(tickers_list, label="Fetching prices") as bar:
            for t in bar:
                r = fetch_yfinance_history(
                    conn, t["symbol"], days=days, exchange=t["exchange"]
                )
                results.append(r)
    inserted = sum(r.get("inserted", 0) for r in results)
    failed = sum(1 for r in results if "error" in r)
    click.echo(f"Done: {inserted} bars inserted across {len(results)} tickers ({failed} failures)")


# ============================================================================
# Ingest
# ============================================================================

@cli.group()
def ingest() -> None:
    """Ingest from data sources."""


@ingest.command("sec-edgar")
def ingest_sec() -> None:
    from fesi.db import connect
    from fesi.ingest.sec_edgar import SecEdgarAdapter
    from fesi.store.raw_items import insert_raw_items
    items = SecEdgarAdapter().fetch()
    with connect() as conn:
        result = insert_raw_items(conn, items)
    click.echo(json.dumps({"fetched": len(items), **result}, indent=2))


@ingest.command("fda")
def ingest_fda() -> None:
    from fesi.db import connect
    from fesi.ingest.fda_openfda import FdaOpenfdaAdapter
    from fesi.store.raw_items import insert_raw_items
    items = FdaOpenfdaAdapter().fetch()
    with connect() as conn:
        result = insert_raw_items(conn, items)
    click.echo(json.dumps({"fetched": len(items), **result}, indent=2))


@ingest.command("clinicaltrials")
def ingest_ct() -> None:
    from fesi.db import connect
    from fesi.ingest.clinicaltrials import ClinicalTrialsAdapter
    from fesi.store.raw_items import insert_raw_items
    items = ClinicalTrialsAdapter().fetch()
    with connect() as conn:
        result = insert_raw_items(conn, items)
    click.echo(json.dumps({"fetched": len(items), **result}, indent=2))


@ingest.command("wires")
def ingest_wires() -> None:
    from fesi.db import connect
    from fesi.ingest.wires import WiresAdapter
    from fesi.store.raw_items import insert_raw_items
    items = WiresAdapter().fetch()
    with connect() as conn:
        result = insert_raw_items(conn, items)
    click.echo(json.dumps({"fetched": len(items), **result}, indent=2))


@ingest.command("all")
def ingest_all() -> None:
    """Run all active ingest adapters in sequence."""
    from fesi.ops.pipeline import _ingest_all, PipelineRunStats
    from datetime import datetime, timezone
    from fesi.db import connect
    from fesi.store.raw_items import insert_raw_items
    stats = PipelineRunStats(started_at=datetime.now(timezone.utc))
    items = _ingest_all(only_sources=None, stats=stats)
    with connect() as conn:
        result = insert_raw_items(conn, items)
    click.echo(json.dumps({"fetched": len(items), **result, "errors": stats.errors}, indent=2))


# ============================================================================
# Pipeline / outcomes / schedule / digest
# ============================================================================

@cli.command("run-pipeline")
@click.option("--window", default=48, help="Scan window in hours")
@click.option("--silent/--noisy", default=False, help="Silent push notifications")
def run_pipeline_cmd(window: int, silent: bool) -> None:
    """Run one full pipeline cycle: ingest → decide → digest → notify."""
    from fesi.ops.pipeline import run_pipeline
    stats = run_pipeline(scan_window_hours=window, silent_alerts=silent)
    click.echo(json.dumps(stats.to_dict(), indent=2))


@cli.command("outcomes")
@click.argument("subcommand", type=click.Choice(["update"]))
def outcomes_cmd(subcommand: str) -> None:
    if subcommand == "update":
        from fesi.db import connect
        from fesi.store.outcomes import update_all_outcomes
        with connect() as conn:
            result = update_all_outcomes(conn)
        click.echo(json.dumps(result, indent=2))


@cli.group()
def schedule() -> None:
    """Scheduler commands."""


@schedule.command("run")
def schedule_run() -> None:
    """Start the long-running scheduler (5 scans/day in UAE timezone)."""
    from fesi.ops.scheduler import run_forever
    run_forever()


@cli.group()
def digest() -> None:
    """Digest commands."""


@digest.command("last")
def digest_last() -> None:
    """Print the most recent digest body."""
    from fesi.db import connect
    from fesi.store.digests import list_recent_digests, get_digest_by_id
    with connect() as conn:
        recent = list_recent_digests(conn, limit=1)
        if not recent:
            click.echo("No digests yet. Run `fesi run-pipeline` first.")
            return
        d = get_digest_by_id(conn, recent[0]["id"])
    click.echo(d["markdown_body"])


if __name__ == "__main__":
    cli()
