"""QML wiring tests for the Python script editor (offscreen, no browser needed)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


@pytest.mark.parametrize("refresh_delay_ms", [0, 1500])
def test_native_qml_configuration_and_profile_creation(tmp_path, refresh_delay_ms):
    script = '''
import json
import time
from PyQt6 import sip
from PyQt6.QtCore import Q_ARG, QCoreApplication, QEvent, QMetaObject, Qt, QTimer, QUrl
from app.storage import db
from app.ui.qml_app import QmlApplication
db.init_db()
db.db_set_setting('onboarding_completed', 'true')
ui = QmlApplication(['Owned Native UI verification'])
warnings = []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
def pump(seconds=.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ui.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(.01)
def find(item, key, value):
    if item.property(key) == value: return item
    for child in item.childItems():
        found = find(child, key, value)
        if found is not None: return found
    return None
try:
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    pump()
    ui.state.setPage('Browser')
    pump()
    root = ui.engine.rootObjects()[0].contentItem()
    page = find(root, 'objectName', 'browserPage')
    QMetaObject.invokeMethod(find(page, 'label', 'Glint'), 'clicked')
    pump()
    section = find(page, 'objectName', 'nativeConfigurationSection')
    assert section.isVisible()
    assert section.property('title') == 'Glint'
    QMetaObject.invokeMethod(find(section, 'label', 'Mobile Web'), 'clicked')
    pump()
    assert ui.browser_settings.nativeEnvironment == 'mobile_web'
    assert ui.browser_settings.windowWidth == 390
    assert ui.browser_settings.nativeDeviceScaleFactor == 3.0
    width = find(section, 'label', 'Viewport width')
    width.setProperty('text', '420')
    QMetaObject.invokeMethod(width, 'editingFinished')
    media = find(page, 'objectName', 'nativeMediaPreferencesSection')
    assert media.isVisible()
    preferences = {'color_scheme': ('Dark', 'dark'), 'reduced_motion': ('Reduced', 'reduce'),
                   'forced_colors': ('On', 'active'), 'contrast': ('More', 'more')}
    for key, (label, value) in preferences.items():
        row = find(media, 'objectName', 'nativeMedia-' + key)
        assert row is not None
        button = find(row, 'label', label)
        QMetaObject.invokeMethod(button, 'clicked')
        pump(.05)
        assert button.property('active') and ui.browser_settings.nativeMediaPreferences[key] == value
    QMetaObject.invokeMethod(find(page, 'text', 'Save changes'), 'clicked')
    pump()
    assert db.db_get_native_defaults()['window_width'] == 420
    assert all(db.db_get_native_defaults()[key] == value for key, (_, value) in preferences.items())
    assert db.db_get_browser_engine() == 'native'
    page.setProperty('tab', 'Fingerprint')
    pump()
    privacy = find(page, 'objectName', 'nativePrivacySection')
    assert privacy.isVisible() and not section.isVisible()
    QMetaObject.invokeMethod(find(privacy, 'text', 'Privacy preset'), 'clicked')
    pump()
    assert {'Arial', 'Times New Roman', 'Courier New', 'Consolas'}.issubset(ui.browser_settings.nativePrivacyPolicy['fonts'])
    cpu = find(privacy, 'objectName', 'nativeCpuLimit')
    cpu.setProperty('text', '2')
    QMetaObject.invokeMethod(cpu, 'editingFinished')
    options = ui.browser_settings.nativeFontRasterizationOptions
    assert len(options) == 5 and options[2] == {'value': 'grayscale', 'label': 'Grayscale'}
    grayscale = find(privacy, 'label', 'Grayscale')
    assert grayscale is not None
    QMetaObject.invokeMethod(grayscale, 'clicked')
    pump()
    assert grayscale.property('active')
    ui.browser_settings.setNativePrivacyValue('font_rasterization', 'unknown')
    assert ui.browser_settings.nativePrivacyPolicy['font_rasterization'] == 'grayscale'
    QMetaObject.invokeMethod(find(page, 'text', 'Save changes'), 'clicked')
    pump()
    policy = db.db_get_native_defaults()['privacy_policy']
    assert policy['cpu_limit'] == 2 and policy['restrict_webrtc']
    assert policy['font_rasterization'] == 'grayscale'
    assert 'reviewed local runtime required' in ui.browser_settings.nativePrivacyStatus
    tuning = find(privacy, 'objectName', 'nativeTextTuning')
    assert tuning is not None and not tuning.property('enabled')
    text_options = ui.browser_settings.nativeTextTuningOptions
    assert len(text_options) == 9 and text_options[0] == {'value': 'native', 'label': 'Native'}
    native_mode = find(privacy, 'label', 'Native')
    QMetaObject.invokeMethod(native_mode, 'clicked')
    pump()
    assert tuning.property('enabled')
    selected = next(index for index, option in enumerate(text_options) if option['value'] == 'gamma-2200-contrast-500')
    QMetaObject.invokeMethod(tuning, 'activated', Qt.ConnectionType.DirectConnection, Q_ARG('int', selected))
    pump()
    assert tuning.property('currentIndex') == selected
    assert ui.browser_settings.nativePrivacyPolicy['text_tuning'] == 'gamma-2200-contrast-500'
    ui.browser_settings.setNativePrivacyValue('text_tuning', 'gamma-2000')
    ui.browser_settings.setNativePrivacyValue('font_rasterization', 'grayscale')
    assert ui.browser_settings.nativePrivacyPolicy['text_tuning'] == 'gamma-2200-contrast-500'
    assert ui.browser_settings.nativePrivacyPolicy['font_rasterization'] == 'native'
    QMetaObject.invokeMethod(find(page, 'text', 'Save changes'), 'clicked')
    pump()
    assert db.db_get_native_defaults()['privacy_policy']['text_tuning'] == 'gamma-2200-contrast-500'
    from app.core.native.configuration import NativeConfiguration
    try:
        NativeConfiguration.from_settings(db.db_get_native_defaults()).launch_arguments()
        raise AssertionError('Unverified privacy policy was silently launched')
    except ValueError as error:
        assert 'verified' in str(error)
    QMetaObject.invokeMethod(find(privacy, 'text', 'Native values'), 'clicked')
    QMetaObject.invokeMethod(find(page, 'text', 'Save changes'), 'clicked')
    pump()
    assert not db.db_get_native_defaults()['privacy_policy']['cpu_limit']
    assert db.db_get_native_defaults()['privacy_policy']['font_rasterization'] == 'native'
    assert db.db_get_native_defaults()['window_width'] == 420
    ui.browser_settings.setValue('fingerprint_noise', True)
    messages = []
    ui.browser_settings.message.connect(messages.append)
    ui.browser_settings.save()
    assert 'does not support' in messages[-1]
    assert 'fingerprint_noise' not in db.db_get_native_defaults()
    ui.browser_settings.reload()
    ui.browser_settings.checkCompatibility()
    deadline = time.monotonic() + 3
    while ui.browser_settings.compatibilityRunning and time.monotonic() < deadline:
        pump(.05)
    assert not ui.browser_settings.compatibilityRunning
    assert ui.browser_settings.compatibilityReport.startswith('Blocked:')
    page.setProperty('tab', 'Maintenance')
    pump()
    release_section = find(page, 'objectName', 'nativeReleaseSection')
    assert release_section.isVisible()
    assert not find(page, 'text', 'Check updates').isVisible()
    assert not find(page, 'text', 'Update engine').isVisible()
    install = find(release_section, 'objectName', 'nativeInstallRelease')
    rollback = find(release_section, 'objectName', 'nativeRollbackRelease')
    assert not install.isEnabled() and not rollback.isEnabled()
    store = db.OUTPUTS_DIR / 'owned-native-store'
    bundle = db.OUTPUTS_DIR / 'invalid-owned-native.tar.gz'
    bundle.write_bytes(b'not a release')
    ui.browser_settings.setValue('binary_source', 'managed')
    ui.browser_settings.setValue('binary_store', str(store))
    find(release_section, 'objectName', 'nativeBundleArchive').setProperty('text', QUrl.fromLocalFile(str(bundle)).toString())
    find(release_section, 'objectName', 'nativeBundleChecksum').setProperty('text', 'invalid')
    pump()
    assert install.isEnabled() and rollback.isEnabled()
    QMetaObject.invokeMethod(install, 'clicked')
    pump()
    assert 'SHA-256' in ui.browser_settings.nativeReleaseReport
    assert not ui.browser_settings.nativeReleaseRunning and not store.exists()
    ui.state.setPage('Profiles')
    pump()
    combo = find(root, 'objectName', 'newProfileEngine')
    assert combo.property('currentIndex') == 2
    if REFRESH_DELAY_MS:
        apply_accounts = ui.profiles._refresh_task._apply
        ui.profiles._refresh_task._apply = lambda value: QTimer.singleShot(REFRESH_DELAY_MS, lambda: apply_accounts(value))
    profile_events = []
    profile_started = time.monotonic()
    ui.profiles.busyChanged.connect(lambda: profile_events.append(
        ('busy', round(time.monotonic() - profile_started, 3), ui.profiles.busy)))
    ui.profiles.modelChanged.connect(lambda: profile_events.append(
        ('model', round(time.monotonic() - profile_started, 3), len(ui.profiles._accounts_cache))))
    ui.profiles.message.connect(lambda _: profile_events.append(
        ('message', round(time.monotonic() - profile_started, 3))))
    QMetaObject.invokeMethod(find(root, 'text', 'New Profile'), 'clicked')
    deadline = time.monotonic() + 3
    while True:
        pump(.05)
        rows = db.db_get_accounts()
        if len(rows) == 1 and ui.profiles.getProfile(rows[0]['name'], '').get('engine') == 'native':
            break
        assert time.monotonic() < deadline, ('Created Glint profile was not delivered to the UI model', {
            'db_count': len(rows), 'db_engines': [row.get('_browser_engine') for row in rows],
            'cache_count': len(ui.profiles._accounts_cache),
            'cache_engines': [row.get('_browser_engine') for row in ui.profiles._accounts_cache],
            'busy': ui.profiles.busy, 'refresh_busy': ui.profiles._refresh_task.busy,
            'events': profile_events})
    assert rows[0]['_browser_engine'] == 'native'
    defaults = db.db_get_native_defaults()
    profile = rows[0]['name']
    profiles_page = find(root, 'objectName', 'pageLoader').property('item')
    QMetaObject.invokeMethod(profiles_page, 'openBrowserOverridesModal', Qt.ConnectionType.DirectConnection,
                             Q_ARG('QVariant', profile))
    deadline = time.monotonic() + 3
    while True:
        pin = find(root, 'objectName', 'nativePinEnvironment')
        editor = find(root, 'objectName', 'profileBrowserSettingsEditor')
        if pin is not None and editor is not None and pin.isVisible(): break
        assert time.monotonic() < deadline, ('Native profile dialog did not become ready', warnings)
        pump(.05)
    assert pin.isVisible() and pin.isEnabled()
    original = rows[0].get('native_settings')
    QMetaObject.invokeMethod(pin, 'clicked')
    pump()
    prepared_text = editor.property('text')
    prepared = json.loads(prepared_text)
    assert prepared['window_width'] == 420 and prepared['environment'] == 'mobile_web'
    assert prepared['color_scheme'] == 'dark' and prepared['contrast'] == 'more'
    assert not {'permissions', 'binary_store', 'executable_path', 'extra_http_headers', 'storage_state_path'} & prepared.keys()
    assert db.db_get_accounts()[0].get('native_settings') == original
    editor.setProperty('text', '{')
    QMetaObject.invokeMethod(pin, 'clicked')
    pump()
    assert editor.property('text') == '{'
    editor.setProperty('text', prepared_text)
    QMetaObject.invokeMethod(find(root, 'objectName', 'profileBrowserSettingsSave'), 'clicked')
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        pump(.1)
        stored = db.db_get_accounts()[0].get('native_settings') or {}
        if stored.get('window_width') == 420: break
    assert stored == prepared
    assert db.db_get_native_defaults() == defaults
    db.db_set_native_defaults({**defaults, 'window_width': 900, 'color_scheme': 'light'})
    from app.core.native.configuration import NativeConfiguration
    effective = NativeConfiguration.from_settings({**db.db_get_native_defaults(), **stored})
    assert effective.width == 420 and effective.color_scheme == 'dark'
    assert not warnings, warnings
finally:
    ui.recorder.shutdown(); ui.operations.shutdown(); ui.ai.shutdown()
    sip.delete(ui.engine)
    ui._workspace_lock.unlock()
'''
    script = script.replace('REFRESH_DELAY_MS', str(refresh_delay_ms))
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_settings_keyboard_navigation_and_scroll(tmp_path):
    script = '''
import time
from PyQt6 import sip
from PyQt6.QtCore import QPointF, Qt, QUrl
from PyQt6.QtTest import QTest
from app.storage import db
from app.ui.qml_app import QmlApplication

db.init_db()
db.db_set_setting('onboarding_completed', 'true')
ui = QmlApplication(['Browser keyboard regression'])
warnings = []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
def pump():
    for _ in range(10):
        ui.app.processEvents()
        time.sleep(.005)
def find(item, key, value):
    if item.property(key) == value: return item
    for child in item.childItems():
        found = find(child, key, value)
        if found is not None: return found
    return None
def press(key, modifiers=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(window, key, modifiers)
    pump()
try:
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    pump()
    ui.state.setPage('Browser')
    pump()
    window = ui.engine.rootObjects()[0]
    page = find(window.contentItem(), 'objectName', 'browserPage')
    glint = find(page, 'label', 'Glint')
    glint.forceActiveFocus()
    press(Qt.Key.Key_Return)
    assert ui.browser_settings.engine == 'native'
    scroll = find(page, 'objectName', 'browserSettingsScroll')
    permissions = None
    for _ in range(35):
        press(Qt.Key.Key_Tab)
        item = window.activeFocusItem()
        if item.property('placeholderText') == 'One supported permission per line':
            permissions = item
            break
    assert permissions is not None, 'Permissions field is unreachable by Tab'
    top = permissions.mapToItem(scroll, QPointF(0, 0)).y()
    assert top >= 0 and top + permissions.height() <= scroll.height()
    before = permissions.property('text')
    press(Qt.Key.Key_Tab)
    assert window.activeFocusItem() is not permissions
    assert permissions.property('text') == before, 'Tab must not insert whitespace'
    press(Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert window.activeFocusItem() is permissions
    press(Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    toggle = window.activeFocusItem()
    assert toggle.property('label') == 'Headless', (toggle.metaObject().className(), toggle.property('text'), toggle.property('label'))
    headless = ui.browser_settings.headlessMode
    press(Qt.Key.Key_Space)
    assert ui.browser_settings.headlessMode != headless
    page.setProperty('tab', 'Fingerprint')
    pump()
    glint.forceActiveFocus()
    found_fonts = False
    for _ in range(35):
        press(Qt.Key.Key_Tab)
        item = window.activeFocusItem()
        if item.property('placeholderText') == 'Empty = native; include Arial; one family per line':
            found_fonts = True
            before = item.property('text')
            press(Qt.Key.Key_Tab)
            assert window.activeFocusItem() is not item
            assert item.property('text') == before
            break
    assert found_fonts
    page.setProperty('tab', 'Runtime')
    pump()
    glint.forceActiveFocus()
    for _ in range(3): press(Qt.Key.Key_Tab)
    assert window.activeFocusItem().property('text') == 'Engine health'
    press(Qt.Key.Key_Space)
    assert page.property('tab') == 'Maintenance'
    press(Qt.Key.Key_Tab)
    assert window.activeFocusItem().property('text') == 'Check compatibility'
    press(Qt.Key.Key_Space)
    deadline = time.monotonic() + 10
    while ui.browser_settings.compatibilityRunning and time.monotonic() < deadline:
        pump()
    assert not ui.browser_settings.compatibilityRunning
    assert ui.browser_settings.compatibilityReport != 'Not checked'
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


def test_task_search_and_rapid_page_switches_preserve_qml_contexts(tmp_path):
    script = '''
import time
from PyQt6 import sip
from PyQt6.QtCore import QObject, QUrl
from app.storage import db
from app.ui.qml_app import QmlApplication

db.init_db()
db.db_set_setting('onboarding_completed', 'true')
for index in range(30):
    db.db_save_scenario(f'Task {index:02d}', [{'action': 'start'}, {'action': 'log', 'value': 'test'}], '')
ui = QmlApplication(['Task navigation regression'])
warnings, resets = [], []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
ui.tasks.model.modelReset.connect(lambda: resets.append(True))

def pump(seconds=.1):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ui.app.processEvents()
        time.sleep(.001)

try:
    ui.scenarios.selectScenario('Task 00')
    ui.tasks.setSearch('Task')
    ui.state.setPage('Tasks')
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    assert ui.engine.rootObjects(), warnings
    pump()
    resets.clear()
    for index in range(50):
        ui.tasks.setSearch('Task')
        ui.tasks.refresh()
        ui.state.setPage('ScenarioRuns')
        pump(.01)
        ui.state.setPage('Tasks')
        pump(.01)
    pump(.2)
    assert not resets, 'Unchanged task rows must not recreate list delegates'
    assert ui.tasks.searchQuery == 'Task'
    assert ui.tasks.model.rowCount() == 30
    assert ui.tasks.selectedName == 'Task 00'
    root = ui.engine.rootObjects()[0]
    assert root.findChild(QObject, 'savedTaskList') is not None
    assert not warnings, warnings
    ui.tasks.setSearch('Task 01')
    pump()
    assert len(resets) == 1
    assert ui.tasks.model.rowCount() == 1
    assert ui.tasks.model.get(0)['name'] == 'Task 01'
    assert not warnings, warnings
finally:
    ui.recorder.shutdown()
    ui.operations.shutdown()
    ui.ai.shutdown()
    sip.delete(ui.engine)
    ui._workspace_lock.unlock()
'''
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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


def test_untrusted_qml_labels_do_not_fetch_inline_images(tmp_path):
    script = '''
import faulthandler, socketserver, threading, time
faulthandler.enable()
faulthandler.dump_traceback_later(15)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PyQt6 import sip
from PyQt6.QtCore import QUrl, QMetaObject
from PyQt6.QtQml import QQmlComponent
from app.storage import db
from app.ui.qml_app import QmlApplication

requests = []
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        self.send_response(404)
        self.end_headers()
    def log_message(self, *args): pass
class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # The fixture needs no reverse DNS; macOS CI's resolver can block here.
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]
server = LocalServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
db.init_db()
db.db_set_setting('onboarding_completed', 'true')
ui = QmlApplication(['Untrusted label regression'])
warnings = []
ui.engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
components, rows = [], []
try:
    ui.engine.load(QUrl.fromLocalFile(str(ui.root_dir / 'Main.qml')))
    window = ui.engine.rootObjects()[0]
    cases = [('ProfileRow', ['name', 'tags', 'proxy', 'lockedBy']),
             ('ProxyRow', ['name', 'location', 'address']),
             ('InfoColumn', ['title', 'value']), ('PageHeader', ['title', 'subtitle', 'badge']),
             ('EmptyState', ['title', 'description']), ('PrimaryButton', ['text']),
             ('ScenarioNode', ['title', 'subtitle']), ('FormField', ['label']),
             ('MultiField', ['label']), ('PlainCheckBox', ['text'])]
    for index, (name, fields) in enumerate(cases):
        payload = f'<img src="http://127.0.0.1:{server.server_port}/pixel-{index}.png">Synthetic label'
        component = QQmlComponent(ui.engine, QUrl.fromLocalFile(str(ui.root_dir / 'components' / (name + '.qml'))))
        row = component.createWithInitialProperties({**{field: payload for field in fields}, 'width': 800})
        assert row is not None, [error.toString() for error in component.errors()]
        row.setParentItem(window.contentItem())
        row.setY(index * 90)
        components.append(component)
        rows.append(row)
    from app.ui.bridge.models import DictListModel
    payload = f'<img src="http://127.0.0.1:{server.server_port}/combo.png">Synthetic choice'
    role_model = DictListModel(['name'], [{'name': payload}, {'name': 'Second choice'}])
    for model, role in [([payload, 'Second choice'], ''), ([{'name': payload}, {'name': 'Second choice'}], 'name'), (role_model, 'name')]:
        wrapper = QQmlComponent(ui.engine)
        wrapper.setData(b"""import QtQuick
