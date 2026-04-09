"""FastAPI HTTP layer — exposes the FESI database as a REST API.

Authentication: bearer token via API_TOKEN env var (single shared secret).
The Vercel frontend stores this in a server-only env var.

CORS: env-var driven via CORS_ORIGINS (comma-separated).

This module is the only thing the frontend touches. The scheduler service
runs the same code as the API process (different command) and writes to
the same Postgres database.
"""
