"""QML wiring tests for the Python script editor (offscreen, no browser needed)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PyQt6.QtCore import QUrl  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

from app.ui.bridge.scenarios import ScenariosBridge  # noqa: E402

QML = b"""
import QtQuick
import QtQuick.Controls
TextArea {
    text: "async def main(ctx):\\n    return 1\\n"
    Component.onCompleted: scenariosBridge.highlightPython(textDocument)
}
"""


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_highlight_python_accepts_qml_text_document(qapp, tmp_path):
    """Regression: TextArea.textDocument arrives as QQuickTextDocument, not QObject.

    The slot must declare the concrete type so PyQt downcasts it; a plain
    QObject parameter makes .textDocument() raise AttributeError at page load.
    """
    bridge = ScenariosBridge()
    engine = QQmlEngine()
    engine.rootContext().setContextProperty("scenariosBridge", bridge)
    component = QQmlComponent(engine)
    component.setData(QML, QUrl())
    area = component.create()
    assert area is not None, component.errorString()
    try:
        assert len(getattr(bridge, "_python_highlighters", {})) == 1
    finally:
        area.deleteLater()
        engine.deleteLater()
