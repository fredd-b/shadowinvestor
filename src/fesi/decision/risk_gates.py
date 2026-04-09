"""Risk gates — the four hard checks every 'buy' decision must pass.

Each gate returns (passed: bool, reason: str). If any gate fails, the
final decision is forced to 'no_buy' regardless of conviction.
"""
from __future__ import annotations

from sqlalchemy.engine import Connection

from fesi.config import RiskConfig
from fesi.store.decisions import (
    count_concurrent_buys,
    get_sector_exposure,
    total_deployed_this_month,
)


def check_position_size(
    intended_position_usd: float, risk: RiskConfig
) -> tuple[bool, str]:
    if intended_position_usd > risk.position.max_per_trade_usd:
        return False, (
            f"position ${intended_position_usd:.0f} exceeds max "
            f"${risk.position.max_per_trade_usd:.0f} per trade"
        )
    return True, "ok"


def check_concurrent_positions(
    conn: Connection, risk: RiskConfig, mode: str
) -> tuple[bool, str]:
    n = count_concurrent_buys(conn, mode)
    if n >= risk.position.max_concurrent_positions:
        return False, (
            f"already at {n}/{risk.position.max_concurrent_positions} "
            "concurrent positions"
        )
    return True, "ok"


def check_sector_concentration(
    conn: Connection,
    sector: str,
    intended_position_usd: float,
    risk: RiskConfig,
    mode: str,
) -> tuple[bool, str]:
    exposure = get_sector_exposure(conn, mode)
    current_in_sector = exposure.get(sector, 0.0)
    monthly_cap = risk.capital.monthly_deployment_cap_usd
    sector_cap = monthly_cap * (risk.position.max_per_sector_pct / 100.0)
    new_total = current_in_sector + intended_position_usd
    if new_total > sector_cap:
        return False, (
            f"sector {sector} would be ${new_total:.0f}, exceeding "
            f"${sector_cap:.0f} ({risk.position.max_per_sector_pct}% of monthly cap)"
        )
    return True, "ok"


def check_circuit_breaker(
    conn: Connection, risk: RiskConfig, mode: str
) -> tuple[bool, str]:
    """Phase 1 simplification: only enforces monthly deployment cap.

    Daily/weekly P&L circuit breakers come online in Phase 4 once we have
    realized P&L from live trades. In shadow mode there's no realized loss to
    react to.
    """
    deployed = total_deployed_this_month(conn, mode)
    cap = risk.capital.monthly_deployment_cap_usd
    if deployed >= cap:
        return False, (
            f"monthly deployment ${deployed:.0f} ≥ cap ${cap:.0f}; halt new entries"
        )
    return True, "ok"


def check_all(
    conn: Connection,
    *,
    sector: str,
    intended_position_usd: float,
    risk: RiskConfig,
    mode: str,
) -> dict:
    """Run all 4 risk gates. Returns dict with each gate's pass/fail + reasons."""
    pos_ok, pos_reason = check_position_size(intended_position_usd, risk)
    conc_ok, conc_reason = check_concurrent_positions(conn, risk, mode)
    sec_ok, sec_reason = check_sector_concentration(
        conn, sector, intended_position_usd, risk, mode
    )
    cb_ok, cb_reason = check_circuit_breaker(conn, risk, mode)

    return {
        "all_passed": pos_ok and conc_ok and sec_ok and cb_ok,
        "position_size": {"passed": pos_ok, "reason": pos_reason},
        "concurrent": {"passed": conc_ok, "reason": conc_reason},
        "sector_concentration": {"passed": sec_ok, "reason": sec_reason},
        "circuit_breaker": {"passed": cb_ok, "reason": cb_reason},
    }
