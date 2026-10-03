"""Opt-in full UI/bridge provider run on synthetic data; credentials stay in memory."""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--gif", type=Path)
    args = parser.parse_args()
    settings = json.loads(args.settings_file.read_text(encoding="utf-8-sig"))
    demo_parent = os.environ.get("PUBLIC") if args.screenshot or args.gif else None
    root = Path(tempfile.mkdtemp(prefix="camouflow-real-ui-", dir=demo_parent))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_QUICK_BACKEND"] = "software"
    from PyQt6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
    from PyQt6.QtTest import QTest
    from app.services.ai_agent.llm import LLMConfig
    from app.storage import db
    from app.ui.qml_app import QmlApplication

    config = LLMConfig(
        str(settings.get("ai_base_url") or ""),
        str(settings.get("ai_api_key") or ""),
        str(settings.get("ai_model") or ""),
    )
    db.init_db()
    db.db_set_setting("ai_enabled", "true")
    db.db_set_setting("ai_base_url", config.base_url)
    db.db_set_setting("ai_model", config.model)
    db.db_set_setting("onboarding_completed", "true")
    app = QmlApplication(["Real provider demo"])
    if args.screenshot or args.gif:
        from PyQt6.QtGui import QFontDatabase

        for filename in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "seguisym.ttf"):
            font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
    warnings = []
    app.engine.warnings.connect(
        lambda rows: warnings.extend(row.toString() for row in rows)
    )

    frames = []
    last_frame = 0.0

    def pump(until=lambda: False, timeout=1):
        nonlocal last_frame
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.app.processEvents()
            if (
                args.gif
                and app.engine.rootObjects()
                and time.monotonic() - last_frame >= 1
                and len(frames) < 120
            ):
                frame = root / f"frame-{len(frames):03d}.png"
                if app.engine.rootObjects()[0].grabWindow().save(str(frame)):
                    frames.append(frame)
                    last_frame = time.monotonic()
            if until():
                return True
            time.sleep(0.01)
        return until()

    def control(name):
        item = app.engine.rootObjects()[0].findChild(QObject, name)
        if item is None:
            queue = [app.engine.rootObjects()[0].contentItem()]
            while queue:
                candidate = queue.pop()
                if candidate.objectName() == name:
                    item = candidate
                    break
                queue.extend(candidate.childItems())
        assert item is not None, name
        return item

    def click(name):
        item = control(name)
        assert item.property("visible") and item.property("enabled"), name
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        QTest.mouseClick(app.engine.rootObjects()[0], Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, QPoint(round(point.x()), round(point.y())))
        pump(timeout=0.2)

    try:
        app.engine.load(QUrl.fromLocalFile(str(app.root_dir / "Main.qml")))
        assert app.engine.rootObjects()
        app.state.setPage("ScenarioAI")
        with patch("app.ui.bridge.ai.ai_config", return_value=config):
            app.ai.refresh()
            pump(timeout=0.3)
            click("aiDemoButton")
            assert pump(lambda: bool(app.profiles._cached_account("AI demo")), 10)
            pump(timeout=0.3)
            assert control("aiProfileSelector").property("currentText") == "AI demo"
            control("aiAssistantPanel").setProperty("maxSteps", 8)
            click("aiStartButton")
            assert app.ai.active
            assert pump(lambda: not app.ai.busy, 200)
        rows = app.ai._outputs.get("catalog", [])
        assert len(rows) == 3 and rows[0]["Name"] == "Notebook", (
            "Provider output did not match the synthetic table"
        )
        assert app.ai._outcome in {"success", "done"}, (
            "Model did not finish successfully"
        )
        app.ai.exportResults(str(root / "catalog.csv"))
        assert (
            (root / "catalog.csv")
            .read_text(encoding="utf-8")
            .startswith("Name,Price,Link")
        )
        pump(timeout=0.5)
        control("aiTaskScroll").setProperty("contentY", 0)
        click("aiCreateWorkflow")
        assert control("aiWorkflowDialog").property("visible")
        click("aiAddInput")
        control("aiInputName").setProperty("text", "catalog_url")
        control("aiInputValue").setProperty("text", app.ai._demo.url)
        click("aiVerifyWorkflow")
        assert app.ai.active and pump(lambda: not app.ai.busy, 90)
        assert app.ai._verified_signature, "Replay was not verified"
        assert app.ai._inputs == {"catalog_url": app.ai._demo.url}
        if args.screenshot:
            control("aiWorkflowDialog").close()
            pump(timeout=0.5)
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            assert app.engine.rootObjects()[0].grabWindow().save(str(args.screenshot))
            click("aiCreateWorkflow")
        control("aiScenarioName").setProperty("text", "Catalog workflow verified with real provider")
        click("aiSaveWorkflow")
        assert pump(lambda: not app.ai.busy, 10)
        scenario = db.db_get_scenario("Catalog workflow verified with real provider")
        assert scenario and scenario.steps[0]["_ai_replay_checked"]
        assert not warnings, "QML emitted warnings"
        if args.gif and frames:
            from PIL import Image

            images = [Image.open(frame).convert("RGB") for frame in frames]
            args.gif.parent.mkdir(parents=True, exist_ok=True)
            images[0].save(
                args.gif,
                save_all=True,
                append_images=images[1:],
                duration=1000,
                loop=0,
                optimize=True,
            )
            for image in images:
                image.close()
        report = {
            "passed": True,
            "model": config.model,
            "data_root": str(root),
            "checks": [
                "real provider UI start",
                "structured output",
                "CSV export",
                "parameterization",
                "real replay",
                "verified scenario save",
                "actual QML button clicks",
                "QML warnings",
            ],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    finally:
        app.ai.shutdown()
        app.recorder.shutdown()
        app.operations.shutdown()
        app._workspace_lock.unlock()


if __name__ == "__main__":
    main()
