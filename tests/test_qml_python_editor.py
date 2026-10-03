"""QML wiring tests for the Python script editor (offscreen, no browser needed)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def test_browser_settings_qml_controls_save_and_profile_overrides(tmp_path):
    script = '''
import json, time
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QUrl, Q_ARG
from app.storage import db
from app.core.browser_interface import BrowserInterface
from app.ui.qml_app import QmlApplication
db.init_db()
db.db_set_setting('onboarding_completed', 'true')
db.db_add_account({'name': 'Audit profile', 'browser_engine': 'camoufox'})
ui = QmlApplication(['Settings UI verification'])
warnings = []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
def pump(seconds=.25):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        ui.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(.01)
def find(item, key, value):
    if item.property(key) == value: return item
    for child in item.childItems():
        result = find(child, key, value)
        if result is not None: return result
    return None
try:
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    pump()
    ui.state.setPage('Browser')
    pump()
    root = ui.engine.rootObjects()[0].contentItem()
    page = find(root, 'objectName', 'browserPage')
    for engine in ('camoufox', 'cloakbrowser'):
        ui.browser_settings.setEngine(engine)
        pump()
        page.setProperty('tab', 'Fingerprint')
        for label, text in [('Window width', '1100'), ('Window height', '700'), ('Screen width', '1920'), ('Screen height', '1080')]:
            field = find(page, 'label', label)
            field.setProperty('text', text)
            QMetaObject.invokeMethod(field, 'editingFinished')
        page.setProperty('tab', 'Network')
        for label, text in [('Locale override', 'de-DE'), ('Timezone override', 'Europe/Berlin')]:
            field = find(page, 'label', label)
            assert field is not None, label
            field.setProperty('text', text)
            QMetaObject.invokeMethod(field, 'editingFinished')
        page.setProperty('tab', 'Context')
        headers = find(page, 'label', 'Extra HTTP headers JSON')
        assert headers is not None
        headers.setProperty('text', '{"X-Audit":"qml"}')
        QMetaObject.invokeMethod(headers, 'editingFinished')
        page.setProperty('tab', 'Runtime')
        toggle = find(page, 'label', 'Human-like cursor')
        QMetaObject.invokeMethod(toggle, 'toggled', Q_ARG(bool, False))
        save = find(page, 'text', 'Save changes')
        QMetaObject.invokeMethod(save, 'clicked')
        pump()
        saved = db.db_get_camoufox_defaults() if engine == 'camoufox' else db.db_get_cloakbrowser_defaults()
        assert saved['window_width'] == 1100 and saved['screen_width'] == 1920
        assert saved['locale'] == 'de-DE' and saved['timezone'] == 'Europe/Berlin'
        assert saved['humanize'] is False
        assert saved['extra_http_headers'] == {'X-Audit': 'qml'}
        inherited = BrowserInterface('Inherited-' + engine, browser_engine=engine)
        assert inherited._browser_settings['humanize'] is False
        override = BrowserInterface('Override-' + engine, browser_engine=engine, browser_settings={'locale': 'fr-FR'})
        assert override._browser_settings['locale'] == 'fr-FR'
        assert override._browser_settings['timezone'] == 'Europe/Berlin'
    ui.profiles.saveProfileBrowserSettingsJson('Audit profile', 'camoufox', '{"locale":"fr-FR"}')
    pump(.7)
    account = next(row for row in db.db_get_accounts() if row['name'] == 'Audit profile')
    assert account['camoufox_settings'] == {'locale': 'fr-FR'}
    assert not warnings, warnings
finally:
    ui.recorder.shutdown(); ui.operations.shutdown(); ui.ai.shutdown()
    sip.delete(ui.engine)
    ui._workspace_lock.unlock()
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

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


def test_ai_workspace_closes_before_its_bridges_are_destroyed(tmp_path):
    script = """
import gc
from PyQt6.QtCore import QTimer
from app.storage import db
from app.ui.qml_app import QmlApplication

db.init_db()
db.db_set_setting('onboarding_completed', 'true')
warnings = []
ui = QmlApplication(['AI shutdown regression'])
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
ui.state.setPage('ScenarioAI')
QTimer.singleShot(100, ui.app.quit)
assert ui.exec() == 0
del ui
gc.collect()
assert not warnings, warnings
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TypeError" not in result.stdout + result.stderr