import "components"
Item {
    id: root
    property var choices
    property string choiceRole
    property int activatedIndex: -1
    property alias selectedIndex: combo.currentIndex
    property alias selectedText: combo.currentText
    width: 800; height: 44
    PlainComboBox { id: combo; width: parent.width; model: root.choices; textRole: root.choiceRole; onActivated: function(index) { root.activatedIndex = index } }
    function openChoices() { combo.popup.open() }
    function pickSecond() { combo.popup.contentItem.itemAtIndex(1).clicked() }
}""", QUrl.fromLocalFile(str(ui.root_dir / 'inline-label-test.qml')))
        row = wrapper.createWithInitialProperties({'choices': model, 'choiceRole': role})
        assert row is not None, [error.toString() for error in wrapper.errors()]
        row.setParentItem(window.contentItem())
        QMetaObject.invokeMethod(row, 'openChoices')
        until = time.monotonic() + .15
        while time.monotonic() < until:
            ui.app.processEvents()
            time.sleep(.01)
        assert row.property('selectedText') == payload
        QMetaObject.invokeMethod(row, 'pickSecond')
        ui.app.processEvents()
        assert row.property('selectedIndex') == row.property('activatedIndex') == 1
        assert row.property('selectedText') == 'Second choice'
        components.append(wrapper)
        rows.append(row)
    until = time.monotonic() + .6
    while time.monotonic() < until:
        ui.app.processEvents()
        time.sleep(.01)
    assert not requests, requests
    assert not warnings, warnings
finally:
    server.shutdown()
    server.server_close()
    ui.recorder.shutdown()
    ui.operations.shutdown()
    ui.ai.shutdown()
    sip.delete(ui.engine)
    ui._workspace_lock.unlock()
    faulthandler.cancel_dump_traceback_later()
'''
    try:
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "CAMOUFLOW_DATA_DIR": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        pytest.fail("Inline-label QML check timed out:\n" + stderr)
    assert result.returncode == 0, result.stdout + result.stderr


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
    search = find_item(ui.engine.rootObjects()[0].contentItem(), 'savedTaskSearch')
    assert search is not None
    search.setProperty('text', 'monthly')
    pump(seconds=0.1)
    assert ui.tasks.model.rowCount() == 1
    assert field.property('text') == 'November'
    assert 0 < search.width() <= 380
    assert field.width() > 250
    search.setProperty('text', 'no-matching-task')
    pump(seconds=0.1)
    assert ui.tasks.model.rowCount() == 0
    assert ui.tasks.selectedName == 'Monthly report'
    assert field.property('text') == 'November'
    search.setProperty('text', '')
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
    schedule = find_item(ui.engine.rootObjects()[0].contentItem(), 'runSchedulingForm')
    toggle = find_item(ui.engine.rootObjects()[0].contentItem(), 'toggleRunScheduling')
    assert schedule is not None and toggle is not None
    assert not schedule.isVisible()
    search = find_item(ui.engine.rootObjects()[0].contentItem(), 'runSearch')
    status_filter = find_item(ui.engine.rootObjects()[0].contentItem(), 'runStatusFilter')
    assert search is not None and status_filter is not None
    search.setProperty('text', 'missing run')
    pump(seconds=0.1)
    assert ui.operations.runQuery == 'missing run'
    assert ui.operations.jobsModel.rowCount() == 0
    ui.operations.setRunFilters('', 'queued')
    pump(seconds=0.1)
    assert ui.operations.jobsModel.rowCount() == 3
    assert status_filter.property('currentIndex') == 1
    assert search.property('text') == ''
    ui.operations.setRunFilters('', '')
    details_button = find_property(ui.engine.rootObjects()[0].contentItem(), 'text', 'Details')
    runs_panel = find_item(ui.engine.rootObjects()[0].contentItem(), 'scenarioRunsPanel')
    assert details_button is not None and runs_panel is not None
    QMetaObject.invokeMethod(details_button, 'clicked')
    pump(seconds=0.1)
    assert runs_panel.property('selectedJob') == ui.operations.selectedJob != ''
    ui.operations.selectJob('unknown')
    pump(seconds=0.1)
    assert runs_panel.property('selectedJob') == ''
    QMetaObject.invokeMethod(toggle, 'clicked')
    pump(seconds=0.1)
    assert schedule.isVisible()
    QMetaObject.invokeMethod(toggle, 'clicked')
    pump(seconds=0.1)
    assert not schedule.isVisible()
    ui.operations.prepareRun('Task profile')
    pump(seconds=0.1)
    assert schedule.isVisible()
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
