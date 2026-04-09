"""Swap Vercel env vars to point at the deployed Railway API.

Reads RAILWAY_API_URL and RAILWAY_API_TOKEN from CLI args, removes the old
placeholder values, sets the new ones, and triggers a production redeploy.

Usage:
    python scripts/wire_vercel.py <api_url> <api_token>
"""
from __future__ import annotations

import subprocess
import sys


def vercel(*args: str, cwd: str = "web") -> str:
    result = subprocess.run(
        ["vercel", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"FAIL: vercel {' '.join(args)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def remove_var(name: str) -> None:
    print(f"  removing old {name}...")
    # `vercel env rm` is interactive without --yes
    subprocess.run(
        ["vercel", "env", "rm", name, "production", "--yes"],
        cwd="web",
        capture_output=True,
        text=True,
    )


def add_var(name: str, value: str, sensitive: bool = False) -> None:
    print(f"  setting {name}...")
    args = ["env", "add", name, "production", "--value", value, "--yes"]
    if sensitive:
        args.append("--sensitive")
    out = vercel(*args)
    print(f"    {out.splitlines()[-1] if out else 'ok'}")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: python scripts/wire_vercel.py <api_url> <api_token>")
    api_url = sys.argv[1].rstrip("/")
    api_token = sys.argv[2]

    print(f"== Wiring Vercel to Railway ==")
    print(f"  API URL:   {api_url}")
    print(f"  API token: {api_token[:12]}...")

    print("\n[1/3] Removing placeholder env vars...")
    remove_var("API_BASE_URL")
    remove_var("API_TOKEN")

    print("\n[2/3] Setting fresh env vars...")
    add_var("API_BASE_URL", api_url)
    add_var("API_TOKEN", api_token, sensitive=True)

    print("\n[3/3] Redeploying Vercel...")
    out = vercel("deploy", "--prod", "--yes")
    print(out)
    print("\nDONE")


if __name__ == "__main__":
    main()
