"""Opt-in stdio MCP adapter; no arbitrary browser actions or shell execution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def invoke_cli(
    python: str, repo: Path, data_dir: Path, arguments: list[str], timeout=30
):
    process = subprocess.run(
        [python, str(repo / "main.py"), "--cli", *arguments],
        cwd=repo,
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(data_dir)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        shell=False,
    )
    try:
        result = json.loads(process.stdout)
    except ValueError as exc:
        raise RuntimeError(
            "CLI returned invalid JSON; check the local runtime installation"
        ) from exc
    if process.returncode:
        raise RuntimeError(
            result.get("error") or "Workflow failed; inspect desktop run history"
        )
    return result


def create_server(python, repo, data_dir, scenario="", profile=""):
    from mcp.server import MCPServer

    server = MCPServer("CamouFlow local workflows")

    @server.tool()
    def list_workflows() -> dict:
        """List local workflow names, hashes and profile names; close the desktop first."""
        return invoke_cli(python, repo, data_dir, ["list"])

    @server.tool()
    def run_history() -> dict:
        """Read the latest local workflow run statuses and artifact paths."""
        return invoke_cli(python, repo, data_dir, ["history"])

    if scenario or profile:
        if not scenario or not profile:
            raise ValueError(
                "An execution allowlist needs both --allow-scenario and --allow-profile"
            )
        listing = invoke_cli(python, repo, data_dir, ["list"])
        allowed = next(
            (row for row in listing["scenarios"] if row["name"] == scenario), None
        )
        if allowed is None or profile not in listing["profiles"]:
            raise ValueError("Allowlisted scenario or profile does not exist")
        digest = allowed["hash"]

        @server.tool()
        def run_approved_workflow() -> dict:
            """Run only the startup-approved workflow/profile, unchanged and read-only. A run has a 120-second budget; canceling an MCP request does not cancel the local run."""
            return invoke_cli(
                python,
                repo,
                data_dir,
                [
                    "run",
                    "--scenario",
                    scenario,
                    "--profile",
                    profile,
                    "--confirm",
                    "--expected-hash",
                    digest,
                    "--timeout",
                    "120",
                ],
                timeout=None,
            )

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        required=True,
        help="Absolute path to CamouFlow's virtualenv python.exe",
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--allow-scenario", default="")
    parser.add_argument("--allow-profile", default="")
    args = parser.parse_args()
    python, data_dir = Path(args.python).resolve(), Path(args.data_dir).resolve()
    if not python.is_file() or not data_dir.is_dir():
        parser.error("Python and the existing CamouFlow data directory must exist")
    server = create_server(
        str(python),
        Path(__file__).resolve().parents[1],
        data_dir,
        args.allow_scenario,
        args.allow_profile,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
