"""Scenario editing and mapping helpers."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from app.storage.db import db_delete_scenario, db_get_scenario, db_get_scenarios, db_save_scenario
from app.ui.tabs.scenarios import ACTION_LABELS, ACTION_OPTIONS_DIALOG

_ACTION_CATEGORY_PRESETS = [
    ("Navigation & interaction", ["goto", "wait_for_load_state", "wait_element", "sleep", "click", "type"]),
    ("Variables", ["set_var", "parse_var", "pop_shared", "extract_text", "write_file"]),
    ("Network", ["http_request"]),
    ("Browser tabs", ["new_tab", "switch_tab", "close_tab"]),
    ("Flow & logging", ["start", "end", "run_scenario", "log", "set_tag", "compare"]),
]
ACTION_CATEGORIES: List[Tuple[str, List[str]]] = [(name, list(actions)) for name, actions in _ACTION_CATEGORY_PRESETS]
ACTION_CATEGORY_MAP = {name: actions for name, actions in ACTION_CATEGORIES}
_ALL_ACTION_VALUES = [value for _, value in ACTION_OPTIONS_DIALOG]
_assigned = {action for actions in ACTION_CATEGORY_MAP.values() for action in actions}
_missing = [value for value in _ALL_ACTION_VALUES if value not in _assigned]
if _missing:
    ACTION_CATEGORIES.append(("Other", _missing))
    ACTION_CATEGORY_MAP["Other"] = _missing

def _category_for_action(action: str) -> str:
    for name, actions in ACTION_CATEGORIES:
        if action in actions:
            return name
    return ACTION_CATEGORIES[0][0]


class ScenarioEditorMixin:
    def _suggest_copy_name(self, base_name: str) -> str:
        base_name = str(base_name or "").strip() or "Scenario"
        existing = {sc.name for sc in getattr(self, "scenarios_cache", []) or []}
        candidate = f"{base_name} (copy)"
        if candidate not in existing:
            return candidate
        for i in range(2, 1000):
            candidate_i = f"{base_name} (copy {i})"
            if candidate_i not in existing:
                return candidate_i
        return f"{base_name} (copy {int(len(existing) + 1)})"

    @staticmethod
    def _deepcopy_steps(steps: object) -> List[Dict]:
        if not isinstance(steps, list):
            return []
        try:
            return json.loads(json.dumps(steps, ensure_ascii=False))
        except Exception:
            out: List[Dict] = []
            for item in steps:
                out.append(dict(item) if isinstance(item, dict) else {})
            return out

    @staticmethod
    def _parse_kv_lines(raw: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                key, value = line.split(":", 1)
            elif "=" in line:
                key, value = line.split("=", 1)
            else:
                continue
            key = key.strip()
            if not key:
                continue
            out[key] = value.strip()
        return out

    @staticmethod
    def _format_kv_lines(data: object, sep: str = ": ") -> str:
        if not isinstance(data, dict) or not data:
            return ""
        lines: List[str] = []
        for key in sorted(data.keys(), key=lambda k: str(k).lower()):
            val = data.get(key)
            lines.append(f"{key}{sep}{'' if val is None else val}")
        return "\n".join(lines)

    @staticmethod
    def _frame_selector_to_text(value: object) -> str:
        if isinstance(value, list):
            parts = [str(v).strip() for v in value if str(v).strip()]
            return " >> ".join(parts)
        return "" if value is None else str(value)

    @staticmethod
    def _frame_selector_from_text(raw: str) -> object:
        text = str(raw or "").strip()
        if not text:
            return ""
        if ">>" in text:
            parts = [p.strip() for p in text.split(">>") if p.strip()]
            if len(parts) > 1:
                return parts
            return parts[0] if parts else ""
        return text

    @staticmethod
    def _parse_extract_lines(raw: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            elif ":" in line:
                key, value = line.split(":", 1)
            else:
                continue
            key = key.strip()
            if not key:
                continue
            out[key] = value.strip()
        return out

    @staticmethod
    def _try_parse_json_object(raw: object) -> Dict[str, object]:
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception:
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    def _reload_scenarios(self) -> None:
        self.scenarios_cache = db_get_scenarios()
        self.scenario_list_widget.clear()
        if hasattr(self, "scenario_run_combo"):
            self.scenario_run_combo.clear()
        for scenario in self.scenarios_cache:
            self.scenario_list_widget.addItem(scenario.name)
            if hasattr(self, "scenario_run_combo"):
                self.scenario_run_combo.addItem(scenario.name)
        if self.scenarios_cache:
            self.scenario_list_widget.setCurrentRow(0)
        else:
            self.current_steps = [{"action": "start", "tag": "Start"}]
            self.selected_scenario = None
            self.steps_list.clear()

    def _on_scenario_selected(self) -> None:
        items = self.scenario_list_widget.selectedItems()
        if not items:
            return
        name = items[0].text()
        scenario = db_get_scenario(name)
        if scenario is None:
            QMessageBox.warning(self, "Error", f"Scenario {name} not found")
            return
        self.selected_scenario = scenario
        self._tag_counter = 0
        self.scenario_name_input.setText(name)
        self.scenario_description_input.setText(scenario.description or "")
        self.current_steps = list(scenario.steps or [])
        self._normalize_steps()
        self._ensure_start_step()
        self._ensure_step_tags()
        self._refresh_steps_view()
        if hasattr(self, "map_view"):
            if getattr(self, "_map_focus_on_load", True):
                self.map_view.focus_on_start()
            self._map_focus_on_load = True
        self._update_form_visibility(self._current_action_value())

    def _new_scenario(self) -> None:
        new_name, ok = QInputDialog.getText(self, "New scenario", "Scenario name:", text=self._peek_next_tag())
        if not ok or not new_name.strip():
            return
        self.scenario_name_input.setText(new_name.strip())
        self.selected_scenario = None
        self.scenario_description_input.clear()
        self.current_steps = [{"action": "start", "tag": "Start"}]
        self._tag_counter = 0
        self._refresh_steps_view()
        self._clear_step_form()
        self._update_form_visibility(self._current_action_value())

    def _show_scenario_context_menu(self, pos) -> None:
        item = self.scenario_list_widget.itemAt(pos)
        if not item:
            return
        self.scenario_list_widget.setCurrentItem(item)
        menu = QMenu(self)
        act_edit = menu.addAction("Edit name")
        act_duplicate = menu.addAction("Duplicate")
        chosen = menu.exec(self.scenario_list_widget.mapToGlobal(pos))
        if chosen == act_edit:
            self._rename_selected_scenario()
        if chosen == act_duplicate:
            self._duplicate_selected_scenario()

    def _rename_selected_scenario(self) -> None:
        items = self.scenario_list_widget.selectedItems()
        if not items:
            return
        old_name = items[0].text()
        new_name, ok = QInputDialog.getText(self, "Rename scenario", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        existing = {sc.name for sc in self.scenarios_cache}
        if new_name in existing:
            QMessageBox.warning(self, "Error", f"Scenario {new_name} already exists")
            return
        scenario = db_get_scenario(old_name)
        if scenario is None:
            QMessageBox.warning(self, "Error", f"Scenario {old_name} not found")
            return
        db_save_scenario(new_name, scenario.steps or [], description=scenario.description)
        db_delete_scenario(old_name)
        self._reload_scenarios()
        matches = self.scenario_list_widget.findItems(new_name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.scenario_list_widget.setCurrentItem(matches[0])
        self.log(f"Renamed scenario {old_name} -> {new_name}")

    def _duplicate_selected_scenario(self) -> None:
        items = self.scenario_list_widget.selectedItems()
        if not items:
            return
        source_name = items[0].text()
        source_name = str(source_name or "").strip()
        if not source_name:
            return

        use_current = str(self.scenario_name_input.text() or "").strip() == source_name
        if use_current:
            try:
                self._sync_positions_from_map()
                self._normalize_steps()
            except Exception:
                pass
            steps = self._deepcopy_steps(self.current_steps)
            description = self.scenario_description_input.text().strip() or None
        else:
            scenario = db_get_scenario(source_name)
            if scenario is None:
                QMessageBox.warning(self, "Error", f"Scenario {source_name} not found")
                return
            steps = self._deepcopy_steps(scenario.steps or [])
            description = scenario.description

        suggested = self._suggest_copy_name(source_name)
        new_name, ok = QInputDialog.getText(self, "Duplicate scenario", "New name:", text=suggested)
        if not ok or not str(new_name or "").strip():
            return
        new_name = str(new_name or "").strip()

        existing = {sc.name for sc in getattr(self, "scenarios_cache", []) or []}
        if new_name in existing:
            QMessageBox.warning(self, "Error", f"Scenario {new_name} already exists")
            return

        db_save_scenario(new_name, steps, description=description)
        self._reload_scenarios()
        matches = self.scenario_list_widget.findItems(new_name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.scenario_list_widget.setCurrentItem(matches[0])
        self.log(f"Duplicated scenario {source_name} -> {new_name}")

    def _delete_selected_scenario(self) -> None:
        items = self.scenario_list_widget.selectedItems()
        if not items:
            return
        name = items[0].text()
        confirm = QMessageBox.question(
            self,
            "Confirm",
            f"Delete scenario {name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        db_delete_scenario(name)
        self._reload_scenarios()
        self._new_scenario()
        self.log(f"Scenario {name} deleted")

    def _fill_step_form_from_selection(self) -> None:
        row = self.steps_list.currentRow()
        if row < 0 or row >= len(self.current_steps):
            return
        self.map_view.set_selected(row)
        step = self.current_steps[row] or {}
        self.step_tag_input.setText(step.get("tag", ""))
        self._select_action_value(step.get("action", "goto"))
        self.step_selector_input.setText(step.get("selector", ""))
        self.step_selector_type_input.setCurrentText(step.get("selector_type", "css"))
        self.step_selector_index.setValue(int(step.get("selector_index", 0) or 0))
        targets = step.get("targets") or []
        targets_str = step.get("pattern") or step.get("targets_string")
        if targets_str:
            self.step_targets_input.setText(str(targets_str))
        elif isinstance(targets, list) and targets:
            self.step_targets_input.setText(" | ".join(map(str, targets)))
        else:
            self.step_targets_input.clear()
        self.step_frame_input.setText(self._frame_selector_to_text(step.get("frame_selector", "")))
        self.step_value_input.setText(
            step.get("value")
            or step.get("url")
            or step.get("text")
            or step.get("message")
            or ""
        )

        http_merged: Dict[str, object] = {}
        http_merged.update(self._try_parse_json_object(step.get("options") or {}))
        http_merged.update(self._try_parse_json_object(step.get("options_json") or ""))
        http_merged.update({k: v for k, v in step.items() if v is not None})

        method = str(http_merged.get("method") or "GET").upper()
        self.step_http_method_combo.setCurrentText(method if method else "GET")
        self.step_http_headers_input.setPlainText(self._format_kv_lines(http_merged.get("headers")))
        self.step_http_params_input.setPlainText(self._format_kv_lines(http_merged.get("params"), sep="="))

        body_val = http_merged.get("data")
        if body_val is None:
            body_val = http_merged.get("json")
        if body_val is None:
            body_val = http_merged.get("body")
        if isinstance(body_val, (dict, list)):
            try:
                self.step_http_body_input.setPlainText(json.dumps(body_val, ensure_ascii=False, indent=2))
                self.step_http_body_is_json.setChecked(True)
            except Exception:
                self.step_http_body_input.setPlainText("")
                self.step_http_body_is_json.setChecked(False)
        else:
            self.step_http_body_input.setPlainText("" if body_val is None else str(body_val))
            self.step_http_body_is_json.setChecked(False)

        self.step_http_save_as_input.setText(str(http_merged.get("save_as") or ""))
        self.step_http_response_var_input.setText(str(http_merged.get("response_var") or http_merged.get("to_var") or ""))
        self.step_http_extract_input.setPlainText(self._format_kv_lines(http_merged.get("extract_json"), sep="="))
        self.step_http_require_success.setChecked(bool(http_merged.get("require_success")))
        self.step_http_fail_on_status_code.setChecked(bool(http_merged.get("fail_on_status_code")))
        self.step_http_ignore_https_errors.setChecked(bool(http_merged.get("ignore_https_errors")))
        try:
            self.step_http_max_redirects.setValue(int(http_merged.get("max_redirects") or 0))
        except Exception:
            self.step_http_max_redirects.setValue(0)
        try:
            self.step_http_max_retries.setValue(int(http_merged.get("max_retries") or 0))
        except Exception:
            self.step_http_max_retries.setValue(0)

        self.step_variable_input.setText(step.get("to_var") or step.get("variable") or step.get("name") or "")
        self.step_attribute_input.setText(step.get("attribute", ""))
        self.step_state_input.setCurrentText(step.get("state", ""))
        self.step_timeout_input.setValue(int(step.get("timeout_ms", 0) or 0))
        self.step_sleep_input.setValue(float(step.get("seconds", 0) or 0))
        self.step_tab_index.setValue(int(step.get("tab_index", step.get("index", 0) or 0)))

        self.step_compare_op_input.setCurrentText(str(step.get("op") or step.get("operator") or "equals"))
        self.step_compare_right_var_input.setText(str(step.get("right_var") or ""))
        self.step_compare_result_var_input.setText(str(step.get("result_var") or step.get("to_var") or ""))
        self.step_compare_case_sensitive.setChecked(bool(step.get("case_sensitive", False)))
        update_account_raw = step.get("update_account")
        self.step_parse_update_account.setChecked(True if update_account_raw is None else bool(update_account_raw))

    def _peek_next_tag(self) -> str:
        return f"Step{self._tag_counter + 1}"

    def _next_tag(self) -> str:
        self._tag_counter += 1
        return f"Step{self._tag_counter}"

    def _tag_taken(self, tag: str, ignore_index: Optional[int] = None) -> bool:
        for idx, step in enumerate(self.current_steps):
            if ignore_index is not None and idx == ignore_index:
                continue
            if str(step.get("tag") or "") == tag:
                return True
        return False

    def _ensure_step_tags(self) -> None:
        existing = set()
        next_id = self._tag_counter
        rename_map: Dict[str, str] = {}
        for step in self.current_steps:
            raw = str(step.get("tag") or "").strip()
            tag = raw
            if tag and tag in existing:
                tag = ""
            if not tag:
                next_id += 1
                tag = f"Step{next_id}"
            if raw and raw != tag:
                rename_map[raw] = tag
            existing.add(tag)
            step["tag"] = tag
            if tag.startswith("Step"):
                try:
                    num = int(tag[4:])
                    next_id = max(next_id, num)
                except Exception:
                    pass
        self._tag_counter = max(self._tag_counter, next_id)

        if rename_map:
            for step in self.current_steps:
                if step.get("next_success_step") in rename_map:
                    step["next_success_step"] = rename_map[step["next_success_step"]]
                if step.get("next_error_step") in rename_map:
                    step["next_error_step"] = rename_map[step["next_error_step"]]

    def _normalize_steps(self) -> None:
        for step in self.current_steps:
            if not isinstance(step, dict):
                continue
            step.pop("on_error", None)
            step.pop("on_error_target", None)
            step.pop("jump_to", None)
            action_raw = str(step.get("action") or "")
            action = action_raw.lower()
            if action == "set_stage":
                step["action"] = "set_tag"
                action = "set_tag"
            if step.get("selector"):
                sel_type = str(step.get("selector_type") or "css").lower()
                step["selector_type"] = sel_type
            if not step.get("value"):
                for legacy_key in ("url", "text", "message"):
                    if step.get(legacy_key):
                        step["value"] = step.get(legacy_key)
                        break

    def _ensure_start_step(self) -> None:
        if self.current_steps and (self.current_steps[0].get("action") == "start"):
            start_step = self.current_steps[0]
        else:
            start_step = {"action": "start", "tag": "Start"}
            if self.current_steps:
                first_tag = self.current_steps[0].get("tag") or ""
                if not first_tag:
                    self._ensure_step_tags()
                    first_tag = self.current_steps[0].get("tag") or ""
                if first_tag:
                    start_step["next_success_step"] = first_tag
            self.current_steps = [start_step] + list(self.current_steps)
        start_step["tag"] = start_step.get("tag") or "Start"
        start_step.pop("next_error_step", None)
        if len(self.current_steps) > 1:
            first_tag = self.current_steps[1].get("tag")
            if first_tag and not start_step.get("next_success_step"):
                start_step["next_success_step"] = first_tag
        else:
            start_step.pop("next_success_step", None)

    def _replace_tag_references(self, old_tag: str, new_tag: str) -> None:
        if not old_tag or not new_tag or old_tag == new_tag:
            return
        for step in self.current_steps:
            if step.get("next_success_step") == old_tag:
                step["next_success_step"] = new_tag
            if step.get("next_error_step") == old_tag:
                step["next_error_step"] = new_tag

    def _refresh_steps_view(self) -> None:
        self._normalize_steps()
        self._ensure_start_step()
        self._ensure_step_tags()
        self.steps_list.clear()
        for idx, step in enumerate(self.current_steps):
            self.steps_list.addItem(self._step_display_text(idx, step))
        self.map_view.set_steps(self.current_steps)
        # keep selection in sync
        current = self.steps_list.currentRow()
        if current >= 0:
            self.map_view.set_selected(current)
        self._refresh_vars_list()

    def _clear_step_form(self) -> None:
        self.step_selector_input.clear()
        self.step_selector_type_input.setCurrentText("css")
        self.step_frame_input.clear()
        self.step_value_input.clear()
        self.step_http_method_combo.setCurrentText("GET")
        self.step_http_headers_input.clear()
        self.step_http_params_input.clear()
        self.step_http_body_input.clear()
        self.step_http_body_is_json.setChecked(False)
        self.step_http_save_as_input.clear()
        self.step_http_response_var_input.clear()
        self.step_http_extract_input.clear()
        self.step_http_require_success.setChecked(False)
        self.step_http_fail_on_status_code.setChecked(False)
        self.step_http_ignore_https_errors.setChecked(False)
        self.step_http_max_redirects.setValue(0)
        self.step_http_max_retries.setValue(0)
        self.step_variable_input.clear()
        self.step_attribute_input.clear()
        self.step_targets_input.clear()
        self.step_state_input.setCurrentIndex(0)
        self.step_timeout_input.setValue(60000)
        self.step_sleep_input.setValue(0)
        self.step_tab_index.setValue(0)
        self.step_selector_index.setValue(0)
        self.step_compare_op_input.setCurrentText("equals")
        self.step_compare_right_var_input.clear()
        self.step_compare_result_var_input.clear()
        self.step_compare_case_sensitive.setChecked(False)
        self.step_parse_update_account.setChecked(True)
        self.step_tag_input.setText(self._peek_next_tag())
        self._update_form_visibility(self._current_action_value())

    def _collect_step_from_form(self, existing_index: Optional[int] = None) -> Dict:
        action = self._current_action_value()
        step: Dict[str, object] = {"action": action}
        existing_next_ok = None
        existing_next_err = None
        old_tag = None
        if existing_index is not None and 0 <= existing_index < len(self.current_steps):
            prev = self.current_steps[existing_index]
            existing_next_ok = prev.get("next_success_step")
            existing_next_err = prev.get("next_error_step")
            old_tag = prev.get("tag")
        label = self.step_label_input.text().strip()
        tag = self.step_tag_input.text().strip()
        if not tag or self._tag_taken(tag, ignore_index=existing_index):
            tag = old_tag or self._next_tag()
        step["tag"] = tag

        selector = self.step_selector_input.text().strip()
        selector_type = self.step_selector_type_input.currentText().strip() or "css"
        selector_index = self.step_selector_index.value()
        targets_raw = self.step_targets_input.text().strip()
        frame_raw = self.step_frame_input.text().strip()
        frame = self._frame_selector_from_text(frame_raw)
        value = self.step_value_input.text().strip()
        variable = self.step_variable_input.text().strip()
        attribute = self.step_attribute_input.text().strip()
        compare_op = self.step_compare_op_input.currentText().strip()
        compare_right_var = self.step_compare_right_var_input.text().strip()
        compare_result_var = self.step_compare_result_var_input.text().strip()
        compare_case_sensitive = bool(self.step_compare_case_sensitive.isChecked())
        parse_update_account = bool(self.step_parse_update_account.isChecked())
        state = self.step_state_input.currentText().strip()
        timeout = self.step_timeout_input.value()
        seconds = self.step_sleep_input.value()
        tab_index = self.step_tab_index.value()
        selector_index = self.step_selector_index.value()

        if selector:
            step["selector"] = selector
            step["selector_type"] = selector_type
            if selector_index:
                step["selector_index"] = selector_index
            if selector_index:
                step["selector_index"] = selector_index
        if frame:
            step["frame_selector"] = frame
        if state:
            step["state"] = state
        if timeout:
            step["timeout_ms"] = timeout
        if seconds:
            step["seconds"] = seconds
        if tab_index:
            step["tab_index"] = tab_index
        if attribute:
            step["attribute"] = attribute
        if targets_raw:
            if action in {"pop_shared", "parse_var"}:
                step["pattern"] = targets_raw
                step["targets_string"] = targets_raw  # backward compatibility
        if value:
            step["value"] = value
        if action == "http_request":
            method = self.step_http_method_combo.currentText().strip() or "GET"
            step["method"] = method.upper()
            headers = self._parse_kv_lines(self.step_http_headers_input.toPlainText())
            if headers:
                step["headers"] = headers
            params = self._parse_kv_lines(self.step_http_params_input.toPlainText())
            if params:
                step["params"] = params
            body_raw = self.step_http_body_input.toPlainText().strip()
            if body_raw:
                if self.step_http_body_is_json.isChecked():
                    try:
                        step["data"] = json.loads(body_raw)
                    except Exception:
                        step["data"] = body_raw
                else:
                    step["data"] = body_raw
            save_as = self.step_http_save_as_input.text().strip()
            if save_as:
                step["save_as"] = save_as
            response_var = self.step_http_response_var_input.text().strip()
            if response_var:
                step["response_var"] = response_var
            extract_map = self._parse_extract_lines(self.step_http_extract_input.toPlainText())
            if extract_map:
                step["extract_json"] = extract_map
            if self.step_http_require_success.isChecked():
                step["require_success"] = True
            if self.step_http_fail_on_status_code.isChecked():
                step["fail_on_status_code"] = True
            if self.step_http_ignore_https_errors.isChecked():
                step["ignore_https_errors"] = True
            max_redirects = int(self.step_http_max_redirects.value() or 0)
            if max_redirects:
                step["max_redirects"] = max_redirects
            max_retries = int(self.step_http_max_retries.value() or 0)
            if max_retries:
                step["max_retries"] = max_retries
        if action == "parse_var" and variable:
            step["from_var"] = variable
            if not parse_update_account:
                step["update_account"] = False
        if action == "compare":
            if variable:
                step["left_var"] = variable
            if compare_right_var:
                step["right_var"] = compare_right_var
            if compare_op:
                step["op"] = compare_op
            if compare_result_var:
                step["result_var"] = compare_result_var
            if compare_case_sensitive:
                step["case_sensitive"] = True
        if action == "type":
            step.setdefault("clear", True)
        if action == "set_var" and variable:
            step["name"] = variable
        if action == "extract_text" and variable:
            step["to_var"] = variable
        if action in ("wait_for_load_state",) and value:
            step["state"] = value

        if existing_next_ok:
            step["next_success_step"] = existing_next_ok
        if existing_next_err:
            step["next_error_step"] = existing_next_err

        return step

    def _add_step_from_form(self) -> None:
        step = self._collect_step_from_form()
        self.current_steps.append(step)
        new_idx = len(self.current_steps) - 1
        self._refresh_steps_view()
        self.steps_list.setCurrentRow(new_idx)
        if hasattr(self, "map_view"):
            self.map_view.set_selected(new_idx)
        self._clear_step_form()
        self._update_form_visibility(self._current_action_value())

    def _load_selected_scenario(self) -> None:
        items = self.scenario_list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "No selection", "Select a scenario to load.")
            return
        self._on_scenario_selected()

    def _insert_step(self, index: int, step: Dict) -> None:
        index = max(0, min(index, len(self.current_steps)))
        if self.current_steps and self.current_steps[0].get("action") == "start":
            index = max(1, index)
        if "tag" not in step or not step.get("tag"):
            step["tag"] = self._next_tag()
        self._sync_positions_from_map()
        self.current_steps.insert(index, step)
        self._refresh_steps_view()
        self.steps_list.setCurrentRow(index)
        self.map_view.set_selected(index)

    def _update_step_from_form(self) -> None:
        row = self.steps_list.currentRow()
        if row < 0 or row >= len(self.current_steps):
            return
        old_tag = self.current_steps[row].get("tag")
        old_pos = self.current_steps[row].get("_pos")
        new_step = self._collect_step_from_form(existing_index=row)
        new_tag = new_step.get("tag")
        if old_pos is not None:
            new_step["_pos"] = old_pos
        self.current_steps[row] = new_step
        if old_tag and new_tag and old_tag != new_tag:
            self._replace_tag_references(old_tag, new_tag)
        self._refresh_steps_view()
        self.steps_list.setCurrentRow(row)
        self._update_form_visibility(self._current_action_value())

    def _delete_step(self) -> None:
        row = self.steps_list.currentRow()
        if row < 0 or row >= len(self.current_steps):
            return
        if row == 0 and self.current_steps and self.current_steps[0].get("action") == "start":
            QMessageBox.information(self, "Info", "Start step cannot be deleted")
            return
        self._sync_positions_from_map()
        self.current_steps.pop(row)
        self._refresh_steps_view()

    def _delete_step_by_index(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.current_steps):
            return
        if idx == 0 and self.current_steps and self.current_steps[0].get("action") == "start":
            return
        self._sync_positions_from_map()
        self.current_steps.pop(idx)
        self._refresh_steps_view()
        if idx < self.steps_list.count():
            self.steps_list.setCurrentRow(idx)

    def _move_step(self, direction: int) -> None:
        row = self.steps_list.currentRow()
        self._move_step_by_index(row, direction)

    def _move_step_by_index(self, idx: int, direction: int) -> None:
        if idx < 0:
            return
        new_row = idx + direction
        if new_row < 0 or new_row >= len(self.current_steps):
            return
        self._sync_positions_from_map()
        self.current_steps[idx], self.current_steps[new_row] = self.current_steps[new_row], self.current_steps[idx]
        self._refresh_steps_view()
        self.steps_list.setCurrentRow(new_row)
        self.map_view.set_selected(new_row)

    def _sync_positions_from_map(self) -> None:
        """
        Persist current visual node positions into steps (_pos) so deletion/reordering keeps layout.
        """
        if not hasattr(self, "map_view") or not getattr(self.map_view, "_last_positions", None):
            return
        positions = getattr(self.map_view, "_last_positions", {}) or {}
        try:
            ox = float(self.map_view.offset.x())
            oy = float(self.map_view.offset.y())
        except Exception:
            ox = oy = 0.0
        for idx, step in enumerate(self.current_steps):
            if idx not in positions:
                continue
            try:
                x, y, w, h = positions[idx]
                step["_pos"] = {"x": float(x - ox), "y": float(y - oy)}
            except Exception:
                continue

    def _step_display_text(self, idx: int, step: Dict) -> str:
        parts = [f"{idx + 1}. [{step.get('tag', '')}] {self._action_display_name(step.get('action'))}"]
        if step.get("selector"):
            sel_type = step.get("selector_type")
            prefix = f"sel[{sel_type}]" if sel_type else "sel"
            parts.append(f"{prefix}: {step['selector']}")
        if str(step.get("action") or "").lower() == "http_request":
            if step.get("method"):
                parts.append(f"method: {step.get('method')}")
            if step.get("save_as"):
                parts.append(f"as: {step.get('save_as')}")
        if step.get("value"):
            parts.append(f"val: {step['value']}")
        if step.get("frame_selector"):
            parts.append("iframe")
        if step.get("jump_if_missing") or step.get("jump_if_found"):
            parts.append("branch")
        return " | ".join(parts)

    def _apply_block_template(self, action: str) -> None:
        """
        Prefill form fields with sensible defaults for the chosen block to speed up visual programming.
        """
        self._clear_step_form()
        self._select_action_value(action)
        self.step_selector_type_input.setCurrentText("css")
        if action == "goto":
            self.step_value_input.setText("https://example.com")
            self.step_state_input.setCurrentText("load")
        elif action == "http_request":
            self.step_value_input.setText("https://example.com")
            self.step_http_method_combo.setCurrentText("GET")
            self.step_http_headers_input.setPlainText("Accept: application/json")
            self.step_http_params_input.clear()
            self.step_http_body_input.clear()
            self.step_http_body_is_json.setChecked(False)
            self.step_http_save_as_input.setText("http")
            self.step_http_response_var_input.clear()
            self.step_http_extract_input.clear()
            self.step_http_require_success.setChecked(False)
            self.step_http_fail_on_status_code.setChecked(False)
            self.step_http_ignore_https_errors.setChecked(False)
            self.step_http_max_redirects.setValue(0)
            self.step_http_max_retries.setValue(0)
            self.step_timeout_input.setValue(30000)
        elif action == "wait_element":
            self.step_selector_input.setText("css=body")
            self.step_timeout_input.setValue(10000)
            self.step_state_input.setCurrentText("visible")
        elif action == "wait_for_load_state":
            self.step_state_input.setCurrentText("networkidle")
            self.step_timeout_input.setValue(60000)
        elif action == "click":
            self.step_selector_input.setText("css=button")
        elif action == "type":
            self.step_selector_input.setText("input")
            self.step_value_input.setText("text goes here")
        elif action == "sleep":
            self.step_sleep_input.setValue(1.0)
        elif action == "extract_text":
            self.step_selector_input.setText("css=.title")
            self.step_variable_input.setText("title")
        elif action == "set_var":
            self.step_variable_input.setText("my_var")
            self.step_value_input.setText("value")
        elif action == "parse_var":
            self.step_variable_input.setText("source_var")
            self.step_targets_input.setText("{{a}};{{b}}")
        elif action == "compare":
            self.step_variable_input.setText("var")
            self.step_value_input.setText("value")
            self.step_compare_op_input.setCurrentText("equals")
        elif action == "pop_shared":
            self.step_value_input.setText("shared_key")
            self.step_targets_input.setText("{{value1}}|{{value2}}")
        elif action == "new_tab":
            self.step_value_input.setText("https://example.com")
        elif action == "switch_tab":
            self.step_tab_index.setValue(1)
        elif action == "log":
            self.step_value_input.setText("Log message")
        # Do not auto-add; let user tweak then add explicitly.
        self._update_form_visibility(action)

    def _on_map_select(self, idx: int) -> None:
        if 0 <= idx < len(self.current_steps):
            self.steps_list.setCurrentRow(idx)

    def _on_map_add_after(self, idx: int, pos=None) -> None:
        step = self._show_step_dialog(base_action="goto" if idx < 0 else "log")
        if step:
            insert_at = idx + 1
            if pos is not None:
                try:
                    step["_pos"] = {"x": float(pos.x()), "y": float(pos.y())}
                except Exception:
                    pass
            self._insert_step(insert_at, step)

    def _on_map_move(self, idx: int, direction: int) -> None:
        self._move_step_by_index(idx, direction)

    def _on_map_delete(self, idx: int) -> None:
        self._delete_step_by_index(idx)

    def _on_map_add_detached(self, pos=None) -> None:
        step = self._show_step_dialog(base_action="log")
        if step:
            self._sync_positions_from_map()
            step["_no_default_links"] = True
            step["_ok_links"] = []
            step["_err_links"] = []
            if pos is not None:
                try:
                    step["_pos"] = {"x": float(pos.x()), "y": float(pos.y())}
                except Exception:
                    pass
            if self.current_steps:
                prev = self.current_steps[-1]
                if not prev.get("_no_default_links") and not prev.get("_ok_links") and not prev.get("_err_links"):
                    prev["_no_default_links"] = True
            self._insert_step(len(self.current_steps), step)

    def _on_map_edit(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.current_steps):
            return
        self._sync_positions_from_map()
        step_before = self.current_steps[idx]
        new_step = self._show_step_dialog(current_step=step_before)
        if new_step:
            old_tag = step_before.get("tag")
            new_tag = new_step.get("tag")
            if step_before.get("next_success_step") and not new_step.get("next_success_step"):
                new_step["next_success_step"] = step_before.get("next_success_step")
            if step_before.get("next_error_step") and not new_step.get("next_error_step"):
                new_step["next_error_step"] = step_before.get("next_error_step")
            # keep position if existed
            if "_pos" in step_before:
                new_step["_pos"] = step_before.get("_pos")
            self.current_steps[idx] = new_step
            if old_tag and new_tag and old_tag != new_tag:
                self._replace_tag_references(old_tag, new_tag)
            self._refresh_steps_view()

    def _on_map_drag_end(self, idx: int, pos) -> None:
        if 0 <= idx < len(self.current_steps):
            try:
                self.current_steps[idx]["_pos"] = {"x": float(pos.x()), "y": float(pos.y())}
            except Exception:
                pass

    def _show_step_dialog(self, base_action: str = "log", current_step: Optional[Dict] = None) -> Optional[Dict]:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add step")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        tag_input = QLineEdit()
        selected_action: Dict[str, str] = {"value": str(current_step.get("action") if current_step else base_action)}
        selected_category = _category_for_action(selected_action["value"])

        category_box = QFrame()
        category_layout = QGridLayout(category_box)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setHorizontalSpacing(10)
        category_layout.setVerticalSpacing(10)
        category_buttons: Dict[str, QPushButton] = {}

        def _set_category(name: str) -> None:
            nonlocal selected_category
            selected_category = name
            for key, btn in category_buttons.items():
                btn.setChecked(key == selected_category)
            _rebuild_action_buttons()

        for idx, (cat_name, _) in enumerate(ACTION_CATEGORIES):
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            btn.setProperty("class", "actionCategoryBtn")
            btn.clicked.connect(lambda _, name=cat_name: _set_category(name))
            category_layout.addWidget(btn, idx // 3, idx % 3)
            category_buttons[cat_name] = btn
        category_buttons.get(selected_category, next(iter(category_buttons.values()))).setChecked(True)

        action_box = QFrame()
        action_layout = QGridLayout(action_box)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(8)
        action_buttons: Dict[str, QPushButton] = {}

        selected_action_label = QLabel()
        selected_action_label.setProperty("class", "muted")

        def _set_action(value: str) -> None:
            selected_action["value"] = value
            for key, btn in action_buttons.items():
                btn.setChecked(key == value)
            label = ACTION_LABELS.get(value, value.replace("_", " ").title())
            selected_action_label.setText(f"Selected action: {label}")
            update_visibility(value)

        def _rebuild_action_buttons() -> None:
            while action_layout.count():
                item = action_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            action_buttons.clear()
            actions = ACTION_CATEGORY_MAP.get(selected_category, [])
            for idx, action_value in enumerate(actions):
                label = ACTION_LABELS.get(action_value, action_value.replace("_", " ").title())
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setProperty("class", "actionOptionBtn")
                btn.clicked.connect(lambda _, value=action_value: _set_action(value))
                action_layout.addWidget(btn, idx // 3, idx % 3)
                action_buttons[action_value] = btn
            current = selected_action["value"]
            if current not in action_buttons and actions:
                current = actions[0]
            _set_action(current)

        selector_input = QLineEdit()
        selector_type_input = QComboBox()
        selector_type_input.addItems(["css", "text", "xpath", "id", "name", "test_id"])
        selector_index_input = QSpinBox()
        selector_index_input.setRange(0, 50)
        frame_input = QLineEdit()
        value_input = QLineEdit()
        scenario_combo = QComboBox()
        # Non-editable so it clearly looks like a dropdown (shows the arrow).
        scenario_combo.setEditable(False)
        scenario_combo.setMinimumWidth(260)
        try:
            scenario_combo.setPlaceholderText("Select a scenario")
        except Exception:
            pass
        scenario_combo.addItem("Select a scenario...", "")
        try:
            for sc in db_get_scenarios():
                name = str(getattr(sc, "name", "") or "").strip()
                if name:
                    scenario_combo.addItem(name, name)
        except Exception:
            pass
        variable_input = QLineEdit()
        attribute_input = QLineEdit()
        targets_input = QLineEdit()
        compare_op_input = QComboBox()
        compare_op_input.addItems(
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
        compare_right_var_input = QLineEdit()
        compare_right_var_input.setPlaceholderText("right_var (optional)")
        compare_result_var_input = QLineEdit()
        compare_result_var_input.setPlaceholderText("result_var (optional)")
        compare_case_sensitive_input = QCheckBox("Case sensitive")
        parse_update_account_input = QCheckBox("Update account (save to profile)")
        parse_update_account_input.setChecked(True)
        state_input = QComboBox()
        state_input.addItems(["", "load", "domcontentloaded", "networkidle", "commit", "visible", "attached", "hidden"])
        timeout_input = QSpinBox()
        timeout_input.setRange(0, 600000)
        timeout_input.setValue(60000)
        sleep_input = QDoubleSpinBox()
        sleep_input.setDecimals(3)
        sleep_input.setRange(0, 300)
        tab_index_input = QSpinBox()
        tab_index_input.setRange(0, 20)
        jump_missing_input = QLineEdit()
        jump_found_input = QLineEdit()
        file_name_input = QLineEdit()
        file_name_input.setPlaceholderText("output.txt (saved to outputs/)")

        http_method_combo = QComboBox()
        http_method_combo.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        http_headers_input = QTextEdit()
        http_headers_input.setPlaceholderText("Authorization: Bearer {{token}}\nAccept: application/json")
        http_headers_input.setFixedHeight(70)
        http_params_input = QTextEdit()
        http_params_input.setPlaceholderText("q={{login}}\npage=1")
        http_params_input.setFixedHeight(60)
        http_body_input = QTextEdit()
        http_body_input.setPlaceholderText("Request body (text) or JSON")
        http_body_input.setFixedHeight(90)
        http_body_is_json = QCheckBox("Parse body as JSON")
        http_save_as_input = QLineEdit()
        http_save_as_input.setPlaceholderText("http (prefix for variables)")
        http_response_var_input = QLineEdit()
        http_response_var_input.setPlaceholderText("last_response (optional)")
        http_extract_input = QTextEdit()
        http_extract_input.setPlaceholderText("token=$.token\nuser_id=$.user.id")
        http_extract_input.setFixedHeight(70)
        http_require_success = QCheckBox("Stop if status is not 2xx")
        http_fail_on_status_code = QCheckBox("Fail on non-2xx (Playwright)")
        http_ignore_https_errors = QCheckBox("Ignore HTTPS errors")
        http_max_redirects = QSpinBox()
        http_max_redirects.setRange(0, 50)
        http_max_retries = QSpinBox()
        http_max_retries.setRange(0, 20)

        rows = {
            "selector": (QLabel("Selector:"), selector_input),
            "selector_type": (QLabel("Selector type:"), selector_type_input),
            "selector_index": (QLabel("Selector index (nth):"), selector_index_input),
            "frame": (QLabel("Iframe selector:"), frame_input),
            "value": (QLabel("Value:"), value_input),
            "scenario": (QLabel("Scenario:"), scenario_combo),
            "http_method": (QLabel("HTTP method:"), http_method_combo),
            "http_headers": (QLabel("HTTP headers:"), http_headers_input),
            "http_params": (QLabel("Query params:"), http_params_input),
            "http_body": (QLabel("Body:"), http_body_input),
            "http_body_is_json": (QLabel(""), http_body_is_json),
            "http_save_as": (QLabel("Save as:"), http_save_as_input),
            "http_response_var": (QLabel("Response var:"), http_response_var_input),
            "http_extract": (QLabel("Extract JSON:"), http_extract_input),
            "http_require_success": (QLabel(""), http_require_success),
            "http_fail_on_status": (QLabel(""), http_fail_on_status_code),
            "http_ignore_https": (QLabel(""), http_ignore_https_errors),
            "http_max_redirects": (QLabel("Max redirects:"), http_max_redirects),
            "http_max_retries": (QLabel("Max retries:"), http_max_retries),
            "variable": (QLabel("Variable:"), variable_input),
            "attribute": (QLabel("Attribute:"), attribute_input),
            "targets": (QLabel("Targets / pattern:"), targets_input),
            "parse_update_account": (QLabel(""), parse_update_account_input),
            "compare_op": (QLabel("Compare operator:"), compare_op_input),
            "compare_right_var": (QLabel("Right variable:"), compare_right_var_input),
            "compare_result_var": (QLabel("Result variable:"), compare_result_var_input),
            "compare_case_sensitive": (QLabel(""), compare_case_sensitive_input),
            "state": (QLabel("State:"), state_input),
            "timeout": (QLabel("Timeout, ms:"), timeout_input),
            "sleep": (QLabel("Sleep, sec:"), sleep_input),
            "tab": (QLabel("Tab index:"), tab_index_input),
            "file_name": (QLabel("File name:"), file_name_input),
            "jump_m": (QLabel("Jump if missing:"), jump_missing_input),
            "jump_f": (QLabel("Jump if found:"), jump_found_input),
        }

        action_picker = QWidget(dlg)
        action_picker.setObjectName("actionPicker")
        action_picker_layout = QVBoxLayout(action_picker)
        action_picker_layout.setContentsMargins(0, 0, 0, 0)
        action_picker_layout.setSpacing(12)
        action_picker_layout.addWidget(category_box)
        divider = QFrame(action_picker)
        divider.setObjectName("actionPickerDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        action_picker_layout.addWidget(divider)
        action_picker_layout.addWidget(action_box)
        action_picker_layout.addWidget(selected_action_label)

        form.addRow("Tag:", tag_input)
        form.addRow("", action_picker)
        form.addRow(*rows["file_name"])
        form.addRow(*rows["selector"])
        form.addRow(*rows["selector_type"])
        form.addRow(*rows["selector_index"])
        form.addRow(*rows["frame"])
        form.addRow(*rows["value"])
        form.addRow(*rows["scenario"])
        form.addRow(*rows["http_method"])
        form.addRow(*rows["http_headers"])
        form.addRow(*rows["http_params"])
        form.addRow(*rows["http_body"])
        form.addRow(*rows["http_body_is_json"])
        form.addRow(*rows["http_save_as"])
        form.addRow(*rows["http_response_var"])
        form.addRow(*rows["http_extract"])
        form.addRow(*rows["http_require_success"])
        form.addRow(*rows["http_fail_on_status"])
        form.addRow(*rows["http_ignore_https"])
        form.addRow(*rows["http_max_redirects"])
        form.addRow(*rows["http_max_retries"])
        form.addRow(*rows["variable"])
        form.addRow(*rows["attribute"])
        form.addRow(*rows["targets"])
        form.addRow(*rows["parse_update_account"])
        form.addRow(*rows["compare_op"])
        form.addRow(*rows["compare_right_var"])
        form.addRow(*rows["compare_result_var"])
        form.addRow(*rows["compare_case_sensitive"])
        form.addRow(*rows["state"])
        form.addRow(*rows["timeout"])
        form.addRow(*rows["sleep"])
        form.addRow(*rows["tab"])
        # legacy jump fields removed from UI

        form_container = QWidget(dlg)
        form_container_layout = QVBoxLayout(form_container)
        form_container_layout.setContentsMargins(0, 0, 0, 0)
        form_container_layout.addLayout(form)

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_container)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                max_w = int(geo.width() * 0.95)
                max_h = int(geo.height() * 0.95)
                dlg.setMaximumSize(max_w, max_h)
                dlg.resize(min(980, max_w), min(820, max_h))
        except Exception:
            pass

        def update_visibility(act: str) -> None:
            act = act or ""
            selector_actions = {"click", "type", "wait_element", "extract_text"}
            show_selector = act in selector_actions
            show_frame = act in selector_actions
            show_scenario = act == "run_scenario"
            show_value = act in {"goto", "type", "set_var", "pop_shared", "new_tab", "log", "set_tag", "set_stage", "write_file", "http_request", "compare"}
            show_http = act == "http_request"
            show_variable = act in {"set_var", "extract_text", "parse_var", "compare"}
            show_attribute = act == "extract_text"
            show_targets = act in {"pop_shared", "parse_var"}
            show_parse_update_account = act == "parse_var"
            show_compare = act == "compare"
            show_state = act in {"wait_for_load_state"}
            show_timeout = act in selector_actions or act in {"wait_for_load_state", "goto", "new_tab", "http_request"}
            show_sleep = act == "sleep"
            show_tab = act in {"switch_tab", "close_tab"}
            show_file = act == "write_file"
            show_jump = False

            for key, visible in (
                ("file_name", show_file),
                ("selector", show_selector),
                ("selector_type", show_selector),
                ("selector_index", show_selector),
                ("frame", show_frame),
                ("value", show_value),
                ("scenario", show_scenario),
                ("http_method", show_http),
                ("http_headers", show_http),
                ("http_params", show_http),
                ("http_body", show_http),
                ("http_body_is_json", show_http),
                ("http_save_as", show_http),
                ("http_response_var", show_http),
                ("http_extract", show_http),
                ("http_require_success", show_http),
                ("http_fail_on_status", show_http),
                ("http_ignore_https", show_http),
                ("http_max_redirects", show_http),
                ("http_max_retries", show_http),
                ("variable", show_variable),
                ("attribute", show_attribute),
                ("targets", show_targets),
                ("parse_update_account", show_parse_update_account),
                ("compare_op", show_compare),
                ("compare_right_var", show_compare),
                ("compare_result_var", show_compare),
                ("compare_case_sensitive", show_compare),
                ("state", show_state),
                ("timeout", show_timeout),
                ("sleep", show_sleep),
                ("tab", show_tab),
                ("jump_m", show_jump),
                ("jump_f", show_jump),
            ):
                for w in rows[key]:
                    w.setVisible(visible)

        # prefill if editing
        if current_step:
            selector_input.setText(str(current_step.get("selector", "")))
            selector_type_input.setCurrentText(str(current_step.get("selector_type", "css")))
            selector_index_input.setValue(int(current_step.get("selector_index", 0) or 0))
            frame_input.setText(self._frame_selector_to_text(current_step.get("frame_selector", "")))
            value_input.setText(
                str(
                    current_step.get("value")
                    or current_step.get("url")
                    or current_step.get("text")
                    or current_step.get("message")
                    or ""
                )
            )
            scenario_value = str(
                current_step.get("scenario")
                or current_step.get("scenario_name")
                or current_step.get("name")
                or current_step.get("value")
                or ""
            ).strip()
            if scenario_value:
                idx = scenario_combo.findData(scenario_value)
                if idx >= 0:
                    scenario_combo.setCurrentIndex(idx)
                else:
                    scenario_combo.insertItem(1, scenario_value, scenario_value)
                    scenario_combo.setCurrentIndex(1)

            http_merged: Dict[str, object] = {}
            http_merged.update(self._try_parse_json_object(current_step.get("options") or {}))
            http_merged.update(self._try_parse_json_object(current_step.get("options_json") or ""))
            http_merged.update({k: v for k, v in (current_step or {}).items() if v is not None})

            method = str(http_merged.get("method") or "GET").upper()
            http_method_combo.setCurrentText(method if method else "GET")
            http_headers_input.setPlainText(self._format_kv_lines(http_merged.get("headers")))
            http_params_input.setPlainText(self._format_kv_lines(http_merged.get("params"), sep="="))
            body_val = http_merged.get("data")
            if body_val is None:
                body_val = http_merged.get("json")
            if body_val is None:
                body_val = http_merged.get("body")
            if isinstance(body_val, (dict, list)):
                try:
                    http_body_input.setPlainText(json.dumps(body_val, ensure_ascii=False, indent=2))
                    http_body_is_json.setChecked(True)
                except Exception:
                    http_body_input.setPlainText("")
                    http_body_is_json.setChecked(False)
            else:
                http_body_input.setPlainText("" if body_val is None else str(body_val))
                http_body_is_json.setChecked(False)
            http_save_as_input.setText(str(http_merged.get("save_as") or ""))
            http_response_var_input.setText(str(http_merged.get("response_var") or http_merged.get("to_var") or ""))
            http_extract_input.setPlainText(self._format_kv_lines(http_merged.get("extract_json"), sep="="))
            http_require_success.setChecked(bool(http_merged.get("require_success")))
            http_fail_on_status_code.setChecked(bool(http_merged.get("fail_on_status_code")))
            http_ignore_https_errors.setChecked(bool(http_merged.get("ignore_https_errors")))
            try:
                http_max_redirects.setValue(int(http_merged.get("max_redirects") or 0))
            except Exception:
                http_max_redirects.setValue(0)
            try:
                http_max_retries.setValue(int(http_merged.get("max_retries") or 0))
            except Exception:
                http_max_retries.setValue(0)

            variable_input.setText(str(current_step.get("to_var") or current_step.get("variable") or current_step.get("name") or ""))
            attribute_input.setText(str(current_step.get("attribute", "")))
            targets_val = current_step.get("pattern") or current_step.get("targets_string")
            if targets_val:
                targets_input.setText(str(targets_val))
            elif isinstance(current_step.get("targets"), list):
                targets_input.setText(" | ".join(map(str, current_step.get("targets"))))
            else:
                targets_input.clear()
            compare_op_input.setCurrentText(str(current_step.get("op") or current_step.get("operator") or "equals"))
            compare_right_var_input.setText(str(current_step.get("right_var") or ""))
            compare_result_var_input.setText(str(current_step.get("result_var") or current_step.get("to_var") or ""))
            compare_case_sensitive_input.setChecked(bool(current_step.get("case_sensitive", False)))
            update_account_raw = current_step.get("update_account")
            parse_update_account_input.setChecked(True if update_account_raw is None else bool(update_account_raw))
            state_input.setCurrentText(str(current_step.get("state", "")))
            timeout_input.setValue(int(current_step.get("timeout_ms", 0) or 0))
            sleep_input.setValue(float(current_step.get("seconds", 0) or 0))
            tab_index_input.setValue(int(current_step.get("tab_index", current_step.get("index", 0) or 0)))
            jump_missing_input.setText(str(current_step.get("jump_if_missing", "")))
            jump_found_input.setText(str(current_step.get("jump_if_found", "")))
            file_name_input.setText(str(current_step.get("filename") or current_step.get("file") or ""))
            base_action = current_step.get("action", base_action)
            tag_input.setText(str(current_step.get("tag", "")))
        else:
            tag_input.setText(self._peek_next_tag())

        selected_category = _category_for_action(selected_action["value"])
        _set_category(selected_category)

        def accept():
            step_action = selected_action["value"]
            step: Dict[str, object] = {"action": step_action}
            if step_action == "start" and current_step is None:
                QMessageBox.warning(self, "Error", "Start step already exists")
                return
            selector = selector_input.text().strip()
            selector_type = selector_type_input.currentText().strip() or "css"
            frame_raw = frame_input.text().strip()
            frame = self._frame_selector_from_text(frame_raw)
            value = value_input.text().strip()
            scenario_name = str(scenario_combo.currentData() or scenario_combo.currentText() or "").strip()
            variable = variable_input.text().strip()
            attribute = attribute_input.text().strip()
            targets_raw = targets_input.text().strip()
            compare_op = compare_op_input.currentText().strip()
            compare_right_var = compare_right_var_input.text().strip()
            compare_result_var = compare_result_var_input.text().strip()
            compare_case_sensitive = bool(compare_case_sensitive_input.isChecked())
            state = state_input.currentText().strip()
            timeout = timeout_input.value()
            seconds = sleep_input.value()
            tab_index = tab_index_input.value()
            selector_index = selector_index_input.value()
            jump_missing = jump_missing_input.text().strip()
            jump_found = jump_found_input.text().strip()
            file_name = file_name_input.text().strip()
            tag = tag_input.text().strip() or self._next_tag()
            step["tag"] = tag

            if selector:
                step["selector"] = selector
                step["selector_type"] = selector_type
                if selector_index:
                    step["selector_index"] = selector_index
            if frame:
                step["frame_selector"] = frame
            if state:
                step["state"] = state
            if timeout:
                step["timeout_ms"] = timeout
            if seconds:
                step["seconds"] = seconds
            if tab_index:
                step["tab_index"] = tab_index
            if attribute:
                step["attribute"] = attribute
            if targets_raw:
                if step_action in {"pop_shared", "parse_var"}:
                    step["pattern"] = targets_raw
                    step["targets_string"] = targets_raw  # backward compatibility

            if step_action == "run_scenario":
                if not scenario_name or scenario_name.lower().startswith("select a scenario"):
                    QMessageBox.warning(self, "Error", "Scenario is required for run_scenario")
                    return
                step["scenario"] = scenario_name
                value = scenario_name

            if value:
                step["value"] = value
            if step_action == "parse_var":
                if variable:
                    step["from_var"] = variable
                if not targets_raw:
                    QMessageBox.warning(self, "Error", "Pattern is required for parse_var")
                    return
                if not parse_update_account_input.isChecked():
                    step["update_account"] = False
            if step_action == "compare":
                if variable:
                    step["left_var"] = variable
                if compare_right_var:
                    step["right_var"] = compare_right_var
                if compare_op:
                    step["op"] = compare_op
                if compare_result_var:
                    step["result_var"] = compare_result_var
                if compare_case_sensitive:
                    step["case_sensitive"] = True
            if step_action == "http_request":
                method = http_method_combo.currentText().strip() or "GET"
                step["method"] = method.upper()
                headers = self._parse_kv_lines(http_headers_input.toPlainText())
                if headers:
                    step["headers"] = headers
                params = self._parse_kv_lines(http_params_input.toPlainText())
                if params:
                    step["params"] = params
                body_raw = http_body_input.toPlainText().strip()
                if body_raw:
                    if http_body_is_json.isChecked():
                        try:
                            step["data"] = json.loads(body_raw)
                        except Exception:
                            QMessageBox.warning(self, "Error", "Body is marked as JSON but cannot be parsed")
                            return
                    else:
                        step["data"] = body_raw
                save_as = http_save_as_input.text().strip()
                if save_as:
                    step["save_as"] = save_as
                response_var = http_response_var_input.text().strip()
                if response_var:
                    step["response_var"] = response_var
                extract_map = self._parse_extract_lines(http_extract_input.toPlainText())
                if extract_map:
                    step["extract_json"] = extract_map
                if http_require_success.isChecked():
                    step["require_success"] = True
                if http_fail_on_status_code.isChecked():
                    step["fail_on_status_code"] = True
                if http_ignore_https_errors.isChecked():
                    step["ignore_https_errors"] = True
                max_redirects = int(http_max_redirects.value() or 0)
                if max_redirects:
                    step["max_redirects"] = max_redirects
                max_retries = int(http_max_retries.value() or 0)
                if max_retries:
                    step["max_retries"] = max_retries
            if step_action == "write_file":
                if file_name:
                    step["filename"] = file_name
                if not file_name:
                    QMessageBox.warning(self, "Error", "File name is required for write_file")
                    return
            if step_action == "type":
                step.setdefault("clear", True)
            if step_action == "set_var" and variable:
                step["name"] = variable
            if step_action == "extract_text" and variable:
                step["to_var"] = variable
            if step_action in ("wait_for_load_state",) and value:
                step["state"] = value
            dlg.accept()
            dlg._result_step = step  # type: ignore[attr-defined]

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dlg.reject)
        dlg._result_step = None  # type: ignore[attr-defined]
        dlg.exec()
        return getattr(dlg, "_result_step", None)

    def _save_scenario(self) -> None:
        name = self.scenario_name_input.text().strip()
        if not name:
            items = self.scenario_list_widget.selectedItems()
            if items:
                name = items[0].text()
        if not name:
            QMessageBox.warning(self, "Error", "Scenario name is required")
            return
        description = self.scenario_description_input.text().strip() or None
        self._sync_positions_from_map()
        self._normalize_steps()
        db_save_scenario(name, self.current_steps, description=description)
        self._map_focus_on_load = False
        self._reload_scenarios()
        matches = self.scenario_list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.scenario_list_widget.setCurrentItem(matches[0])
        self._map_focus_on_load = True
        self.log(f"Scenario {name} saved ({len(self.current_steps)} steps)")
        self._refresh_vars_list()

    def _set_row_visible(self, row_widgets: Tuple[QLabel, object], visible: bool) -> None:
        for widget in row_widgets:
            widget.setVisible(visible)

    def _handle_action_combo_change(self, index: int) -> None:
        self._on_action_changed(self._current_action_value())

    def _current_action_value(self) -> str:
        if not hasattr(self, "step_action_combo"):
            return ""
        data = self.step_action_combo.currentData()
        if data is None:
            return str(self.step_action_combo.currentText() or "")
        return str(data)

    def _select_action_value(self, action: Optional[str]) -> None:
        if not hasattr(self, "step_action_combo"):
            return
        combo = self.step_action_combo
        if combo.count() == 0:
            return
        idx = combo.findData(action)
        if idx < 0:
            idx = 0
        previous = combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(previous)
        self._on_action_changed(self._current_action_value())

    def _action_display_name(self, action: Optional[str]) -> str:
        key = str(action or "")
        if not key:
            return "—"
        return ACTION_LABELS.get(key, key.upper())

    def _on_action_changed(self, action: str) -> None:
        self._update_form_visibility(action)

    def _update_form_visibility(self, action: str) -> None:
        action = action or ""
        selector_actions = {"click", "type", "wait_element", "extract_text"}
        show_selector = action in selector_actions
        show_frame = action in selector_actions
        show_value = action in {"goto", "type", "set_var", "pop_shared", "new_tab", "log", "run_scenario", "set_tag", "set_stage", "http_request", "compare"}
        show_http = action == "http_request"
        show_variable = action in {"set_var", "extract_text", "parse_var", "compare"}
        show_attribute = action == "extract_text"
        show_targets = action in {"pop_shared", "parse_var"}
        show_parse_update_account = action == "parse_var"
        show_compare = action == "compare"
        show_state = action in {"wait_for_load_state"}
        show_timeout = action in selector_actions or action in {"wait_for_load_state", "goto", "new_tab", "http_request"}
        show_sleep = action == "sleep"
        show_tab = action in {"switch_tab", "close_tab"}
        show_jump = False

        self._set_row_visible(self.row_selector, show_selector)
        self._set_row_visible(self.row_selector_type, show_selector)
        self._set_row_visible(self.row_selector_index, show_selector)
        self._set_row_visible(self.row_frame, show_frame)
        self._set_row_visible(self.row_value, show_value)
        self._set_row_visible(self.row_parse_update_account, show_parse_update_account)
        self._set_row_visible(self.row_compare_op, show_compare)
        self._set_row_visible(self.row_compare_right_var, show_compare)
        self._set_row_visible(self.row_compare_result_var, show_compare)
        self._set_row_visible(self.row_compare_case_sensitive, show_compare)
        self._set_row_visible(self.row_http_method, show_http)
        self._set_row_visible(self.row_http_headers, show_http)
        self._set_row_visible(self.row_http_params, show_http)
        self._set_row_visible(self.row_http_body, show_http)
        self._set_row_visible(self.row_http_body_is_json, show_http)
        self._set_row_visible(self.row_http_save_as, show_http)
        self._set_row_visible(self.row_http_response_var, show_http)
        self._set_row_visible(self.row_http_extract, show_http)
        self._set_row_visible(self.row_http_require_success, show_http)
        self._set_row_visible(self.row_http_fail_on_status_code, show_http)
        self._set_row_visible(self.row_http_ignore_https_errors, show_http)
        self._set_row_visible(self.row_http_max_redirects, show_http)
        self._set_row_visible(self.row_http_max_retries, show_http)
        self._set_row_visible(self.row_variable, show_variable)
        self._set_row_visible(self.row_attribute, show_attribute)
        self._set_row_visible(self.row_targets, show_targets)
        self._set_row_visible(self.row_state, show_state)
        self._set_row_visible(self.row_timeout, show_timeout)
        self._set_row_visible(self.row_sleep, show_sleep)
        self._set_row_visible(self.row_tab, show_tab)
        self._set_row_visible(self.row_jump_missing, show_jump)
        self._set_row_visible(self.row_jump_found, show_jump)
        # On-error controls stay visible for consistency
        self._refresh_vars_list()

    def _refresh_vars_list(self) -> None:
        if not hasattr(self, "vars_list"):
            return
        vars_found = {"email", "login", "password", "auth2", "proxy"}
        for step in self.current_steps:
            for key in ("name", "variable", "to_var", "save_as"):
                val = step.get(key)
                if val:
                    vars_found.add(str(val))
        self.vars_list.clear()
        for name in sorted(vars_found):
            self.vars_list.addItem(name)
