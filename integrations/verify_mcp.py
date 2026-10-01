"""Explicit stdio integration smoke; runs the supplied local read-only workflow."""

import argparse
import asyncio
import json
from pathlib import Path

from mcp import Client, StdioServerParameters


async def check(args):
    repo = Path(__file__).resolve().parents[1]
    import sys

    command = [
        str(repo / "integrations" / "mcp_server.py"),
        "--python",
        args.python,
        "--data-dir",
        args.data_dir,
    ]
    async with Client(
        StdioServerParameters(command=sys.executable, args=command, cwd=repo)
    ) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {"list_workflows", "run_history"}
        for name in ("list_workflows", "run_history"):
            result = await client.call_tool(name)
            assert not result.is_error, result
            json.loads(result.content[0].text)
    command += ["--allow-scenario", args.scenario, "--allow-profile", args.profile]
    async with Client(
        StdioServerParameters(command=sys.executable, args=command, cwd=repo)
    ) as client:
        tools = await client.list_tools()
        run_tool = next(
            tool for tool in tools.tools if tool.name == "run_approved_workflow"
        )
        assert not run_tool.input_schema.get("properties"), run_tool.input_schema
        result = await client.call_tool(
            "run_approved_workflow", read_timeout_seconds=140
        )
        assert not result.is_error, result
        assert json.loads(result.content[0].text)["run"]["status"] == "success"
    print(
        json.dumps(
            {
                "passed": True,
                "checks": [
                    "stdio handshake",
                    "readonly tools",
                    "list/history",
                    "startup allowlist",
                    "no execution arguments",
                    "actual queue run",
                ],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--profile", required=True)
    asyncio.run(check(parser.parse_args()))
