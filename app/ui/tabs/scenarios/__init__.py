from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QFormLayout,
    QCheckBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from app.ui.scenario_editor import ScenarioEditor
from app.ui.style import create_card

ACTION_OPTIONS_FORM: List[Tuple[str, str]] = [
    ("Open URL", "goto"),
    ("HTTP request", "http_request"),
    ("Wait for element", "wait_element"),
    ("Wait for page load", "wait_for_load_state"),
    ("Sleep", "sleep"),
    ("Click element", "click"),
    ("Type text", "type"),
    ("Set variable", "set_var"),
    ("Parse variable", "parse_var"),
    ("Pop from shared", "pop_shared"),
    ("Extract text", "extract_text"),
    ("Write to file", "write_file"),
    ("Compare / if", "compare"),
    ("Open new tab", "new_tab"),
    ("Switch tab", "switch_tab"),
    ("Close tab", "close_tab"),
    ("Set tag", "set_tag"),
    ("Close browser", "end"),
    ("Run another scenario", "run_scenario"),
    ("Log / message", "log"),
]

ACTION_OPTIONS_DIALOG: List[Tuple[str, str]] = [("Start scenario", "start")] + ACTION_OPTIONS_FORM
ACTION_LABELS = {value: label for label, value in ACTION_OPTIONS_DIALOG}


