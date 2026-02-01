from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from app.ui.style import create_card


def build_logs_tab(main) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(18)
    log_card, log_layout, _ = create_card(tab, "Activity log")
    main.log_edit = QTextEdit()
    main.log_edit.setReadOnly(True)
    main.log_edit.setObjectName("logView")
    log_layout.addWidget(main.log_edit)
    layout.addWidget(log_card)
    return tab
