"""Isolated QML/bridge smoke, including real read-only replay; no model requests."""

import json
import asyncio
import os
import tempfile
import time
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    root = Path(tempfile.mkdtemp(prefix="camouflow-ai-ui-"))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import QObject, QUrl
    from app.storage import db
    from app.ui.qml_app import QmlApplication
    from app.services.ai_agent.loop import save_transcript
    from app.services.server_client import get_server_session

    db.init_db()
    db.db_add_account({"name": "UI profile", "browser_engine": "camoufox"})
    app = QmlApplication(["AI UI smoke"])
    errors = []
    app.engine.warnings.connect(lambda es: errors.extend(e.toString() for e in es))

    def pump(until=lambda: False, timeout=1):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.app.processEvents()
            if until():
                return True
            time.sleep(0.01)
        return until()

    try:
        blocked = subprocess.run(
            [sys.executable, "main.py", "--cli", "list"],
            capture_output=True,
            encoding="utf-8",
            timeout=20,
        )
        assert (
            blocked.returncode == 1
            and "already open" in json.loads(blocked.stdout)["error"]
        )
        app.engine.load(QUrl.fromLocalFile(str(app.root_dir / "Main.qml")))
        assert app.engine.rootObjects()
        app.state.setPage("ScenarioAI")
        app.profiles.refresh()
        assert pump(lambda: bool(app.profiles._cached_account("UI profile")), 5)
        pump(timeout=0.3)
        panel = app.engine.rootObjects()[0].findChild(QObject, "aiAssistantPanel")
        assert panel
        assert "Configure" in app.ai.sessionIssue("UI profile")
        app.settings.saveAiSettings(
            True, "http://127.0.0.1:11434/v1", "", "fixture", "25"
        )
        pump(timeout=0.3)
        assert panel.property("sessionProblem") == "", panel.property("sessionProblem")
        task_input = app.engine.rootObjects()[0].findChild(QObject, "aiTaskInput")
        task_input.setProperty("text", "Keep this task while configuring the provider")
        app.state.setPage("Settings")
        pump(timeout=0.1)
        app.state.setPage("ScenarioAI")
        pump(timeout=0.1)
        assert app.engine.rootObjects()[0].findChild(QObject, "aiTaskInput") == task_input
        assert task_input.property("text") == "Keep this task while configuring the provider"
        app.ai._active = True
        app.ai.togglePause()
        assert app.ai.paused
        app.ai.togglePause()
        assert not app.ai.paused

        async def approve():
            task = asyncio.create_task(
                app.ai._before_action(
                    {"name": "click", "index": 0},
                    [{"text": "Preview", "selector": "button"}],
                )
            )
            await asyncio.sleep(0.05)
            assert app.ai.waiting
            app.ai.respond("Approved")
            assert await task == "Approved"
            assert not app.ai.waiting

        asyncio.run(approve())
        app.ai._active = False
        app.ai.installTemplate("catalog")
        assert db.db_get_scenario("Catalog to JSON")
        app.state.setPage("ScenarioAI")
        app.ai.prepareDemo()
        assert pump(lambda: bool(app.profiles._cached_account("AI demo")), 5)
        pump(timeout=0.3)
        combo = app.engine.rootObjects()[0].findChild(QObject, "aiProfileSelector")
        assert combo.property("currentText") == "AI demo"
        url = app.ai._demo.url
        result = {
            "task": "Extract synthetic catalog",
            "status": "success",
            "result": "3 rows",
            "steps": [
                {"action": "start"},
                {"action": "goto", "value": url},
                {
                    "action": "extract_text",
                    "selector": 'table[data-testid="catalog"]',
                    "to_var": "catalog",
                    "format": "table",
                    "require_nonempty": True,
                },
            ],
            "outputs": {
                "catalog": [
                    {"Name": "Notebook", "Price": "12", "Link": "/products/notebook"}
                ]
            },
            "output_sources": {"catalog": url},
            "events": [],
        }
        artifacts = root / "outputs" / "ai-runs" / "ui-smoke"
        save_transcript(result, artifacts)
        app.ai._session = get_server_session()
        app.ai._task = result["task"]
        app.ai._profile_name = "AI demo"
        app.ai._accept_result(result, str(artifacts))
        with patch(
            "app.ui.bridge.ai.get_server_session",
            return_value=SimpleNamespace(
                enabled=True,
                url="https://other.invalid",
                team_id="other",
                email="other",
            ),
        ):
            app.ai.save("Wrong workspace")
            assert not app.ai.busy and app.ai.hasDraft
        assert db.db_get_scenario("Wrong workspace") is None
        app.ai.exportResults(str(root / "catalog.csv"))
        assert (
            (root / "catalog.csv")
            .read_text(encoding="utf-8")
            .startswith("Name,Price,Link")
        )
        app.ai.setInputs(json.dumps({"catalog_url": url}))
        app.ai.exportWorkflow(str(root / "shared.json"))
        shared = json.loads((root / "shared.json").read_text(encoding="utf-8"))
        assert url not in json.dumps(shared)
        app.ai.verifyDraft()
        assert app.ai.active
        assert pump(lambda: not app.ai.busy, 90), "Replay timeout"
        assert app.ai._verified_signature, app.ai.status
        finished = app.ai._history.get("ui-smoke")["finished"]
        app.ai.discard()
        app.ai.loadRun("ui-smoke")
        assert app.ai.hasDraft and app.ai._outputs["catalog"]
        assert app.ai._history.get("ui-smoke")["finished"] == finished
        app.ai.save("UI saved workflow")
        assert pump(lambda: not app.ai.busy, 5)
        assert db.db_get_scenario("UI saved workflow")
        assert not errors, errors
        print(
            json.dumps(
                {
                    "passed": True,
                    "data_root": str(root),
                    "checks": [
                        "workspace lock and save scope",
                        "approval",
                        "pause/resume",
                        "QML root",
                        "initial profile selection",
                        "AI navigation keeps unsent task",
                        "settings invalidation",
                        "demo profile selection",
                        "template installation",
                        "CSV export",
                        "parameterized share",
                        "real replay check",
                        "history restore",
                        "save draft",
                    ],
                }
            )
        )
    finally:
        app.ai.shutdown()
        app.recorder.shutdown()
        app.operations.shutdown()
        app._workspace_lock.unlock()


if __name__ == "__main__":
    main()
