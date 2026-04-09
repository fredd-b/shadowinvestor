"""FastAPI app entrypoint.

Run locally:
    fesi api run        # uvicorn on $API_HOST:$API_PORT
    or
    uvicorn fesi.api.main:app --reload --port 8000

Run on Railway: the Dockerfile sets CMD to `uvicorn fesi.api.main:app
--host 0.0.0.0 --port $PORT`.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fesi import __version__
from fesi.config import get_settings
from fesi.logging import get_logger, setup_logging

log = get_logger(__name__)

setup_logging("INFO")

app = FastAPI(
    title="ShadowInvestor API",
    description="Personal catalyst-driven shadow trading signal system",
    version=__version__,
)


# ---- CORS ----
def _build_cors_origins() -> list[str]:
    origins = get_settings().cors_origins
    return [o.strip() for o in origins.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---- Auth ----
security = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    """Require a valid bearer token if API_TOKEN env var is set.

    If API_TOKEN is empty, auth is disabled (local dev mode). In production
    on Railway, API_TOKEN MUST be set or the API is unauthenticated.
    """
    expected = get_settings().api_token
    if not expected:
        return  # local dev, no token configured
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )


# ---- Routes ----
from fesi.api import routes  # noqa: E402

app.include_router(routes.router, dependencies=[Depends(require_auth)])
app.include_router(routes.health_router)  # health is unauthenticated


@app.on_event("startup")
def on_startup() -> None:
    """At startup: ensure schema exists. Idempotent — safe to run on every boot."""
    from fesi.db import init_db
    from fesi.db import connect
    from fesi.store.tickers import load_watchlist_to_db

    log.info("api_startup", version=__version__)
    init_db()
    with connect() as conn:
        n = load_watchlist_to_db(conn)
    log.info("watchlist_loaded_at_startup", count=n)
