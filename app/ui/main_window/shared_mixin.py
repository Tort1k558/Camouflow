"""Shared variables and stages management."""

from __future__ import annotations

import json
from typing import Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from app.storage.db import db_get_accounts, db_get_setting, db_set_setting, db_update_stage


class SharedDataMixin:
    def _clear_shared_dialog_refs(self) -> None:
        for attr in ("shared_vars_list", "shared_key_input", "shared_type_input", "shared_value_input"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _open_shared_vars_dialog(self) -> None:
        self._clear_shared_dialog_refs()
        dlg = QDialog(self)
        dlg.setWindowTitle("Shared variables")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        intro = QLabel("Shared variables are available to every scenario. Lists use one value per line.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.shared_vars_list = QListWidget()
        self.shared_vars_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.shared_vars_list.itemSelectionChanged.connect(self._on_shared_var_selected)
        layout.addWidget(self.shared_vars_list)

        form_row = QHBoxLayout()
        self.shared_key_input = QLineEdit()
        self.shared_key_input.setPlaceholderText("key")
        form_row.addWidget(self.shared_key_input)
        self.shared_type_input = QComboBox()
        self.shared_type_input.addItems(["string", "list"])
        form_row.addWidget(self.shared_type_input)
        layout.addLayout(form_row)

        self.shared_value_input = QTextEdit()
        self.shared_value_input.setPlaceholderText("value (for list: one item per line)")
        self.shared_value_input.setFixedHeight(120)
        layout.addWidget(self.shared_value_input)

        buttons_row = QHBoxLayout()
        btn_add_shared = QPushButton("Add/Update")
        btn_add_shared.setProperty("class", "primary")
        btn_add_shared.clicked.connect(self._add_or_update_shared_var)
        btn_delete_shared = QPushButton("Delete")
        btn_delete_shared.clicked.connect(self._delete_shared_var)
        buttons_row.addWidget(btn_add_shared)
        buttons_row.addWidget(btn_delete_shared)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(dlg.reject)
        close_box.accepted.connect(dlg.accept)
        layout.addWidget(close_box)

        self._refresh_shared_vars_list()
        dlg.exec()
        self._clear_shared_dialog_refs()

    def _load_shared_vars(self) -> None:
        import json

        raw = db_get_setting("shared_variables") or "{}"
        try:
            self.shared_variables = json.loads(raw)
        except Exception:
            self.shared_variables = {}
        self._refresh_shared_vars_list()

    def _save_shared_vars(self) -> None:
        import json

        db_set_setting("shared_variables", json.dumps(self.shared_variables, ensure_ascii=False))
        self._refresh_shared_vars_list()

    def _load_stages(self) -> None:
        import json

        raw = db_get_setting("stages_json") or "[]"
        try:
            self.stages = list(json.loads(raw))
        except Exception:
            self.stages = []
        self._refresh_stages()

    def _save_stages(self) -> None:
        import json

        db_set_setting("stages_json", json.dumps(self.stages, ensure_ascii=False))
        self._refresh_stages()

    def _refresh_stages(self) -> None:
        if hasattr(self, "stages_list"):
            self.stages_list.clear()
            for st in sorted(self.stages):
                self.stages_list.addItem(st)
        if hasattr(self, "run_stage_combo"):
            self.run_stage_combo.clear()
            self.run_stage_combo.addItem("")
            for st in sorted(self.stages):
                self.run_stage_combo.addItem(st)
        self._rebuild_stage_filter_chips()
        if hasattr(self, "_refresh_delete_tag_combo"):
            self._refresh_delete_tag_combo()

    def _rebuild_stage_filter_chips(self) -> None:
        layout = getattr(self, "stage_filter_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.stages:
            placeholder = QLabel("Add tags to group accounts faster.")
            placeholder.setProperty("class", "muted")
            layout.addWidget(placeholder)
            layout.addStretch()
            return
        clear_btn = QPushButton("All tags")
        clear_btn.setCheckable(True)
        clear_btn.setProperty("class", "tagChip")
        clear_btn.setChecked(self._active_stage_filter is None)
        clear_btn.clicked.connect(lambda _: self._set_stage_filter(None))
        layout.addWidget(clear_btn)
        for stage in sorted(self.stages):
            btn = QPushButton(stage)
            btn.setCheckable(True)
            btn.setProperty("class", "tagChip")
            btn.setChecked(self._active_stage_filter == stage)
            btn.clicked.connect(lambda _, value=stage: self._set_stage_filter(value))
            layout.addWidget(btn)
        layout.addStretch()

    def _set_stage_filter(self, stage: Optional[str]) -> None:
        self._active_stage_filter = stage or None
        self._rebuild_stage_filter_chips()
        self._apply_accounts_filter()
        if hasattr(self, "stage_accounts_list"):
            self.stage_accounts_list.clear()

    def _refresh_shared_vars_list(self) -> None:
        if not hasattr(self, "shared_vars_list"):
            return
        self.shared_vars_list.clear()
        for key, payload in sorted(self.shared_variables.items()):
            try:
                val = payload.get("value")
                typ = payload.get("type", "string")
            except AttributeError:
                val = payload
                typ = "string"
            display = ""
            if typ == "list" and isinstance(val, list):
                display = ", ".join(map(str, val))
            else:
                display = str(val)
            item = QListWidgetItem(f"[{typ}] {key}: {display}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.shared_vars_list.addItem(item)

    def _populate_shared_var_fields(self, key: str) -> None:
        data = self.shared_variables.get(key)
        typ = "string"
        val = ""
        if isinstance(data, dict):
            typ = str(data.get("type", "string") or "string")
            raw_val = data.get("value")
            if typ == "list":
                if isinstance(raw_val, list):
                    val = "\n".join(map(str, raw_val))
                elif isinstance(raw_val, str):
                    parts = [ln.strip() for ln in raw_val.splitlines() if ln.strip()]
                    val = "\n".join(parts)
                else:
                    val = "" if raw_val is None else str(raw_val)
            else:
                val = "" if raw_val is None else str(raw_val)
        elif data is not None:
            val = str(data)
        self.shared_key_input.setText(key)
        self.shared_type_input.setCurrentText(typ or "string")
        self.shared_value_input.setPlainText(val)

    def _on_shared_var_selected(self) -> None:
        row = self.shared_vars_list.currentRow()
        if row < 0:
            return
        item = self.shared_vars_list.item(row)
        if not item:
            return
        key_data = item.data(Qt.ItemDataRole.UserRole)
        text = item.text()
        # format: [type] key: value
        if text.startswith("[") and "]" in text:
            typ = text[1 : text.index("]")]
            rest = text[text.index("]") + 1 :].strip()
        else:
            typ = "string"
            rest = text
        if ": " in rest:
            key_part, val = rest.split(": ", 1)
        else:
            key_part, val = rest, ""
        if key_data not in (None, ""):
            key = str(key_data)
        else:
            key = key_part.rstrip(":").strip()
        self._populate_shared_var_fields(key)

    def _on_stage_selected(self) -> None:
        if not hasattr(self, "stage_accounts_list"):
            return
        row = self.stages_list.currentRow()
        if row < 0:
            self.stage_accounts_list.clear()
            return
        stage_name = self.stages_list.item(row).text()
        accounts = [acc for acc in db_get_accounts() if str(acc.get("stage") or "") == stage_name]
        self.stage_accounts_list.clear()
        for acc in accounts:
            self.stage_accounts_list.addItem(str(acc.get("name") or ""))

    def _add_or_update_shared_var(self) -> None:
        key = self.shared_key_input.text().strip()
        typ = self.shared_type_input.currentText().strip() or "string"
        raw = self.shared_value_input.toPlainText()
        if typ == "list":
            val: object = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        else:
            val = raw.strip()
        if not key:
            QMessageBox.warning(self, "Error", "Key is required for shared variable")
            return
        self.shared_variables[key] = {"type": typ, "value": val}
        self._save_shared_vars()
        for idx in range(self.shared_vars_list.count()):
            item = self.shared_vars_list.item(idx)
            if item and item.data(Qt.ItemDataRole.UserRole) == key:
                self.shared_vars_list.setCurrentRow(idx)
                break
        self._populate_shared_var_fields(key)

    def _delete_shared_var(self) -> None:
        key = self.shared_key_input.text().strip()
        if not key:
            return
        if key in self.shared_variables:
            self.shared_variables.pop(key, None)
            self._save_shared_vars()

    def _add_stage(self) -> None:
        name, ok = QInputDialog.getText(self, "Add tag", "Tag name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in self.stages:
            QMessageBox.warning(self, "Error", "Tag already exists")
            return
        self.stages.append(name)
        self._save_stages()

    def _delete_stage(self) -> None:
        items = getattr(self, "stages_list", None)
        if items and items.currentItem():
            name = items.currentItem().text()
        else:
            name, ok = QInputDialog.getText(self, "Delete tag", "Tag name to delete:")
            if not ok:
                return
            name = name.strip()
        if not name:
            return
        # remove stage from accounts
        for acc in db_get_accounts():
            if (acc.get("stage") or "") == name:
                db_update_stage(str(acc.get("name") or ""), None)
        self.stages = [st for st in self.stages if st != name]
        self._save_stages()

    def _open_stage_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage tags")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        info = QLabel("Tags allow you to group profiles and run scenarios for a cohort.")
        info.setWordWrap(True)
        layout.addWidget(info)

        stage_list = QListWidget()
        stage_list.addItems(sorted(self.stages))
        layout.addWidget(stage_list)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add tag")
        delete_btn = QPushButton("Delete selected")
        buttons.addWidget(add_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(dlg.reject)
        close_box.accepted.connect(dlg.accept)
        layout.addWidget(close_box)

        def refresh_list():
            stage_list.clear()
            for st in sorted(self.stages):
                stage_list.addItem(st)

        def add_stage_dialog():
            name, ok = QInputDialog.getText(dlg, "Add tag", "Tag name:")
            if not ok:
                return
            name = name.strip()
            if not name:
                return
            if name in self.stages:
                QMessageBox.warning(dlg, "Error", "Tag already exists")
                return
            self.stages.append(name)
            self._save_stages()
            refresh_list()

        def delete_stage_dialog():
            item = stage_list.currentItem()
            if not item:
                return
            name = item.text()
            for acc in db_get_accounts():
                if (acc.get("stage") or "") == name:
                    db_update_stage(str(acc.get("name") or ""), None)
            self.stages = [st for st in self.stages if st != name]
            self._save_stages()
            refresh_list()

        add_btn.clicked.connect(add_stage_dialog)
        delete_btn.clicked.connect(delete_stage_dialog)

        dlg.exec()
