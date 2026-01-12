from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.style import create_card


def build_proxies_tab(main) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(18)

    hero_card, hero_layout, _ = create_card(tab)
    hero_title = QLabel("Proxy pools")
    hero_title.setProperty("class", "heroTitle")
    hero_layout.addWidget(hero_title)
    hero_caption = QLabel("Organize unlimited proxy lists, reuse them across profiles, and monitor assignments.")
    hero_caption.setProperty("class", "muted")
    hero_layout.addWidget(hero_caption)
    layout.addWidget(hero_card)

    body_row = QHBoxLayout()
    body_row.setSpacing(18)

    pools_card, pools_layout, _ = create_card(tab, "Pools")
    main.proxy_pool_list = QListWidget()
    main.proxy_pool_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    main.proxy_pool_list.itemSelectionChanged.connect(main._on_proxy_pool_selected)
    pools_layout.addWidget(main.proxy_pool_list, 1)
    pools_btns = QHBoxLayout()
    btn_add = QPushButton("New pool")
    btn_add.setProperty("class", "primary")
    btn_add.clicked.connect(main._add_proxy_pool)
    btn_rename = QPushButton("Rename")
    btn_rename.clicked.connect(main._rename_proxy_pool)
    btn_delete = QPushButton("Delete")
    btn_delete.clicked.connect(main._delete_proxy_pool)
    pools_btns.addWidget(btn_add)
    pools_btns.addWidget(btn_rename)
    pools_btns.addWidget(btn_delete)
    pools_btns.addStretch()
    pools_layout.addLayout(pools_btns)
    body_row.addWidget(pools_card, 1)

    details_card, details_layout, _ = create_card(tab, "Pool details")
    main.proxy_pool_title = QLabel("Select a pool")
    main.proxy_pool_title.setProperty("class", "cardTitle")
    details_layout.addWidget(main.proxy_pool_title)
    main.proxy_pool_stats = QLabel("0 proxies")
    main.proxy_pool_stats.setProperty("class", "muted")
    details_layout.addWidget(main.proxy_pool_stats)

    main.proxy_items_list = QListWidget()
    main.proxy_items_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    main.proxy_items_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    main.proxy_items_list.customContextMenuRequested.connect(main._show_proxy_context_menu)
    details_layout.addWidget(main.proxy_items_list, 1)

    actions_row = QHBoxLayout()
    main.btn_check_proxies = QPushButton("Check internet")
    main.btn_check_proxies.clicked.connect(lambda: main._check_current_pool_proxies(selected_only=False))
    actions_row.addWidget(main.btn_check_proxies)
    btn_release = QPushButton("Release selected")
    btn_release.clicked.connect(main._release_selected_pool_proxies)
    btn_remove = QPushButton("Remove selected")
    btn_remove.clicked.connect(main._remove_selected_pool_proxies)
    actions_row.addWidget(btn_release)
    actions_row.addWidget(btn_remove)
    actions_row.addStretch()
    details_layout.addLayout(actions_row)

    import_label = QLabel("Bulk import (one proxy per line) — duplicates are ignored.")
    import_label.setProperty("class", "muted")
    details_layout.addWidget(import_label)
    main.proxy_batch_input = QTextEdit()
    main.proxy_batch_input.setPlaceholderText("ip:port:login:password")
    main.proxy_batch_input.setFixedHeight(110)
    details_layout.addWidget(main.proxy_batch_input)
    import_row = QHBoxLayout()
    btn_import = QPushButton("Append proxies")
    btn_import.setProperty("class", "primary")
    btn_import.clicked.connect(main._append_proxies_to_pool)
    btn_clear = QPushButton("Clear input")
    btn_clear.clicked.connect(main.proxy_batch_input.clear)
    import_row.addWidget(btn_import)
    import_row.addWidget(btn_clear)
    import_row.addStretch()
    details_layout.addLayout(import_row)

    body_row.addWidget(details_card, 2)

    layout.addLayout(body_row)
    layout.addStretch()
    return tab
