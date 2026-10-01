"""Run the static n8n example in an isolated local Windows runtime/workspace."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n8n", type=Path, required=True, help="Path to n8n's bin/n8n script"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    root = Path(tempfile.mkdtemp(prefix="camouflow-n8n-"))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    sys.path.insert(0, str(repo))
    from app.services.ai_agent.templates import DemoServer, template
    from app.storage import db

    db.init_db()
    server = DemoServer()
    try:
        db.db_add_account(
            {
                "name": "n8n-demo",
                "browser_engine": "camoufox",
                "camoufox_settings": {"headless": True},
                "extra_fields": {"catalog_url": server.url},
            }
        )
        starter = template("catalog")
        db.db_save_scenario(starter["name"], starter["steps"], starter["description"])
        workflow = json.loads(
            (repo / "integrations/n8n-local-catalog.json").read_text(encoding="utf-8")
        )
        workflow["id"] = "CamouFlowSmoke01"
        command = subprocess.list2cmdline(
            [
                sys.executable,
                str(repo / "main.py"),
                "--cli",
                "run",
                "--scenario",
                "Catalog to JSON",
                "--profile",
                "n8n-demo",
                "--confirm",
                "--timeout",
                "120",
            ]
        )
        next(node for node in workflow["nodes"] if node["id"] == "cli")["parameters"][
            "command"
        ] = command
        workflow_file = root / "workflow.json"
        workflow_file.write_text(json.dumps(workflow), encoding="utf-8")
        env = {
            **os.environ,
            "N8N_USER_FOLDER": str(root / "n8n"),
            "N8N_DIAGNOSTICS_ENABLED": "false",
            "N8N_VERSION_NOTIFICATIONS_ENABLED": "false",
            "N8N_TEMPLATES_ENABLED": "false",
            "NODES_INCLUDE": json.dumps(
                [
                    "n8n-nodes-base.manualTrigger",
                    "n8n-nodes-base.executeCommand",
                    "n8n-nodes-base.code",
                ]
            ),
            "NODES_EXCLUDE": json.dumps(["n8n-nodes-base.localFileTrigger"]),
            "N8N_LOG_LEVEL": "info",
            "N8N_PYTHON_ENABLED": "false",
        }
        for command_args, label in (
            (["import:workflow", "--input", str(workflow_file)], "import"),
            (["execute", "--id", workflow["id"], "--rawOutput"], "execute"),
        ):
            result = subprocess.run(
                ["node", str(args.n8n.resolve()), *command_args],
                env=env,
                cwd=repo,
                capture_output=True,
                encoding="utf-8",
                timeout=180,
            )
            (root / f"{label}.log").write_text(
                result.stdout + result.stderr, encoding="utf-8"
            )
            if result.returncode:
                raise RuntimeError(
                    f"n8n {label} failed; inspect {root / (label + '.log')}"
                )
        execution = None
        decoder = json.JSONDecoder()
        for offset, char in enumerate(result.stdout):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(result.stdout[offset:])
            except ValueError:
                continue
            if (
                isinstance(candidate, dict)
                and candidate.get("status") == "success"
                and "data" in candidate
            ):
                execution = candidate
                break
        assert execution is not None, "n8n did not return a successful execution record"
        parsed = execution["data"]["resultData"]["runData"]["Parse CLI result"][0][
            "data"
        ]["main"][0][0]["json"]
        assert parsed["run"]["status"] == "success", "n8n did not parse the CLI result"
        from app.services.run_history import RunHistory

        rows = RunHistory(db.SETTINGS_DIR / "run-history.json").list("local")
        assert rows and rows[0]["status"] == "success", "n8n did not complete a CLI run"
        exports = list((root / "outputs").glob("catalog-*.json"))
        assert exports and len(json.loads(exports[0].read_text(encoding="utf-8"))) == 3
        report = {
            "passed": True,
            "data_root": str(root),
            "checks": [
                "actual n8n import",
                "static command",
                "real browser CLI queue",
                "JSON artifact",
                "run history",
                "parse result node",
            ],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    finally:
        server.close()


if __name__ == "__main__":
    main()
