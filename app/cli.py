"""Local JSON CLI using the desktop queue, permissions and execution engine."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time

READ_ONLY_ACTIONS = {
    "start",
    "goto",
    "wait_element",
    "wait_for_load_state",
    "sleep",
    "extract_text",
    "write_file",
}


def definition_hash(steps):
    return hashlib.sha256(
        json.dumps(steps, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def validate_readonly(steps):
    if not steps or any(
        not isinstance(step, dict) or step.get("action") not in READ_ONLY_ACTIONS
        for step in steps
    ):
        raise ValueError(
            "CLI runs only reviewed read-only extraction workflows; use desktop Runs for interactive scenarios"
        )
    if not any(step.get("action") == "extract_text" for step in steps):
        raise ValueError("A CLI workflow must extract an output")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "history", "run"))
    parser.add_argument("--scenario", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--expected-hash", default="")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    app = None
    result, code = {}, 0
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from app.services.run_queue import TERMINAL
            from app.services.server_client import get_server_session
            from app.storage import db
            from app.ui.qml_app import QmlApplication

            db.init_db()
            if get_server_session().enabled:
                raise ValueError("CLI supports local workspaces only")
            app = QmlApplication([sys.argv[0]])
            if args.command == "list":
                result = {
                    "scenarios": [
                        {"name": s.name, "hash": definition_hash(s.steps)}
                        for s in db.db_get_scenarios()
                    ],
                    "profiles": [a["name"] for a in db.db_get_accounts()],
                }
            elif args.command == "history":
                result = {
                    "runs": app.operations.history.list(
                        app.operations._workspace(), 100
                    )
                }
            else:
                if (
                    not args.confirm
                    or not args.scenario
                    or not args.profile
                    or not 1 <= args.timeout <= 3600
                ):
                    raise ValueError(
                        "Run requires --scenario, --profile, --confirm and a timeout of 1..3600 seconds"
                    )
                scenario = db.db_get_scenario(args.scenario)
                if scenario is None:
                    raise ValueError("Scenario not found")
                validate_readonly(scenario.steps)
                if args.expected_hash and args.expected_hash != definition_hash(
                    scenario.steps
                ):
                    raise ValueError("Workflow changed since approval")
                if any(
                    job["status"] not in TERMINAL
                    for job in app.operations.queue.snapshot()
                ):
                    raise ValueError("Review unfinished desktop jobs before using CLI")
                messages = []
                app.operations.message.connect(messages.append)
                previous = {job["id"] for job in app.operations.queue.snapshot()}
                app.operations.enqueue(args.profile, args.scenario, "", "unchanged", "")
                jobs = [
                    j
                    for j in app.operations.queue.snapshot()
                    if j["id"] not in previous
                ]
                if len(jobs) != 1:
                    raise ValueError(
                        messages[-1] if messages else "Could not queue workflow"
                    )
                job_id = jobs[0]["id"]
                if args.expected_hash and args.expected_hash != definition_hash(
                    jobs[0]["steps"]
                ):
                    app.operations.cancel(job_id)
                    raise ValueError(
                        "Workflow changed while queuing; canceled before execution"
                    )
                validate_readonly(jobs[0]["steps"])
                app.operations.configure(1, False)
                deadline = time.monotonic() + args.timeout
                while True:
                    app.app.processEvents()
                    job = next(
                        j for j in app.operations.queue.snapshot() if j["id"] == job_id
                    )
                    if job["status"] in TERMINAL:
                        result = {"run": app.operations.history.get(job_id) or job}
                        code = 0 if job["status"] == "success" else 1
                        break
                    if time.monotonic() >= deadline:
                        app.operations.cancel(job_id)
                        raise TimeoutError("CLI timeout; this run was canceled")
                    time.sleep(0.05)
    except (Exception, KeyboardInterrupt) as exc:
        result, code = {"error": str(exc) or "Interrupted"}, 1
    finally:
        if app is not None:
            app.ai.shutdown()
            app.recorder.shutdown()
            app.operations.shutdown()
            app._workspace_lock.unlock()
    print(json.dumps(result, ensure_ascii=False))
    return code
