"""Main application window assembly."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, cast

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.browser_interface import BrowserInterface
from app.utils.parsing import DEFAULT_ACCOUNT_TEMPLATE
from app.storage.db import (
    CAMOUFOX_DEFAULTS,
    Scenario,
    db_get_camoufox_defaults,
    db_get_setting,
    db_set_camoufox_defaults,
    db_set_setting,
)
from app.ui.tabs.logs import build_logs_tab
from app.ui.tabs.proxies import build_proxies_tab
from app.ui.tabs.run import build_run_tab
from app.ui.tabs.scenarios import build_scenarios_tab
from app.ui.tabs.settings import build_settings_tab
from app.ui.style import DEFAULT_THEME, apply_modern_theme, normalize_theme

from .accounts_mixin import AccountsMixin
from .logging_mixin import LoggingMixin
from .proxy_mixin import ProxyPoolMixin
from .scenario_editor import ScenarioEditorMixin
from .scenario_runner import ScenarioRunnerMixin
from .shared_mixin import SharedDataMixin

CamoufoxControls = Dict[str, object]


class MainWindow(
    ScenarioEditorMixin,
    ScenarioRunnerMixin,
    AccountsMixin,
    SharedDataMixin,
    ProxyPoolMixin,
    LoggingMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CamouFlow")
        self._initial_maximize_scheduled = False
        self.live_browsers: Dict[str, BrowserInterface] = {}
        self.current_steps: List[Dict] = []
        self.selected_scenario: Optional[Scenario] = None
        self.scenarios_cache: List[Scenario] = []
        self._tag_counter: int = 0
        self.account_parse_template: str = DEFAULT_ACCOUNT_TEMPLATE
        self.shared_variables: Dict[str, str] = {}
        self.proxy_pools: Dict[str, Dict[str, object]] = {}
        self._selected_proxy_pool: Optional[str] = None
        self.stages: List[str] = []
        self.camoufox_defaults: Dict[str, object] = {}
        self._camoufox_controls: Optional[CamoufoxControls] = None
        self._ensure_start_step()
        self._load_camoufox_defaults()
        self._log_default_color: Optional[QColor] = None
        self._log_error_color = QColor("#ff4d4f")
        self._map_focus_on_load = True
        self._accounts_snapshot: List[Dict[str, object]] = []
        self._active_stage_filter: Optional[str] = None
        self._nav_buttons: Dict[int, QPushButton] = {}
        self._account_row_widgets: Dict[QWidget, QListWidgetItem] = {}
        self.current_theme: str = DEFAULT_THEME
        self._theme_combo: Optional[QComboBox] = None
        self._load_ui_theme_preference()
        app = QApplication.instance()
        if app:
            apply_modern_theme(app, self.current_theme)
        if hasattr(self, "_ensure_ui_invoker"):
            self._ensure_ui_invoker()

        central = QWidget()
        central.setObjectName("CentralContainer")
        self._stack = QStackedWidget()
        run_tab = build_run_tab(self)
        proxies_tab = build_proxies_tab(self)
        scenarios_tab = build_scenarios_tab(self)
        logs_tab = build_logs_tab(self)
        settings_tab = build_settings_tab(self)
        self._run_tab_index = self._stack.addWidget(run_tab)
        proxies_index = self._stack.addWidget(proxies_tab)
        scenarios_index = self._stack.addWidget(scenarios_tab)
        logs_index = self._stack.addWidget(logs_tab)
        settings_index = self._stack.addWidget(settings_tab)
        self._stack.currentChanged.connect(self._on_tab_changed)
        self._install_log_handler()
        self._load_ui_log_from_file()

        header = self._build_top_bar(
            [
                ("Profiles", self._run_tab_index),
                ("Proxies", proxies_index),
                ("Scenarios", scenarios_index),
                ("Logs", logs_index),
                ("Settings", settings_index),
            ]
        )
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(18)
        outer.addWidget(header)
        outer.addWidget(self._stack, 1)
        self.setCentralWidget(central)
        QTimer.singleShot(0, self._expand_to_screen)

        self.refresh_accounts_list()
        self._reload_scenarios()
        self._load_stages()
        self._load_account_template()
        self._load_shared_vars()
        self._load_proxy_pools()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._initial_maximize_scheduled:
            return
        self._initial_maximize_scheduled = True

        def try_maximize() -> None:
            if not self.isMaximized():
                self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
                self.showMaximized()
            self.raise_()
            self.activateWindow()

        QTimer.singleShot(0, try_maximize)
        QTimer.singleShot(150, try_maximize)

    def _build_top_bar(self, nav_items: List[Tuple[str, int]]) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(18)
        intro = QVBoxLayout()
        title = QLabel("CamouFlow")
        title.setProperty("class", "heroTitle")
        intro.addWidget(title)
        layout.addLayout(intro)

        nav_widget = QWidget(bar)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)
        self._nav_buttons.clear()
        for label, idx in nav_items:
            btn = QPushButton(label, nav_widget)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setProperty("class", "nav")
            btn.clicked.connect(lambda _, page=idx: self._stack.setCurrentIndex(page))
            nav_layout.addWidget(btn)
            self._nav_buttons[idx] = btn
        layout.addWidget(nav_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        refresh_btn = QPushButton("Refresh profiles", bar)
        refresh_btn.setProperty("class", "ghost")
        refresh_btn.clicked.connect(self.refresh_accounts_list)
        actions.addWidget(refresh_btn)
        layout.addLayout(actions)
        self._update_nav_state(self._stack.currentIndex())
        return bar

    def _build_camoufox_controls(self, parent: QWidget) -> Tuple[CamoufoxControls, QWidget]:
        headless_combo = QComboBox(parent)
        headless_combo.addItem("Standard window", False)
        headless_combo.addItem("Headless", True)
        headless_combo.addItem("Headless (virtual display)", "virtual")

        humanize_check = QCheckBox("Enable human-like cursor movement", parent)
        humanize_duration = QDoubleSpinBox(parent)
        humanize_duration.setRange(0.1, 10.0)
        humanize_duration.setDecimals(2)
        humanize_duration.setSingleStep(0.1)
        humanize_duration.setSuffix(" s")
        humanize_duration.setValue(1.5)

        def _auto_toggle_widget(
            inner: QWidget, clear_callback: Callable[[], None], hint: str = ""
        ) -> Tuple[QWidget, Callable[[bool], None]]:
            container = QWidget(parent)
            container.setObjectName("CamoufoxAutoSet")
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            btn_auto = QPushButton("Auto", parent)
            btn_auto.setCheckable(True)
            btn_auto.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn_set = QPushButton("Set", parent)
            btn_set.setCheckable(True)
            btn_set.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            def apply_state(is_auto: bool) -> None:
                btn_auto.blockSignals(True)
                btn_set.blockSignals(True)
                btn_auto.setChecked(is_auto)
                btn_set.setChecked(not is_auto)
                inner.setVisible(not is_auto)
                if is_auto:
                    clear_callback()
                btn_auto.blockSignals(False)
                btn_set.blockSignals(False)

            btn_auto.clicked.connect(lambda: apply_state(True))
            btn_set.clicked.connect(lambda: apply_state(False))
            layout.addWidget(btn_auto)
            if hint:
                btn_auto.setToolTip(f"Use automatic {hint}")
                btn_set.setToolTip(f"Set {hint} manually")
            layout.addWidget(btn_set)
            layout.addWidget(inner, 1)
            apply_state(True)
            return container, apply_state

        def _auto_line_edit(placeholder: str) -> Tuple[QWidget, QLineEdit, Callable[[bool], None]]:
            line = QLineEdit(parent)
            line.setPlaceholderText(placeholder)
            container, toggle = _auto_toggle_widget(line, line.clear, placeholder)
            return container, line, toggle

        def _auto_text_edit(placeholder: str, height: int = 80) -> Tuple[QWidget, QTextEdit, Callable[[bool], None]]:
            text = QTextEdit(parent)
            text.setPlaceholderText(placeholder)
            text.setFixedHeight(height)
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            container, toggle = _auto_toggle_widget(text, text.clear, placeholder)
            container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            container.setMinimumHeight(height)
            return container, text, toggle

        def _auto_bool_combo(hint: str) -> Tuple[QWidget, QComboBox, Callable[[bool], None]]:
            combo = QComboBox(parent)
            combo.addItem("Auto", None)
            combo.addItem("True", True)
            combo.addItem("False", False)
            container, toggle = _auto_toggle_widget(combo, lambda: combo.setCurrentIndex(0), hint)
            return container, combo, toggle

        def _auto_spinbox(
            minimum: int,
            maximum: int,
            step: int,
            hint: str,
            suffix: str = "",
        ) -> Tuple[QWidget, QSpinBox, Callable[[bool], None]]:
            spin = QSpinBox(parent)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            if suffix:
                spin.setSuffix(suffix)
            container, toggle = _auto_toggle_widget(spin, lambda: spin.setValue(minimum), hint)
            return container, spin, toggle

        def _auto_double_spinbox(
            minimum: float,
            maximum: float,
            step: float,
            hint: str,
            decimals: int = 2,
        ) -> Tuple[QWidget, QDoubleSpinBox, Callable[[bool], None]]:
            spin = QDoubleSpinBox(parent)
            spin.setRange(minimum, maximum)
            spin.setDecimals(decimals)
            spin.setSingleStep(step)
            container, toggle = _auto_toggle_widget(spin, lambda: spin.setValue(minimum), hint)
            return container, spin, toggle

        def _bool_combo() -> QComboBox:
            combo = QComboBox(parent)
            combo.addItem("Auto", None)
            combo.addItem("True", True)
            combo.addItem("False", False)
            return combo

        humanize_container, humanize_duration_toggle = _auto_toggle_widget(
            humanize_duration, lambda: humanize_duration.setValue(1.5), "cursor duration"
        )
        humanize_check.toggled.connect(lambda checked: humanize_container.setVisible(checked))
        humanize_check.toggled.connect(lambda checked: humanize_container.setEnabled(checked))
        humanize_check.setChecked(True)

        locale_container, locale_input, locale_toggle = _auto_line_edit("Auto-detect locale")
        timezone_container, timezone_input, timezone_toggle = _auto_line_edit("Auto-detect timezone")

        width_spin = QSpinBox(parent)
        width_spin.setRange(0, 4000)
        width_spin.setSingleStep(10)
        width_spin.setSuffix(" px")

        height_spin = QSpinBox(parent)
        height_spin.setRange(0, 4000)
        height_spin.setSingleStep(10)
        height_spin.setSuffix(" px")

        os_auto_check = QCheckBox("Auto", parent)
        os_auto_check.setChecked(True)
        os_checks = {
            "windows": QCheckBox("Windows", parent),
            "macos": QCheckBox("MacOS", parent),
            "linux": QCheckBox("Linux", parent),
        }
        os_layout = QHBoxLayout()
        os_layout.setSpacing(12)
        os_layout.addWidget(os_auto_check)
        for cb in os_checks.values():
            os_layout.addWidget(cb)

        def _sync_os_state():
            any_checked = any(cb.isChecked() for cb in os_checks.values())
            os_auto_check.blockSignals(True)
            os_auto_check.setChecked(not any_checked)
            os_auto_check.blockSignals(False)

        def _auto_toggled(checked: bool) -> None:
            if checked:
                for cb in os_checks.values():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        os_auto_check.toggled.connect(_auto_toggled)
        for cb in os_checks.values():
            cb.toggled.connect(lambda _: _sync_os_state())
        _sync_os_state()

        fonts_edit = QTextEdit(parent)
        fonts_edit.setPlaceholderText("One font per line")
        fonts_edit.setFixedHeight(90)

        webgl_vendor_container, webgl_vendor_input, webgl_vendor_toggle = _auto_line_edit("Vendor")
        webgl_renderer_container, webgl_renderer_input, webgl_renderer_toggle = _auto_line_edit("Renderer")

        window_inputs = QWidget(parent)
        window_inputs_layout = QHBoxLayout(window_inputs)
        window_inputs_layout.setContentsMargins(0, 0, 0, 0)
        window_inputs_layout.setSpacing(8)
        window_inputs_layout.addWidget(width_spin)
        window_inputs_layout.addWidget(height_spin)

        def _clear_window() -> None:
            width_spin.setValue(0)
            height_spin.setValue(0)

        window_container, window_toggle = _auto_toggle_widget(window_inputs, _clear_window, "window size")

        persistent_context_check = QCheckBox("Persistent context (recommended)", parent)
        cache_check = QCheckBox("Enable cache", parent)

        block_webrtc_check = QCheckBox("Block WebRTC", parent)
        block_images_check = QCheckBox("Block images", parent)
        block_webgl_check = QCheckBox("Block WebGL", parent)
        disable_coop_check = QCheckBox("Disable COOP (helpful for Cloudflare)", parent)

        tabs = QTabWidget(parent)
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        general_tab = QWidget()
        general_form = QFormLayout(general_tab)
        general_form.addRow("Operating systems:", os_layout)
        general_form.addRow("Execution mode:", headless_combo)
        general_form.addRow("Humanize cursor:", humanize_check)
        general_form.addRow("Cursor duration:", humanize_container)
        general_form.addRow("Locale override:", locale_container)
        general_form.addRow("Timezone override:", timezone_container)
        general_form.addRow("Fonts:", fonts_edit)
        general_form.addRow("WebGL vendor:", webgl_vendor_container)
        general_form.addRow("WebGL renderer:", webgl_renderer_container)
        general_form.addRow("", persistent_context_check)
        general_form.addRow("Enable cache:", cache_check)
        general_form.addRow("Block WebRTC:", block_webrtc_check)
        general_form.addRow("Block images:", block_images_check)
        general_form.addRow("Block WebGL:", block_webgl_check)
        general_form.addRow("Disable COOP:", disable_coop_check)
        tabs.addTab(general_tab, "General")

        window_controls: Dict[str, Dict[str, object]] = {}

        def _register_window_control(
            key: str, entry_type: str, widget: QWidget, toggle: Optional[Callable[[bool], None]] = None
        ) -> None:
            meta: Dict[str, object] = {"type": entry_type, "widget": widget}
            if callable(toggle):
                meta["toggle"] = toggle
            window_controls[key] = meta

        def _add_window_int(
            target_form: QFormLayout,
            key: str,
            label: str,
            minimum: int,
            maximum: int,
            step: int = 1,
        ) -> None:
            container, spin, toggle = _auto_spinbox(minimum, maximum, step, label.lower())
            target_form.addRow(f"{label}:", container)
            _register_window_control(key, "int", spin, toggle)

        def _add_window_double(
            target_form: QFormLayout,
            key: str,
            label: str,
            minimum: float,
            maximum: float,
            step: float = 0.1,
            decimals: int = 2,
        ) -> None:
            container, spin, toggle = _auto_double_spinbox(minimum, maximum, step, label.lower(), decimals)
            target_form.addRow(f"{label}:", container)
            _register_window_control(key, "double", spin, toggle)

        window_tab = QWidget()
        window_form = QFormLayout(window_tab)
        window_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        window_info = QLabel("Spoof screen and browser window metrics. Leave Auto for defaults.")
        window_info.setWordWrap(True)
        window_info.setProperty("class", "muted")
        window_form.addRow(window_info)
        window_form.addRow("Window size (width x height):", window_container)

        screen_header = QLabel("Screen metrics")
        screen_header.setProperty("class", "cardTitle")
        window_form.addRow(screen_header)
        _add_window_int(window_form, "screen.availHeight", "Available height", 0, 10000)
        _add_window_int(window_form, "screen.availWidth", "Available width", 0, 10000)
        _add_window_int(window_form, "screen.availTop", "Available top", -2000, 2000)
        _add_window_int(window_form, "screen.availLeft", "Available left", -2000, 2000)
        _add_window_int(window_form, "screen.height", "Screen height", 0, 10000)
        _add_window_int(window_form, "screen.width", "Screen width", 0, 10000)
        _add_window_int(window_form, "screen.colorDepth", "Color depth", 0, 64)
        _add_window_int(window_form, "screen.pixelDepth", "Pixel depth", 0, 64)

        browser_header = QLabel("Browser window metrics")
        browser_header.setProperty("class", "cardTitle")
        window_form.addRow(browser_header)
        _add_window_int(window_form, "browser.scrollMinX", "Scroll min X", -10000, 10000)
        _add_window_int(window_form, "browser.scrollMinY", "Scroll min Y", -10000, 10000)
        _add_window_int(window_form, "browser.scrollMaxX", "Scroll max X", -10000, 10000)
        _add_window_int(window_form, "browser.scrollMaxY", "Scroll max Y", -10000, 10000)
        _add_window_int(window_form, "browser.outerHeight", "Outer height", 0, 10000)
        _add_window_int(window_form, "browser.outerWidth", "Outer width", 0, 10000)
        _add_window_int(window_form, "browser.innerHeight", "Inner height", 0, 10000)
        _add_window_int(window_form, "browser.innerWidth", "Inner width", 0, 10000)
        _add_window_int(window_form, "browser.screenX", "Screen X", -10000, 10000)
        _add_window_int(window_form, "browser.screenY", "Screen Y", -10000, 10000)
        _add_window_double(window_form, "browser.devicePixelRatio", "Device pixel ratio", 0.1, 8.0, 0.1, 2)

        history_header = QLabel("History and scroll")
        history_header.setProperty("class", "cardTitle")
        window_form.addRow(history_header)
        _add_window_int(window_form, "history.length", "History length", 0, 500)
        fp_spacing_container, fp_spacing_spin, fp_spacing_toggle = _auto_spinbox(0, 2_147_483_647, 1, "fonts:spacing_seed")
        fp_canvas_container, fp_canvas_spin, fp_canvas_toggle = _auto_spinbox(-1000, 1000, 1, "canvas:aaOffset")
        fp_screeny_container, fp_screeny_spin, fp_screeny_toggle = _auto_spinbox(-2000, 2000, 1, "window.screenY")
        fp_history_container, fp_history_spin, fp_history_toggle = _auto_spinbox(0, 500, 1, "window.history.length")
        window_form.addRow("fonts:spacing_seed:", fp_spacing_container)
        window_form.addRow("canvas:aaOffset:", fp_canvas_container)
        window_form.addRow("window.screenY:", fp_screeny_container)
        window_form.addRow("window.history.length:", fp_history_container)

        tabs.addTab(window_tab, "Window")
        navigator_controls: Dict[str, Dict[str, object]] = {}
        navigator_tab = QWidget()
        navigator_form = QFormLayout(navigator_tab)
        navigator_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        navigator_info = QLabel("Override navigator.* values. Leave everything on Auto to keep Camoufox defaults.")
        navigator_info.setProperty("class", "muted")
        navigator_info.setWordWrap(True)
        navigator_form.addRow(navigator_info)

        def _add_nav_line(field: str, label: str, placeholder: str = "") -> None:
            container, line, toggle = _auto_line_edit(placeholder or label)
            navigator_form.addRow(f"{label}:", container)
            navigator_controls[field] = {"type": "str", "widget": line, "toggle": toggle}

        def _add_nav_list(field: str, label: str, placeholder: str = "") -> None:
            container, text_edit, toggle = _auto_text_edit(placeholder or label, 90)
            navigator_form.addRow(f"{label}:", container)
            navigator_controls[field] = {"type": "list", "widget": text_edit, "toggle": toggle}

        def _add_nav_bool(field: str, label: str) -> None:
            combo = _bool_combo()
            navigator_form.addRow(f"{label}:", combo)
            navigator_controls[field] = {"type": "bool", "widget": combo}

        def _add_nav_int(field: str, label: str, minimum: int, maximum: int, step: int = 1, suffix: str = "") -> None:
            container, spin, toggle = _auto_spinbox(minimum, maximum, step, label.lower(), suffix)
            navigator_form.addRow(f"{label}:", container)
            navigator_controls[field] = {"type": "int", "widget": spin, "toggle": toggle}

        _add_nav_line("userAgent", "User agent", "Mozilla/5.0 ...")
        _add_nav_line("doNotTrack", "Do not track")
        _add_nav_line("appCodeName", "App code name")
        _add_nav_line("appName", "App name")
        _add_nav_line("appVersion", "App version")
        _add_nav_line("oscpu", "OS / CPU info")
        _add_nav_line("platform", "Platform")
        _add_nav_line("language", "Language", "en-US")
        _add_nav_list("languages", "Languages", "en-US\nru-RU")
        _add_nav_int("hardwareConcurrency", "Hardware concurrency", 1, 128)
        _add_nav_int("maxTouchPoints", "Max touch points", 0, 16)
        _add_nav_line("product", "Product")
        _add_nav_line("productSub", "Product sub")
        _add_nav_line("buildID", "Build ID")
        _add_nav_bool("cookieEnabled", "Cookies enabled")
        _add_nav_bool("globalPrivacyControl", "Global Privacy Control")
        _add_nav_bool("onLine", "Online status")
        tabs.addTab(navigator_tab, "Navigator")
        plugins_tab = QWidget()
        plugins_form = QFormLayout(plugins_tab)
        plugins_info = QLabel(
            "Load addons (extracted .xpi folders) and optionally exclude default addons."
        )
        plugins_info.setWordWrap(True)
        plugins_info.setProperty("class", "muted")
        plugins_form.addRow(plugins_info)
        addons_container, addons_input, addons_toggle = _auto_text_edit(
            "Addon folder paths (one per line)", 120
        )
        exclude_container, exclude_input, exclude_toggle = _auto_text_edit(
            "Default addons to exclude (e.g. UBO)", 90
        )
        plugins_form.addRow("Addons:", addons_container)
        plugins_form.addRow("Exclude defaults:", exclude_container)
        plugins_form.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        tabs.addTab(plugins_tab, "Plugins")

        controls = {
            "headless": headless_combo,
            "humanize": humanize_check,
            "humanize_duration": humanize_duration,
            "humanize_duration_toggle": humanize_duration_toggle,
            "humanize_container": humanize_container,
            "locale": locale_input,
            "locale_toggle": locale_toggle,
            "timezone": timezone_input,
            "timezone_toggle": timezone_toggle,
            "os_checks": os_checks,
            "os_auto": os_auto_check,
            "fonts": fonts_edit,
            "webgl_vendor": webgl_vendor_input,
            "webgl_vendor_toggle": webgl_vendor_toggle,
            "webgl_renderer": webgl_renderer_input,
            "webgl_renderer_toggle": webgl_renderer_toggle,
            "window_width": width_spin,
            "window_height": height_spin,
            "window_widget": window_inputs,
            "window_toggle": window_toggle,
            "persistent_context": persistent_context_check,
            "block_webrtc": block_webrtc_check,
            "block_images": block_images_check,
            "block_webgl": block_webgl_check,
            "disable_coop": disable_coop_check,
            "enable_cache": cache_check,
            "window_controls": window_controls,
            "navigator": navigator_controls,
            "addons": addons_input,
            "addons_toggle": addons_toggle,
            "exclude_addons": exclude_input,
            "exclude_addons_toggle": exclude_toggle,
            "fp_spacing_seed": fp_spacing_spin,
            "fp_spacing_seed_toggle": fp_spacing_toggle,
            "fp_canvas_aaoffset": fp_canvas_spin,
            "fp_canvas_aaoffset_toggle": fp_canvas_toggle,
            "fp_window_screeny": fp_screeny_spin,
            "fp_window_screeny_toggle": fp_screeny_toggle,
            "fp_history_length": fp_history_spin,
            "fp_history_length_toggle": fp_history_toggle,
        }
        return controls, tabs

    def _apply_camoufox_controls(self, controls: CamoufoxControls, values: Dict[str, object]) -> None:
        headless_combo = cast(QComboBox, controls["headless"])
        headless_value = values.get("headless", False)
        if isinstance(headless_value, str):
            normalized = headless_value.lower()
            if normalized in {"true", "headless"}:
                headless_value = True
            elif normalized == "virtual":
                headless_value = "virtual"
            else:
                headless_value = False
        idx = headless_combo.findData(headless_value)
        headless_combo.setCurrentIndex(idx if idx >= 0 else 0)

        humanize_check = cast(QCheckBox, controls["humanize"])
        humanize_duration = cast(QDoubleSpinBox, controls["humanize_duration"])
        humanize_toggle = cast(Callable[[bool], None], controls["humanize_duration_toggle"])
        humanize_container = cast(QWidget, controls["humanize_container"])
        humanize_value = values.get("humanize", True)
        if isinstance(humanize_value, bool):
            humanize_check.setChecked(humanize_value)
            humanize_toggle(True)
        else:
            try:
                duration = float(humanize_value)
                if duration <= 0:
                    raise ValueError
                humanize_duration.setValue(duration)
                humanize_check.setChecked(True)
                humanize_toggle(False)
            except Exception:
                humanize_check.setChecked(True)
                humanize_toggle(True)
        humanize_container.setVisible(humanize_check.isChecked())
        humanize_container.setEnabled(humanize_check.isChecked())

        locale_input = cast(QLineEdit, controls["locale"])
        locale_toggle = cast(Callable[[bool], None], controls["locale_toggle"])
        locale_value = str(values.get("locale") or "")
        if locale_value:
            locale_toggle(False)
            locale_input.setText(locale_value)
        else:
            locale_toggle(True)
        timezone_input = cast(QLineEdit, controls["timezone"])
        timezone_toggle = cast(Callable[[bool], None], controls["timezone_toggle"])
        timezone_value = str(values.get("timezone") or "")
        if timezone_value:
            timezone_toggle(False)
            timezone_input.setText(timezone_value)
        else:
            timezone_toggle(True)
        os_checks = cast(Dict[str, QCheckBox], controls["os_checks"])
        os_auto = cast(QCheckBox, controls["os_auto"])
        os_value = values.get("os")
        selected = set()
        if isinstance(os_value, list):
            selected = {str(v).lower() for v in os_value}
        elif isinstance(os_value, str) and os_value.strip():
            selected = {os_value.strip().lower()}
        for name, checkbox in os_checks.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(name in selected)
            checkbox.blockSignals(False)
        os_auto.blockSignals(True)
        os_auto.setChecked(len(selected) == 0)
        os_auto.blockSignals(False)

        fonts_edit = cast(QTextEdit, controls["fonts"])
        fonts_value = values.get("fonts")
        if isinstance(fonts_value, list):
            fonts_edit.setPlainText("\n".join(str(v) for v in fonts_value))
        else:
            fonts_edit.setPlainText(str(fonts_value or ""))

        width_spin = cast(QSpinBox, controls["window_width"])
        height_spin = cast(QSpinBox, controls["window_height"])
        window_toggle = cast(Callable[[bool], None], controls["window_toggle"])
        try:
            width_spin.setValue(int(values.get("window_width") or 0))
        except Exception:
            width_spin.setValue(0)
        try:
            height_spin.setValue(int(values.get("window_height") or 0))
        except Exception:
            height_spin.setValue(0)
        if width_spin.value() > 0 and height_spin.value() > 0:
            window_toggle(False)
        else:
            window_toggle(True)

        webgl_vendor_input = cast(QLineEdit, controls["webgl_vendor"])
        webgl_vendor_toggle = cast(Callable[[bool], None], controls["webgl_vendor_toggle"])
        vendor_value = str(values.get("webgl_vendor") or "")
        if vendor_value:
            webgl_vendor_toggle(False)
            webgl_vendor_input.setText(vendor_value)
        else:
            webgl_vendor_toggle(True)

        webgl_renderer_input = cast(QLineEdit, controls["webgl_renderer"])
        webgl_renderer_toggle = cast(Callable[[bool], None], controls["webgl_renderer_toggle"])
        renderer_value = str(values.get("webgl_renderer") or "")
        if renderer_value:
            webgl_renderer_toggle(False)
            webgl_renderer_input.setText(renderer_value)
        else:
            webgl_renderer_toggle(True)

        for key in (
            "block_webrtc",
            "block_images",
            "block_webgl",
            "disable_coop",
            "enable_cache",
            "persistent_context",
        ):
            checkbox = cast(QCheckBox, controls[key])
            checkbox.setChecked(bool(values.get(key, CAMOUFOX_DEFAULTS.get(key, False))))

        window_values = values.get("window_overrides")
        if not isinstance(window_values, dict):
            window_values = {}
        window_controls_map = cast(Dict[str, Dict[str, object]], controls.get("window_controls", {}))

        def _value_from_path(payload: Dict[str, object], key_path: str) -> Optional[object]:
            node: Optional[object] = payload
            for part in key_path.split("."):
                if not isinstance(node, dict):
                    return None
                node = node.get(part)
            return node

        for key, meta in window_controls_map.items():
            widget = meta.get("widget")
            toggle = meta.get("toggle")
            entry_type = meta.get("type")
            value = _value_from_path(window_values, key)
            if value is None:
                if callable(toggle):
                    toggle(True)
                continue
            try:
                if entry_type == "int":
                    cast(QSpinBox, widget).setValue(int(value))
                elif entry_type == "double":
                    cast(QDoubleSpinBox, widget).setValue(float(value))
            except Exception:
                if callable(toggle):
                    toggle(True)
                continue
            if callable(toggle):
                toggle(False)

        navigator_values = values.get("navigator_overrides")
        if not isinstance(navigator_values, dict):
            navigator_values = {}
        navigator_controls = cast(Dict[str, Dict[str, object]], controls.get("navigator", {}))
        for field, meta in navigator_controls.items():
            entry_type = meta.get("type")
            payload = navigator_values.get(field)
            if entry_type == "str":
                widget = cast(QLineEdit, meta["widget"])
                toggle = cast(Callable[[bool], None], meta["toggle"])
                text = str(payload or "").strip()
                if text:
                    toggle(False)
                    widget.setText(text)
                else:
                    widget.clear()
                    toggle(True)
            elif entry_type == "list":
                widget = cast(QTextEdit, meta["widget"])
                toggle = cast(Callable[[bool], None], meta["toggle"])
                if isinstance(payload, list):
                    formatted = "\n".join(str(v) for v in payload)
                elif isinstance(payload, str):
                    formatted = payload.strip()
                else:
                    formatted = ""
                if formatted:
                    widget.setPlainText(formatted)
                    toggle(False)
                else:
                    widget.clear()
                    toggle(True)
            elif entry_type == "bool":
                combo = cast(QComboBox, meta["widget"])
                value = payload if isinstance(payload, bool) else None
                idx = combo.findData(value)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
            elif entry_type == "int":
                spin = cast(QSpinBox, meta["widget"])
                toggle = cast(Callable[[bool], None], meta["toggle"])
                if isinstance(payload, bool):
                    payload = int(payload)
                if isinstance(payload, (int, float)):
                    spin.setValue(int(payload))
                    toggle(False)
                else:
                    toggle(True)

        def _apply_list_control(key: str, toggle_key: str, value: object) -> None:
            widget = controls.get(key)
            toggle = controls.get(toggle_key)
            if not widget or not callable(toggle):
                return
            if isinstance(value, list):
                formatted = "\n".join(str(v) for v in value if str(v))
            elif isinstance(value, str):
                formatted = value.strip()
            else:
                formatted = ""
            if formatted:
                cast(QTextEdit, widget).setPlainText(formatted)
                toggle(False)
            else:
                cast(QTextEdit, widget).clear()
                toggle(True)

        _apply_list_control("addons", "addons_toggle", values.get("addons"))
        _apply_list_control("exclude_addons", "exclude_addons_toggle", values.get("exclude_addons"))

    def _collect_camoufox_controls(self, controls: CamoufoxControls) -> Dict[str, object]:
        headless_combo = cast(QComboBox, controls["headless"])
        humanize_check = cast(QCheckBox, controls["humanize"])
        humanize_duration = cast(QDoubleSpinBox, controls["humanize_duration"])
        locale_input = cast(QLineEdit, controls["locale"])
        timezone_input = cast(QLineEdit, controls["timezone"])
        os_checks = cast(Dict[str, QCheckBox], controls["os_checks"])
        fonts_edit = cast(QTextEdit, controls["fonts"])
        width_spin = cast(QSpinBox, controls["window_width"])
        height_spin = cast(QSpinBox, controls["window_height"])
        window_widget = cast(QWidget, controls["window_widget"])
        block_webrtc = cast(QCheckBox, controls["block_webrtc"])
        block_images = cast(QCheckBox, controls["block_images"])
        block_webgl = cast(QCheckBox, controls["block_webgl"])
        disable_coop = cast(QCheckBox, controls["disable_coop"])
        cache_check = cast(QCheckBox, controls["enable_cache"])
        persistent_context = cast(QCheckBox, controls["persistent_context"])
        webgl_vendor = cast(QLineEdit, controls["webgl_vendor"])
        webgl_renderer = cast(QLineEdit, controls["webgl_renderer"])

        def _text_list(raw: str) -> List[str]:
            items: List[str] = []
            for part in raw.replace("\r", "\n").split("\n"):
                normalized = part.strip()
                if normalized:
                    items.append(normalized)
            return items

        os_selected = [name for name, checkbox in os_checks.items() if checkbox.isChecked()]
        locale_value = locale_input.text().strip() if locale_input.isVisible() else ""
        timezone_value = timezone_input.text().strip() if timezone_input.isVisible() else ""
        vendor_value = webgl_vendor.text().strip() if webgl_vendor.isVisible() else ""
        renderer_value = webgl_renderer.text().strip() if webgl_renderer.isVisible() else ""
        width_value = width_spin.value() if window_widget.isVisible() else 0
        height_value = height_spin.value() if window_widget.isVisible() else 0

        if not humanize_check.isChecked():
            humanize_value: object = False
        elif humanize_duration.isVisible():
            humanize_value = round(float(humanize_duration.value()), 2)
        else:
            humanize_value = True

        window_controls_map = cast(Dict[str, Dict[str, object]], controls.get("window_controls", {}))
        window_overrides: Dict[str, object] = {}

        def _assign_window_value(path: List[str], value: object) -> None:
            if not path:
                return
            node: Dict[str, object] = window_overrides
            for part in path[:-1]:
                child = node.get(part)
                if not isinstance(child, dict):
                    child = {}
                    node[part] = child
                node = cast(Dict[str, object], child)
            node[path[-1]] = value

        for key, meta in window_controls_map.items():
            widget = cast(QWidget, meta.get("widget"))
            if widget is None or not widget.isVisible():
                continue
            entry_type = meta.get("type")
            if entry_type == "int":
                value = int(cast(QSpinBox, widget).value())
            elif entry_type == "double":
                value = round(float(cast(QDoubleSpinBox, widget).value()), 4)
            else:
                continue
            _assign_window_value(key.split("."), value)

        navigator_controls = cast(Dict[str, Dict[str, object]], controls.get("navigator", {}))
        navigator_values: Dict[str, object] = {}
        for field, meta in navigator_controls.items():
            entry_type = meta.get("type")
            if entry_type == "str":
                widget = cast(QLineEdit, meta["widget"])
                if widget.isVisible():
                    text = widget.text().strip()
                    if text:
                        navigator_values[field] = text
            elif entry_type == "list":
                widget = cast(QTextEdit, meta["widget"])
                if widget.isVisible():
                    entries = _text_list(widget.toPlainText())
                    if entries:
                        navigator_values[field] = entries
            elif entry_type == "bool":
                combo = cast(QComboBox, meta["widget"])
                val = combo.currentData()
                if isinstance(val, bool):
                    navigator_values[field] = val
            elif entry_type == "int":
                spin = cast(QSpinBox, meta["widget"])
                if spin.isVisible():
                    navigator_values[field] = int(spin.value())

        addons_list: List[str] = []
        addons_widget = cast(QTextEdit, controls.get("addons"))
        if addons_widget is not None and addons_widget.isVisible():
            addons_list = _text_list(addons_widget.toPlainText())

        exclude_list: List[str] = []
        exclude_widget = cast(QTextEdit, controls.get("exclude_addons"))
        if exclude_widget is not None and exclude_widget.isVisible():
            exclude_list = _text_list(exclude_widget.toPlainText())

        result = {
            "headless": headless_combo.currentData(),
            "humanize": humanize_value,
            "locale": locale_value,
            "timezone": timezone_value,
            "os": os_selected,
            "fonts": _text_list(fonts_edit.toPlainText()),
            "window_width": width_value,
            "window_height": height_value,
            "block_webrtc": block_webrtc.isChecked(),
            "block_images": block_images.isChecked(),
            "block_webgl": block_webgl.isChecked(),
            "disable_coop": disable_coop.isChecked(),
            "enable_cache": cache_check.isChecked(),
            "persistent_context": persistent_context.isChecked(),
            "webgl_vendor": vendor_value,
            "webgl_renderer": renderer_value,
            "addons": addons_list,
            "exclude_addons": exclude_list,
            "window_overrides": window_overrides,
            "navigator_overrides": navigator_values,
        }
        return result

    def _load_camoufox_defaults(self) -> None:
        self.camoufox_defaults = db_get_camoufox_defaults()
        if self._camoufox_controls:
            self._apply_camoufox_controls(self._camoufox_controls, self.camoufox_defaults)

    def _apply_camoufox_defaults_to_form(self) -> None:
        if self._camoufox_controls:
            self._apply_camoufox_controls(self._camoufox_controls, self.camoufox_defaults)

    def _save_camoufox_defaults(self) -> None:
        if not self._camoufox_controls:
            return
        values = self._collect_camoufox_controls(self._camoufox_controls)
        db_set_camoufox_defaults(values)
        self.camoufox_defaults = values
        self.log("Saved Camoufox defaults")

    def _reset_camoufox_defaults(self) -> None:
        self.camoufox_defaults = dict(CAMOUFOX_DEFAULTS)
        if self._camoufox_controls:
            self._apply_camoufox_controls(self._camoufox_controls, self.camoufox_defaults)
        db_set_camoufox_defaults(self.camoufox_defaults)
        self.log("Camoufox defaults restored")

    def _load_ui_theme_preference(self) -> str:
        theme_raw = db_get_setting("ui_theme")
        normalized = normalize_theme(theme_raw)
        self.current_theme = normalized
        return normalized

    def _handle_theme_selection(self, value: Optional[str]) -> None:
        if value in (None, ""):
            return
        self._set_ui_theme(str(value))

    def _set_ui_theme(self, theme: Optional[str]) -> None:
        normalized = normalize_theme(theme)
        if normalized == getattr(self, "current_theme", DEFAULT_THEME):
            return
        self.current_theme = normalized
        app = QApplication.instance()
        if app:
            apply_modern_theme(app, normalized)
        if hasattr(self, "_refresh_log_colors"):
            self._refresh_log_colors()
        db_set_setting("ui_theme", normalized)
        if self._theme_combo is not None:
            idx = self._theme_combo.findData(normalized)
            if idx >= 0 and self._theme_combo.currentIndex() != idx:
                self._theme_combo.blockSignals(True)
                self._theme_combo.setCurrentIndex(idx)
                self._theme_combo.blockSignals(False)
        self.refresh_accounts_list()
        self.log(f"Theme switched to {normalized}")

    def _update_nav_state(self, index: int) -> None:
        for idx, btn in self._nav_buttons.items():
            btn.setChecked(idx == index)

    def _load_account_template(self) -> None:
        tmpl = db_get_setting("account_parse_template") or DEFAULT_ACCOUNT_TEMPLATE
        self.account_parse_template = tmpl

    def _save_account_template(self, value: Optional[str] = None) -> None:
        tmpl = (value if value is not None else self.account_parse_template) or DEFAULT_ACCOUNT_TEMPLATE
        tmpl = tmpl.strip() or DEFAULT_ACCOUNT_TEMPLATE
        self.account_parse_template = tmpl
        db_set_setting("account_parse_template", tmpl)

    def _expand_to_screen(self) -> None:
        self.showMaximized()

    def _on_tab_changed(self, index: int) -> None:
        self._update_nav_state(index)
        if index == getattr(self, "_run_tab_index", -1):
            self.refresh_accounts_list()
            self._load_shared_vars()
