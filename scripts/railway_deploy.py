"""Provision the shadowinvestor stack on Railway via GraphQL.

The Railway CLI's write-op auth flow is broken in non-interactive environments,
so this script bypasses the CLI and talks directly to backboard.railway.com
using the access token stored in ~/.railway/config.json.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import httpx

GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
PROJECT_ID = "e05eaef6-387d-43e3-ae1b-71dbbf1b09bf"
GITHUB_REPO = "fredd-b/shadowinvestor"
POSTGRES_IMAGE = "ghcr.io/railwayapp-templates/postgres-ssl:latest"

CONFIG_PATH = Path.home() / ".railway" / "config.json"


def get_token() -> str:
    """Read the Railway CLI access token from its config file."""
    if not CONFIG_PATH.exists():
        sys.exit(f"Railway config not found at {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text())
    token = cfg.get("user", {}).get("accessToken")
    if not token:
        sys.exit("No accessToken in Railway config")
    return token


def gql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict:
    """Execute a GraphQL query/mutation. Raises on errors."""
    response = httpx.post(
        GRAPHQL_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data and data["errors"]:
        first = data["errors"][0]
        msg = first.get("message", "unknown")
        path = ".".join(str(p) for p in first.get("path", []))
        raise RuntimeError(f"{msg} (at {path})" if path else msg)
    return data["data"]


def get_environment_id(token: str, project_id: str, env_name: str = "production") -> str:
    """Look up the production environment id for the project."""
    data = gql(
        token,
        """
        query($id: String!) {
            project(id: $id) {
                environments {
                    edges {
                        node { id name }
                    }
                }
            }
        }
        """,
        {"id": project_id},
    )
    for edge in data["project"]["environments"]["edges"]:
        if edge["node"]["name"] == env_name:
            return edge["node"]["id"]
    raise RuntimeError(f"environment {env_name!r} not found in project")


def list_services(token: str, project_id: str) -> list[dict]:
    """List existing services in the project."""
    data = gql(
        token,
        """
        query($id: String!) {
            project(id: $id) {
                services {
                    edges {
                        node {
                            id
                            name
                            serviceInstances { edges { node { id source { image repo } } } }
                        }
                    }
                }
            }
        }
        """,
        {"id": project_id},
    )
    return [edge["node"] for edge in data["project"]["services"]["edges"]]


def create_service(
    token: str,
    project_id: str,
    name: str,
    source: dict,
) -> str:
    """Create a service. Returns the service id."""
    data = gql(
        token,
        """
        mutation($input: ServiceCreateInput!) {
            serviceCreate(input: $input) { id name }
        }
        """,
        {
            "input": {
                "projectId": project_id,
                "name": name,
                "source": source,
            }
        },
    )
    sid = data["serviceCreate"]["id"]
    print(f"  ✓ created service {name!r} → {sid}")
    return sid


def upsert_variable(
    token: str,
    project_id: str,
    environment_id: str,
    service_id: str,
    name: str,
    value: str,
) -> None:
    """Set a single env var on a service."""
    gql(
        token,
        """
        mutation($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """,
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": service_id,
                "name": name,
                "value": value,
            }
        },
    )


def deploy_service(token: str, service_id: str, environment_id: str) -> str:
    """Trigger a deployment for a service."""
    data = gql(
        token,
        """
        mutation($serviceId: String!, $environmentId: String!) {
            serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
        }
        """,
        {"serviceId": service_id, "environmentId": environment_id},
    )
    return data["serviceInstanceDeployV2"]


def create_service_domain(token: str, service_id: str, environment_id: str) -> str:
    """Generate a public *.up.railway.app domain for the service. Returns full URL."""
    data = gql(
        token,
        """
        mutation($input: ServiceDomainCreateInput!) {
            serviceDomainCreate(input: $input) {
                domain
                targetPort
            }
        }
        """,
        {
            "input": {
                "serviceId": service_id,
                "environmentId": environment_id,
            }
        },
    )
    return data["serviceDomainCreate"]["domain"]


def update_service_instance_start_cmd(
    token: str,
    service_id: str,
    environment_id: str,
    start_command: str,
) -> None:
    """Override the start command for the service in this environment."""
    gql(
        token,
        """
        mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
            serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
        }
        """,
        {
            "serviceId": service_id,
            "environmentId": environment_id,
            "input": {"startCommand": start_command},
        },
    )


def main() -> None:
    token = get_token()
    print("== Railway provision via GraphQL ==")

    print(f"\n[1/7] Looking up production environment for project {PROJECT_ID[:8]}...")
    env_id = get_environment_id(token, PROJECT_ID)
    print(f"  ✓ environment id: {env_id}")

    print("\n[2/7] Checking existing services...")
    existing = list_services(token, PROJECT_ID)
    by_name = {s["name"]: s for s in existing}
    print(f"  found {len(existing)} existing service(s): {[s['name'] for s in existing]}")

    # Postgres
    print("\n[3/7] Provisioning Postgres service...")
    if "Postgres" in by_name:
        pg_id = by_name["Postgres"]["id"]
        print(f"  ↻ postgres already exists → {pg_id}")
    else:
        pg_id = create_service(
            token, PROJECT_ID, "Postgres",
            source={"image": POSTGRES_IMAGE},
        )

    # API service
    print("\n[4/7] Provisioning shadowinvestor-api service from GitHub...")
    if "shadowinvestor-api" in by_name:
        api_id = by_name["shadowinvestor-api"]["id"]
        print(f"  ↻ api service already exists → {api_id}")
    else:
        api_id = create_service(
            token, PROJECT_ID, "shadowinvestor-api",
            source={"repo": GITHUB_REPO},
        )

    # Scheduler service
    print("\n[5/7] Provisioning shadowinvestor-scheduler service from GitHub...")
    if "shadowinvestor-scheduler" in by_name:
        sched_id = by_name["shadowinvestor-scheduler"]["id"]
        print(f"  ↻ scheduler service already exists → {sched_id}")
    else:
        sched_id = create_service(
            token, PROJECT_ID, "shadowinvestor-scheduler",
            source={"repo": GITHUB_REPO},
        )

    # Generate API token
    api_token_value = secrets.token_hex(32)

    print("\n[6/7] Setting environment variables...")
    common_vars = {
        "MODE": "shadow",
        "TZ": "Asia/Dubai",
        "ENVIRONMENT": "prod",
        "API_TOKEN": api_token_value,
        "CORS_ORIGINS": "https://shadowinvestor.vercel.app,https://shadowinvestor-fred.vercel.app",
        # Reference the Postgres service's DATABASE_URL via Railway template variable
        "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
    }
    for k, v in common_vars.items():
        upsert_variable(token, PROJECT_ID, env_id, api_id, k, v)
        upsert_variable(token, PROJECT_ID, env_id, sched_id, k, v)
    print(f"  ✓ set {len(common_vars)} vars on api + scheduler")

    # Override scheduler start command
    print("  setting scheduler start command...")
    try:
        update_service_instance_start_cmd(
            token, sched_id, env_id,
            start_command="fesi schedule run",
        )
        print("  ✓ scheduler will run `fesi schedule run`")
    except Exception as e:
        print(f"  ⚠ failed to set start cmd via API: {e}")

    print("\n[7/7] Generating public domain for API...")
    try:
        domain = create_service_domain(token, api_id, env_id)
        api_url = f"https://{domain}"
        print(f"  ✓ {api_url}")
    except Exception as e:
        print(f"  ⚠ domain creation failed: {e}")
        api_url = "(domain creation failed — check Railway dashboard)"

    print("\n[deploy] Triggering deploys...")
    for name, sid in [("postgres", pg_id), ("api", api_id), ("scheduler", sched_id)]:
        try:
            deploy_id = deploy_service(token, sid, env_id)
            print(f"  ✓ {name} deploying → {deploy_id}")
        except Exception as e:
            print(f"  ⚠ {name} deploy failed: {e}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"  Project URL:      https://railway.com/project/{PROJECT_ID}")
    print(f"  API URL:          {api_url}")
    print(f"  API token:        {api_token_value}")
    print()
    print("Next: run scripts/wire_vercel.py to swap Vercel env vars.")


if __name__ == "__main__":
    main()
