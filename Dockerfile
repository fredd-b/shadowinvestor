# Dockerfile for ShadowInvestor — used by both the API and scheduler
# services on Railway. Same image, different start command.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

# System deps (psycopg, ssl certs, build essentials for any wheels needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the project (need pyproject + source for the install to work)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python deps
RUN pip install --upgrade pip wheel && pip install ".[ml]"

# Copy runtime config (separate layer so config edits don't reinstall deps)
COPY config/ ./config/

# Create runtime directories
RUN mkdir -p data logs models

# Default port (Railway sets $PORT)
EXPOSE 8000

# Health check uses the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

# Default command starts the API. The scheduler service overrides this with
# `fesi schedule run`.
CMD uvicorn fesi.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
