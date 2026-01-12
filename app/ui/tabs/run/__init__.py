from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QCheckBox,
    QTextEdit,
    QPushButton,
    QListWidget,
    QSpinBox,
    QWidget,
    QLineEdit,
)

from app.ui.style import create_card


def build_run_tab(main) -> QWidget:
    """Build the redesigned run tab using card-like sections."""
    tab = QWidget()
    main_layout = QVBoxLayout(tab)
    main_layout.setContentsMargins(6, 6, 6, 6)
    main_layout.setSpacing(18)

    hero_card, hero_layout, _ = create_card(tab)
    hero_header = QLabel("Profiles")
    hero_header.setProperty("class", "heroTitle")
    hero_layout.addWidget(hero_header)
    stats_row = QHBoxLayout()
    main.profile_count_label = QLabel("0 profiles")
    main.profile_count_label.setProperty("class", "statValue")
    stats_row.addWidget(main.profile_count_label)
    main.profile_status_label = QLabel("0 undefined")
    main.profile_status_label.setProperty("class", "muted")
    stats_row.addWidget(main.profile_status_label)
    stats_row.addStretch()
    hero_layout.addLayout(stats_row)
    hero_caption = QLabel("Import accounts, attach proxies, and launch scenarios in one workspace.")
    hero_caption.setProperty("class", "muted")
    hero_layout.addWidget(hero_caption)
    main_layout.addWidget(hero_card)

    list_card, list_layout, _ = create_card(tab)
    header_row = QHBoxLayout()
    header_label = QLabel("Profiles and tags")
    header_label.setProperty("class", "cardTitle")
    header_row.addWidget(header_label)
    header_row.addStretch()
    share_btn = QPushButton("Shared variables")
    share_btn.setProperty("class", "ghost")
    share_btn.clicked.connect(main._open_shared_vars_dialog)
    header_row.addWidget(share_btn)
    add_btn = QPushButton("Add profiles")
    add_btn.setProperty("class", "primary")
    add_btn.clicked.connect(main._open_import_dialog)
    header_row.addWidget(add_btn)
    list_layout.addLayout(header_row)

    filter_block = QVBoxLayout()
    search_row = QHBoxLayout()
    main.accounts_search_input = QLineEdit()
    main.accounts_search_input.setPlaceholderText("Profile title or description")
    main.accounts_search_input.setProperty("class", "search")
    main.accounts_search_input.textChanged.connect(main._apply_accounts_filter)
    search_row.addWidget(main.accounts_search_input, 1)
    clear_btn = QPushButton("Clear")
    clear_btn.setProperty("class", "ghost")
    clear_btn.clicked.connect(lambda _: main.accounts_search_input.clear())
    search_row.addWidget(clear_btn)
    filter_block.addLayout(search_row)
    chips_row = QHBoxLayout()
    chips_caption = QLabel("Tags")
    chips_caption.setProperty("class", "muted")
    chips_row.addWidget(chips_caption)
    manage_btn = QPushButton("Manage tags")
    manage_btn.setProperty("class", "ghost")
    manage_btn.clicked.connect(main._open_stage_dialog)
    chips_row.addWidget(manage_btn)
    chips_row.addStretch()
    chips_row.addWidget(QLabel("Delete tag"))
    main.delete_tag_combo = QComboBox()
    main.delete_tag_combo.setMinimumWidth(180)
    chips_row.addWidget(main.delete_tag_combo)
    main.delete_tag_proxy_check = QCheckBox("Remove proxies")
    main.delete_tag_proxy_check.setChecked(False)
    chips_row.addWidget(main.delete_tag_proxy_check)
    delete_tag_btn = QPushButton("Delete profiles")
    delete_tag_btn.setProperty("class", "danger")
    delete_tag_btn.clicked.connect(main._delete_profiles_by_tag)
    chips_row.addWidget(delete_tag_btn)
    filter_block.addLayout(chips_row)
    chips_widget = QWidget()
    chips_layout = QHBoxLayout(chips_widget)
    chips_layout.setContentsMargins(0, 0, 0, 0)
    chips_layout.setSpacing(8)
    main.stage_filter_layout = chips_layout
    filter_block.addWidget(chips_widget)
    list_layout.addLayout(filter_block)
    columns_row = QHBoxLayout()
    columns = [
        ("Name", 3, Qt.AlignmentFlag.AlignLeft),
        ("Proxy", 2, Qt.AlignmentFlag.AlignLeft),
        ("Tags", 2, Qt.AlignmentFlag.AlignLeft),
        ("Actions", 1, Qt.AlignmentFlag.AlignRight),
    ]
    for title, stretch, align in columns:
        lbl = QLabel(title)
        lbl.setProperty("class", "columnHeader")
        lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        columns_row.addWidget(lbl, stretch)
    list_layout.addLayout(columns_row)
    main.accounts_list = QListWidget()
    main.accounts_list.setObjectName("accountsList")
    main.accounts_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    main.accounts_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    main.accounts_list.customContextMenuRequested.connect(main._show_account_context_menu)
    main.accounts_list.itemSelectionChanged.connect(main._update_row_selection_styles)
    list_layout.addWidget(main.accounts_list)

    run_controls = QHBoxLayout()
    run_controls.addWidget(QLabel("Tag"))
    main.run_stage_combo = QComboBox()
    main.run_stage_combo.setMinimumWidth(150)
    run_controls.addWidget(main.run_stage_combo)
    run_controls.addWidget(QLabel("Scenario"))
    main.scenario_run_combo = QComboBox()
    run_controls.addWidget(main.scenario_run_combo, 1)
    run_controls.addWidget(QLabel("Max accounts"))
    main.count_spin = QSpinBox()
    main.count_spin.setRange(1, 100)
    main.count_spin.setValue(1)
    run_controls.addWidget(main.count_spin)
    main.btn_run_stage = QPushButton("Run for tag")
    main.btn_run_stage.setProperty("class", "primary")
    main.btn_run_stage.clicked.connect(main.run_scenario_for_stage)
    run_controls.addWidget(main.btn_run_stage)
    list_layout.addLayout(run_controls)

    main_layout.addWidget(list_card)

    return tab