def test_recorded_task_form_and_queue_load_without_qml_errors(tmp_path):
    script = """
import time
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QUrl
from app.storage import db
from app.ui.qml_app import QmlApplication

db.init_db()
db.db_set_setting('onboarding_completed', 'true')
db.db_add_account({'name': 'Task profile', 'browser_engine': 'camoufox'})
ui = QmlApplication(['Task UI regression'])
warnings = []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
def pump(predicate=lambda: False, seconds=2):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        ui.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if predicate(): return True
        time.sleep(0.01)
    return predicate()
def find_item(item, name):
    if item.objectName() == name: return item
    for child in item.childItems():
        found = find_item(child, name)
        if found is not None: return found
    return None
def find_property(item, key, value):
    if item.property(key) == value: return item
    for child in item.childItems():
        found = find_property(child, key, value)
        if found is not None: return found
    return None
try:
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    assert ui.engine.rootObjects(), warnings
    pump(seconds=0.2)
    ui.state.setPage('ScenarioRecord')
    ui.recorder._updated([
        {'action': 'start', 'tag': 'Start'},
        {'action': 'goto', 'value': 'https://example.test', 'tag': 'Step1'},
        {'action': 'type', 'selector': '#period', 'value': 'October', 'tag': 'Step2'}], ['A popup was not recorded.'])
    ui.recorder._finished('')
    pump(seconds=0.15)
    assert ui.engine.rootObjects()[0].findChild(QObject, 'recordedActionsList')
    changing = find_property(ui.engine.rootObjects()[0].contentItem(), 'text', 'Text field: October')
    assert changing is not None
    changing.setProperty('checked', True)
    QMetaObject.invokeMethod(changing, 'clicked')
    name_field = find_property(ui.engine.rootObjects()[0].contentItem(), 'label', 'Task name')
    name_field.setProperty('text', 'Monthly report')
    QMetaObject.invokeMethod(ui.engine.rootObjects()[0].findChild(QObject, 'saveRecordedTask'), 'clicked')
    assert pump(lambda: not ui.recorder.saving and ui.state.currentPage == 'Tasks'), ui.recorder.status
    ui.tasks.select('Monthly report')
    assert pump(lambda: find_item(ui.engine.rootObjects()[0].contentItem(), 'taskInput_input_2') is not None)
    field = find_item(ui.engine.rootObjects()[0].contentItem(), 'taskInput_input_2')
    assert field.property('label') == 'Text field'
    field.setProperty('text', 'November')
    ui.operations.refresh()
    pump(seconds=0.1)
    assert field.property('text') == 'November'
    assert 'popup' in ui.tasks.review
    assert not ui.tasks.run('Task profile', {})
    assert ui.operations.queue.snapshot() == []
    assert ui.tasks.run('Task profile', {'input_2': 'November'})
    job = ui.operations.queue.snapshot()[0]
    assert job['inputs'] == {'input_2': 'November'}
    assert ui.operations.paused
    assert db.db_get_scenario('Monthly report').steps[2]['value'] == '{{input_2}}'
    from pathlib import Path
    csv_path = db.OUTPUTS_DIR / 'batch.csv'
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text('input_2\\nNovember\\nNovember\\nDecember\\n', encoding='utf-8')
    assert ui.tasks.importCsv(str(csv_path), ',')
    assert len(ui.tasks.csvRows) == 3
    panel = find_item(ui.engine.rootObjects()[0].contentItem(), 'taskBatchPanel')
    assert panel is not None
    panel.setProperty('expanded', True)
    pump(seconds=0.1)
    skip = find_item(ui.engine.rootObjects()[0].contentItem(), 'taskCsvSkipDuplicates')
    skip.setProperty('checked', True)
    queue_batch = find_item(ui.engine.rootObjects()[0].contentItem(), 'queueTaskBatch')
    assert queue_batch.property('text') == 'Queue 2 rows'
    QMetaObject.invokeMethod(queue_batch, 'clicked')
    pump(seconds=0.1)
    confirmation = panel.findChild(QObject, 'taskBatchConfirmation')
    QMetaObject.invokeMethod(confirmation, 'accept')
    assert pump(lambda: len(ui.operations.queue.snapshot()) == 3)
    jobs = ui.operations.queue.snapshot()
    assert [job['batch_row'] for job in jobs[1:]] == [1, 3]
    assert len(ui.tasks.csvRows) == 0
    pump(seconds=0.2)
    ui.state.setPage('Tasks')
    pump(seconds=0.1)
    assert len(ui.tasks.batchRuns) == 2
    assert ui.tasks.importCsv(str(csv_path), ',')
    ui.state.setPage('ScenarioRuns')
    pump(seconds=0.1)
    ui.state.setPage('Tasks')
    pump(seconds=0.1)
    assert len(ui.tasks.csvRows) == 3
    db.db_save_scenario('Monthly report', [{'action': 'start'}, {'action': 'log', 'value': 'changed'}], '')
    assert not ui.tasks.run('Task profile', {'input_2': 'November'})
    assert not ui.tasks.runBatch('Task profile', False)
    assert len(ui.operations.queue.snapshot()) == 3
    ui.state.setPage('ScenarioRuns')
    pump(seconds=0.1)
    assert not warnings, warnings
finally:
    ui.recorder.shutdown()
    ui.operations.shutdown()
    ui.ai.shutdown()
    sip.delete(ui.engine)
    ui._workspace_lock.unlock()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TypeError" not in result.stdout + result.stderr