def build_scenarios_tab(main) -> QWidget:
    tab = QWidget()
    scenario_layout = QVBoxLayout(tab)
    scenario_layout.setContentsMargins(6, 6, 6, 6)
    scenario_layout.setSpacing(18)

    scenario_top = QHBoxLayout()
    scenario_top.setSpacing(18)
    scenario_list_card, scenario_list_layout, _ = create_card(tab, "Scenario library")
    main.scenario_list_widget = QListWidget()
    main.scenario_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    main.scenario_list_widget.itemSelectionChanged.connect(main._on_scenario_selected)
    main.scenario_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    main.scenario_list_widget.customContextMenuRequested.connect(main._show_scenario_context_menu)
    scenario_list_layout.addWidget(main.scenario_list_widget, 1)
    scenario_buttons = QHBoxLayout()
    btn_new_scenario = QPushButton("New")
    btn_new_scenario.clicked.connect(main._new_scenario)
    btn_load_scenario = QPushButton("Load")
    btn_load_scenario.clicked.connect(main._load_selected_scenario)
    btn_save_scenario = QPushButton("Save")
    btn_save_scenario.clicked.connect(main._save_scenario)
    btn_duplicate_scenario = QPushButton("Duplicate")
    btn_duplicate_scenario.clicked.connect(main._duplicate_selected_scenario)
    btn_delete_scenario = QPushButton("Delete")
    btn_delete_scenario.clicked.connect(main._delete_selected_scenario)
    scenario_buttons.addWidget(btn_new_scenario)
    scenario_buttons.addWidget(btn_load_scenario)
    scenario_buttons.addWidget(btn_save_scenario)
    scenario_buttons.addWidget(btn_duplicate_scenario)
    scenario_buttons.addWidget(btn_delete_scenario)
    scenario_list_layout.addLayout(scenario_buttons)
    scenario_top.addWidget(scenario_list_card, 1)

    details_card, scenario_editor_layout, _ = create_card(tab, "Details")
    name_row = QHBoxLayout()
    name_row.addWidget(QLabel("Name:"))
    main.scenario_name_input = QLineEdit()
    name_row.addWidget(main.scenario_name_input)
    name_row.addWidget(QLabel("Description:"))
    main.scenario_description_input = QLineEdit()
    name_row.addWidget(main.scenario_description_input)
    scenario_editor_layout.addLayout(name_row)

    vars_row = QHBoxLayout()
    vars_row.addWidget(QLabel("Variables in scenario:"))
    main.vars_list = QListWidget()
    main.vars_list.setMinimumHeight(80)
    vars_row.addWidget(main.vars_list, 1)
    scenario_editor_layout.addLayout(vars_row)
    scenario_top.addWidget(details_card, 2)

    # Hidden container keeps logic-only widgets parented so they don't pop as floating windows
    hidden_container = QWidget(tab)
    hidden_container.setVisible(False)
    hidden_layout = QVBoxLayout(hidden_container)

    # Hidden steps list (logic only)
    main.steps_list = QListWidget()
    main.steps_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    main.steps_list.itemSelectionChanged.connect(main._fill_step_form_from_selection)
    main.steps_list.itemActivated.connect(lambda _: None)
    hidden_layout.addWidget(main.steps_list)

    # Hidden form (logic only)
    form = QFormLayout()
    main.step_tag_input = QLineEdit()
    main.row_tag = (QLabel("Tag:"), main.step_tag_input)
    form.addRow(*main.row_tag)

    main.step_action_combo = QComboBox()
    for label, value in ACTION_OPTIONS_FORM:
        main.step_action_combo.addItem(label, value)
    main.step_action_combo.currentIndexChanged.connect(main._handle_action_combo_change)
    form.addRow("Action:", main.step_action_combo)

    main.step_selector_input = QLineEdit()
    main.row_selector = (QLabel("Selector:"), main.step_selector_input)
    form.addRow(*main.row_selector)

    main.step_selector_type_input = QComboBox()
    main.step_selector_type_input.addItems(["css", "text", "xpath", "id", "name", "test_id"])
    main.row_selector_type = (QLabel("Selector type:"), main.step_selector_type_input)
    form.addRow(*main.row_selector_type)

    main.step_selector_index = QSpinBox()
    main.step_selector_index.setRange(0, 50)
    main.row_selector_index = (QLabel("Selector index (nth):"), main.step_selector_index)
    form.addRow(*main.row_selector_index)

    main.step_targets_input = QLineEdit()
    main.row_targets = (QLabel("Targets / pattern:"), main.step_targets_input)
    form.addRow(*main.row_targets)

    main.step_frame_input = QLineEdit()
    main.row_frame = (QLabel("Iframe selector:"), main.step_frame_input)
    form.addRow(*main.row_frame)

    main.step_value_input = QLineEdit()
    main.row_value = (QLabel("Value:"), main.step_value_input)
    form.addRow(*main.row_value)

    main.step_parse_update_account = QCheckBox("Update account (save to profile)")
    main.step_parse_update_account.setChecked(True)
    main.row_parse_update_account = (QLabel(""), main.step_parse_update_account)
    form.addRow(*main.row_parse_update_account)

    main.step_compare_op_input = QComboBox()
    main.step_compare_op_input.addItems(
        [
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "startswith",
            "endswith",
            "regex",
            "is_empty",
            "not_empty",
            "gt",
            "gte",
            "lt",
            "lte",
        ]
    )
    main.row_compare_op = (QLabel("Compare operator:"), main.step_compare_op_input)
    form.addRow(*main.row_compare_op)

    main.step_compare_right_var_input = QLineEdit()
    main.step_compare_right_var_input.setPlaceholderText("right_var (optional)")
    main.row_compare_right_var = (QLabel("Right variable:"), main.step_compare_right_var_input)
    form.addRow(*main.row_compare_right_var)

    main.step_compare_result_var_input = QLineEdit()
    main.step_compare_result_var_input.setPlaceholderText("result_var (optional)")
    main.row_compare_result_var = (QLabel("Result variable:"), main.step_compare_result_var_input)
    form.addRow(*main.row_compare_result_var)

    main.step_compare_case_sensitive = QCheckBox("Case sensitive")
    main.row_compare_case_sensitive = (QLabel(""), main.step_compare_case_sensitive)
    form.addRow(*main.row_compare_case_sensitive)

    main.step_http_method_combo = QComboBox()
    main.step_http_method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    main.row_http_method = (QLabel("HTTP method:"), main.step_http_method_combo)
    form.addRow(*main.row_http_method)

    main.step_http_headers_input = QTextEdit()
    main.step_http_headers_input.setPlaceholderText("Authorization: Bearer {{token}}\nAccept: application/json")
    main.step_http_headers_input.setFixedHeight(70)
    main.row_http_headers = (QLabel("HTTP headers:"), main.step_http_headers_input)
    form.addRow(*main.row_http_headers)

    main.step_http_params_input = QTextEdit()
    main.step_http_params_input.setPlaceholderText("q={{login}}\npage=1")
    main.step_http_params_input.setFixedHeight(60)
    main.row_http_params = (QLabel("Query params:"), main.step_http_params_input)
    form.addRow(*main.row_http_params)

    main.step_http_body_input = QTextEdit()
    main.step_http_body_input.setPlaceholderText("Request body (text) or JSON")
    main.step_http_body_input.setFixedHeight(90)
    main.row_http_body = (QLabel("Body:"), main.step_http_body_input)
    form.addRow(*main.row_http_body)

    main.step_http_body_is_json = QCheckBox("Parse body as JSON")
    main.row_http_body_is_json = (QLabel(""), main.step_http_body_is_json)
    form.addRow(*main.row_http_body_is_json)

    main.step_http_save_as_input = QLineEdit()
    main.step_http_save_as_input.setPlaceholderText("http (prefix for variables)")
    main.row_http_save_as = (QLabel("Save as:"), main.step_http_save_as_input)
    form.addRow(*main.row_http_save_as)

    main.step_http_response_var_input = QLineEdit()
    main.step_http_response_var_input.setPlaceholderText("last_response (optional)")
    main.row_http_response_var = (QLabel("Response var:"), main.step_http_response_var_input)
    form.addRow(*main.row_http_response_var)

    main.step_http_extract_input = QTextEdit()
    main.step_http_extract_input.setPlaceholderText("token=$.token\nuser_id=$.user.id")
    main.step_http_extract_input.setFixedHeight(70)
    main.row_http_extract = (QLabel("Extract JSON:"), main.step_http_extract_input)
    form.addRow(*main.row_http_extract)

    main.step_http_require_success = QCheckBox("Stop if status is not 2xx")
    main.row_http_require_success = (QLabel(""), main.step_http_require_success)
    form.addRow(*main.row_http_require_success)

    main.step_http_fail_on_status_code = QCheckBox("Fail on non-2xx (Playwright)")
    main.row_http_fail_on_status_code = (QLabel(""), main.step_http_fail_on_status_code)
    form.addRow(*main.row_http_fail_on_status_code)

    main.step_http_ignore_https_errors = QCheckBox("Ignore HTTPS errors")
    main.row_http_ignore_https_errors = (QLabel(""), main.step_http_ignore_https_errors)
    form.addRow(*main.row_http_ignore_https_errors)

    main.step_http_max_redirects = QSpinBox()
    main.step_http_max_redirects.setRange(0, 50)
    main.row_http_max_redirects = (QLabel("Max redirects:"), main.step_http_max_redirects)
    form.addRow(*main.row_http_max_redirects)

    main.step_http_max_retries = QSpinBox()
    main.step_http_max_retries.setRange(0, 20)
    main.row_http_max_retries = (QLabel("Max retries:"), main.step_http_max_retries)
    form.addRow(*main.row_http_max_retries)

    main.step_variable_input = QLineEdit()
    main.row_variable = (QLabel("Variable name:"), main.step_variable_input)
    form.addRow(*main.row_variable)

    main.step_attribute_input = QLineEdit()
    main.row_attribute = (QLabel("Attribute (for extract):"), main.step_attribute_input)
    form.addRow(*main.row_attribute)


    main.step_state_input = QComboBox()
    main.step_state_input.addItems(
        ["", "load", "domcontentloaded", "networkidle", "commit", "visible", "attached", "hidden"]
    )
    main.row_state = (QLabel("State / status:"), main.step_state_input)
    form.addRow(*main.row_state)

    main.step_timeout_input = QSpinBox()
    main.step_timeout_input.setRange(0, 600000)
    main.step_timeout_input.setValue(60000)
    main.row_timeout = (QLabel("Timeout, ms:"), main.step_timeout_input)
    form.addRow(*main.row_timeout)

    main.step_sleep_input = QDoubleSpinBox()
    main.step_sleep_input.setDecimals(3)
    main.step_sleep_input.setRange(0, 300)
    main.row_sleep = (QLabel("Sleep, sec:"), main.step_sleep_input)
    form.addRow(*main.row_sleep)

    main.step_tab_index = QSpinBox()
    main.step_tab_index.setRange(0, 20)
    main.row_tab = (QLabel("Tab index:"), main.step_tab_index)
    form.addRow(*main.row_tab)

    main.step_jump_missing_input = QLineEdit()
    main.row_jump_missing = (QLabel("Jump if missing:"), main.step_jump_missing_input)
    form.addRow(*main.row_jump_missing)
    main.step_jump_found_input = QLineEdit()
    main.row_jump_found = (QLabel("Jump if found:"), main.step_jump_found_input)
    form.addRow(*main.row_jump_found)
    hidden_layout.addLayout(form)

    # Action map fills most space
    scenario_layout.addLayout(scenario_top)
    map_card, map_layout, _ = create_card(tab, "Action map")
    main.map_view = ScenarioEditor()
    main.map_view.set_action_labels(ACTION_LABELS)
    main.map_view.setMinimumHeight(420)
    main.map_view.on_select = main._on_map_select
    main.map_view.on_add_after = main._on_map_add_after
    main.map_view.on_move = main._on_map_move
    main.map_view.on_drag_end = main._on_map_drag_end
    main.map_view.on_edit = main._on_map_edit
    main.map_view.on_delete = main._on_map_delete
    main.map_view.on_add_detached = main._on_map_add_detached
    map_layout.addWidget(main.map_view, 1)
    scenario_layout.addWidget(map_card, 1)
    scenario_layout.addWidget(hidden_container)

    return tab
