"""Scenarios bridge for QML."""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.services.scenario_engine import run_scenario
from app.services.server_client import ServerClient, ServerClientError, server_enabled
from app.storage.db import (
    Scenario,
    db_delete_scenario,
    db_get_accounts,
    db_get_scenario,
    db_get_scenario_path,
    db_get_scenarios,
    db_save_scenario,
    init_db,
)
from app.ui.bridge.cloud_permissions import allows, deny_message
from app.ui.bridge.models import DictListModel

LOGGER = logging.getLogger(__name__)

ACTION_OPTIONS: List[Tuple[str, str]] = [
    ("Start scenario", "start"),
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
ACTION_LABELS = {value: label for label, value in ACTION_OPTIONS}
ACTION_CATEGORY_PRESETS: List[Tuple[str, List[str]]] = [
    ("Navigation & interaction", ["goto", "wait_for_load_state", "wait_element", "sleep", "click", "type"]),
    ("Variables", ["set_var", "parse_var", "pop_shared", "extract_text", "write_file"]),
    ("Network", ["http_request"]),
    ("Browser tabs", ["new_tab", "switch_tab", "close_tab"]),
    ("Flow & logging", ["start", "end", "run_scenario", "log", "set_tag", "compare"]),
]
ACTION_TO_CATEGORY = {action: category for category, actions in ACTION_CATEGORY_PRESETS for action in actions}
MARKET_CATEGORIES = ["All", "Social", "Ads", "E-commerce", "Scraping", "Warm-up", "QA", "Utility"]


def _deepcopy_steps(steps: object) -> List[Dict[str, Any]]:
    if not isinstance(steps, list):
        return []
    try:
        return json.loads(json.dumps(steps, ensure_ascii=False))
    except Exception:
        return [dict(item) for item in steps if isinstance(item, dict)]


class ScenariosBridge(QObject):
    modelChanged = pyqtSignal()
    selectedChanged = pyqtSignal()
    categoryChanged = pyqtSignal()
    selectedStepChanged = pyqtSignal()
    runProfileChanged = pyqtSignal()
    runsChanged = pyqtSignal()
    marketChanged = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, profiles_bridge=None, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._profiles_bridge = profiles_bridge
        self._app_state = app_state
        self._model = DictListModel(["name", "description", "steps"], parent=self)
        self._steps_model = DictListModel([
            "row", "index", "title", "subtitle", "action", "tag", "nextOk", "nextErr", "x", "y", "accent", "selected"
        ], parent=self)
        self._categories_model = DictListModel(["name", "count", "selected"], parent=self)
        self._templates_model = DictListModel(["title", "subtitle", "action", "category"], parent=self)
        self._actions_model = DictListModel(["label", "value", "category"], parent=self)
        self._runs_model = DictListModel([
            "id", "scenario", "profile", "status", "duration", "started", "error", "accent"
        ], parent=self)
        self._market_model = DictListModel([
            "id", "title", "description", "category", "tags", "downloads", "author", "steps", "selected"
        ], parent=self)
        self._market_categories_model = DictListModel(["name", "selected"], parent=self)
        self._selected_name = ""
        self._selected_description = ""
        self._selected_category = ACTION_CATEGORY_PRESETS[0][0]
        self._selected_step_index = -1
        self._run_profile = ""
        self._market_query = ""
        self._market_category = "All"
        self._market_sort = "popular"
        self._selected_market: Dict[str, Any] = {}
        self._market_rows: List[Dict[str, Any]] = []
        self._server_scenario_ids: Dict[str, str] = {}
        self._current_steps: List[Dict[str, Any]] = []
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
            app_state.cloudChanged.connect(self.refresh)
        self._refresh_static_models()
        self.refresh()

    @pyqtProperty(QObject, constant=True)
    def model(self) -> QObject:
        return self._model

    @pyqtProperty(QObject, constant=True)
    def stepsModel(self) -> QObject:  # noqa: N802
        return self._steps_model

    @pyqtProperty(QObject, constant=True)
    def categoriesModel(self) -> QObject:  # noqa: N802
        return self._categories_model

    @pyqtProperty(QObject, constant=True)
    def templatesModel(self) -> QObject:  # noqa: N802
        return self._templates_model

    @pyqtProperty(QObject, constant=True)
    def actionsModel(self) -> QObject:  # noqa: N802
        return self._actions_model

    @pyqtProperty(QObject, constant=True)
    def runsModel(self) -> QObject:  # noqa: N802
        return self._runs_model

    @pyqtProperty(QObject, constant=True)
    def marketModel(self) -> QObject:  # noqa: N802
        return self._market_model

    @pyqtProperty(QObject, constant=True)
    def marketCategoriesModel(self) -> QObject:  # noqa: N802
        return self._market_categories_model

    @pyqtProperty(QObject, constant=True)
    def profilesModel(self) -> QObject:  # noqa: N802
        return self._profiles_bridge.model if self._profiles_bridge is not None else DictListModel(["name"], parent=self)

    @pyqtProperty(str, notify=selectedChanged)
    def selectedName(self) -> str:  # noqa: N802
        return self._selected_name

    @pyqtProperty(str, notify=selectedChanged)
    def selectedDescription(self) -> str:  # noqa: N802
        return self._selected_description

    @pyqtProperty(str, notify=categoryChanged)
    def selectedCategory(self) -> str:  # noqa: N802
        return self._selected_category

    @pyqtProperty(int, notify=selectedStepChanged)
    def selectedStepIndex(self) -> int:  # noqa: N802
        return self._selected_step_index

    @pyqtProperty(str, notify=selectedStepChanged)
    def selectedStepJson(self) -> str:  # noqa: N802
        step = self._selected_step()
        return json.dumps(step or {}, ensure_ascii=False, indent=2)

    @pyqtProperty(str, notify=runProfileChanged)
    def runProfile(self) -> str:  # noqa: N802
        return self._run_profile

    @pyqtProperty(str, notify=marketChanged)
    def marketQuery(self) -> str:  # noqa: N802
        return self._market_query

    @pyqtProperty(str, notify=marketChanged)
    def marketCategory(self) -> str:  # noqa: N802
        return self._market_category

    @pyqtProperty(str, notify=marketChanged)
    def marketSort(self) -> str:  # noqa: N802
        return self._market_sort

    @pyqtProperty(str, notify=marketChanged)
    def selectedMarketTitle(self) -> str:  # noqa: N802
        return str(self._selected_market.get("title") or "")

    @pyqtProperty(str, notify=marketChanged)
    def selectedMarketDescription(self) -> str:  # noqa: N802
        return str(self._selected_market.get("description") or "")

    @pyqtProperty(str, notify=marketChanged)
    def selectedMarketCategory(self) -> str:  # noqa: N802
        return str(self._selected_market.get("category") or "")

    @pyqtProperty(str, notify=marketChanged)
    def selectedMarketMeta(self) -> str:  # noqa: N802
        if not self._selected_market:
            return "Select scenario"
        downloads = int(self._selected_market.get("downloads") or 0)
        steps = len(self._market_steps(self._selected_market))
        tags = ", ".join(self._selected_market.get("tags") or [])
        base = f"{self.selectedMarketCategory} · {steps} steps · {downloads} downloads"
        return f"{base} · {tags}" if tags else base

    @pyqtProperty(str, notify=marketChanged)
    def selectedMarketStepsJson(self) -> str:  # noqa: N802
        steps = self._market_steps(self._selected_market)
        return json.dumps(steps, ensure_ascii=False, indent=2)

    @pyqtProperty(int, notify=modelChanged)
    def total(self) -> int:
        return self._model.rowCount()

    @pyqtProperty(bool, notify=modelChanged)
    def canRun(self) -> bool:  # noqa: N802
        return allows(self._app_state, "operator")

    @pyqtProperty(bool, notify=modelChanged)
    def canManage(self) -> bool:  # noqa: N802
        return allows(self._app_state, "manager")

    @pyqtProperty(bool, notify=modelChanged)
    def canAdmin(self) -> bool:  # noqa: N802
        return allows(self._app_state, "admin")

    def _ensure_allowed(self, min_role: str) -> bool:
        if allows(self._app_state, min_role):
            return True
        self._emit_message(deny_message(min_role))
        return False

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    def _server_client(self):
        client = ServerClient()
        return client if client.configured else None

    def _public_client(self):
        return ServerClient()

    def _list_scenarios(self) -> List[Scenario]:
        client = self._server_client()
        if server_enabled() and client:
            try:
                rows = client.scenarios()
            except ServerClientError as exc:
                self._emit_message(f"Server scenarios error: {exc}")
                return []
            self._server_scenario_ids = {str(row.get("name") or ""): str(row.get("id") or "") for row in rows}
            return [
                Scenario(
                    name=str(row.get("name") or ""),
                    description=str(row.get("description") or ""),
                    steps=(row.get("definition") if isinstance(row.get("definition"), dict) else {}).get("steps") or [],
                )
                for row in rows
            ]
        return db_get_scenarios()

    def _get_scenario(self, name: str) -> Optional[Scenario]:
        if server_enabled() and self._server_client():
            return next((item for item in self._list_scenarios() if item.name == str(name or "")), None)
        return db_get_scenario(name)

    def _save_scenario(self, name: str, steps: List[Dict], description: str) -> None:
        client = self._server_client()
        if server_enabled() and client:
            scenario_id = self._server_scenario_ids.get(name)
            payload = {"name": name, "description": description or "", "definition": {"steps": steps or []}}
            if scenario_id:
                client.update_scenario(scenario_id, payload)
            else:
                client.create_scenario(payload)
            return
        db_save_scenario(name, steps, description)

    def _delete_scenario(self, name: str) -> None:
        client = self._server_client()
        if server_enabled() and client:
            scenario_id = self._server_scenario_ids.get(name)
            if scenario_id:
                client.delete_scenario(scenario_id)
            return
        db_delete_scenario(name)

    def _refresh_static_models(self) -> None:
        self._categories_model.set_rows([
            {"name": name, "count": len(actions), "selected": name == self._selected_category}
            for name, actions in ACTION_CATEGORY_PRESETS
        ])
        self._templates_model.set_rows([
            {
                "title": ACTION_LABELS.get(action, action),
                "subtitle": f"{action}()",
                "action": action,
                "category": self._selected_category,
            }
            for category, actions in ACTION_CATEGORY_PRESETS
            if category == self._selected_category
            for action in actions
        ])
        self._actions_model.set_rows([
            {"label": label, "value": value, "category": ACTION_TO_CATEGORY.get(value, "Other")}
            for label, value in ACTION_OPTIONS
        ])
        self._refresh_market_categories_model()

    def _refresh_market_categories_model(self) -> None:
        self._market_categories_model.set_rows([
            {"name": name, "selected": name == self._market_category}
            for name in MARKET_CATEGORIES
        ])

    @pyqtSlot()
    def refresh(self) -> None:
        scenarios = self._list_scenarios()
        self._model.set_rows([
            {"name": s.name, "description": s.description or "", "steps": len(s.steps or [])}
            for s in scenarios
        ])
        if not self._selected_name and scenarios:
            self._set_selected(scenarios[0])
        elif self._selected_name:
            loaded = self._get_scenario(self._selected_name)
            if loaded:
                self._set_selected(loaded)
            elif scenarios:
                self._set_selected(scenarios[0])
        self._refresh_runs()
        self.modelChanged.emit()

    def _refresh_runs(self) -> None:
        client = self._server_client()
        if not (server_enabled() and client):
            self._runs_model.set_rows([])
            self.runsChanged.emit()
            return
        try:
            rows = client.scenario_runs(limit=80)
        except ServerClientError as exc:
            self._emit_message(f"Scenario runs error: {exc}")
            rows = []
        self._runs_model.set_rows([self._run_row(row) for row in rows])
        self.runsChanged.emit()

    @staticmethod
    def _run_row(row: Dict[str, Any]) -> Dict[str, Any]:
        status = str(row.get("status") or "running").lower()
        duration_ms = int(row.get("duration_ms") or 0)
        if duration_ms >= 1000:
            duration = f"{duration_ms / 1000:.1f}s"
        elif duration_ms > 0:
            duration = f"{duration_ms}ms"
        else:
            duration = "running"
        return {
            "id": str(row.get("id") or ""),
            "scenario": str(row.get("scenario_name") or "Scenario"),
            "profile": str(row.get("profile_name") or "Profile"),
            "status": status.title(),
            "duration": duration,
            "started": str(row.get("started_at") or "")[:19].replace("T", " "),
            "error": str(row.get("error") or ""),
            "accent": "#22c55e" if status == "success" else "#ef4444" if status == "failed" else "#f59e0b",
        }

    @staticmethod
    def _market_steps(row: Dict[str, Any]) -> List[Dict[str, Any]]:
        definition = row.get("definition") if isinstance(row, dict) else {}
        if not isinstance(definition, dict):
            return []
        steps = definition.get("steps")
        return steps if isinstance(steps, list) else []

    @staticmethod
    def _market_row(row: Dict[str, Any], selected_id: str = "") -> Dict[str, Any]:
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        steps = ScenariosBridge._market_steps(row)
        item_id = str(row.get("id") or "")
        return {
            "id": item_id,
            "title": str(row.get("title") or "Scenario"),
            "description": str(row.get("description") or ""),
            "category": str(row.get("category") or "Utility"),
            "tags": ", ".join(str(tag) for tag in tags if str(tag).strip()),
            "downloads": int(row.get("downloads") or 0),
            "author": "Team" if row.get("team_id") else "Community",
            "steps": len(steps),
            "selected": bool(selected_id and item_id == selected_id),
        }

    def _rebuild_market_model(self) -> None:
        selected_id = str(self._selected_market.get("id") or "")
        self._market_model.set_rows([self._market_row(row, selected_id) for row in self._market_rows])
        self._refresh_market_categories_model()
        self.marketChanged.emit()

    def _valid_market_definition(self, row: Dict[str, Any]) -> bool:
        definition = row.get("definition") if isinstance(row, dict) else {}
        return isinstance(definition, dict) and isinstance(definition.get("steps"), list)

    def _unique_scenario_name(self, base_name: str) -> str:
        base = str(base_name or "Scenario").strip() or "Scenario"
        existing = {str(s.name or "").lower() for s in self._list_scenarios()}
        name = base
        index = 2
        while name.lower() in existing:
            name = f"{base} {index}"
            index += 1
        return name

    @staticmethod
    def _tags_from_text(text: str) -> List[str]:
        tags: List[str] = []
        seen: set[str] = set()
        for chunk in str(text or "").replace("\n", ",").split(","):
            tag = chunk.strip()
            key = tag.lower()
            if not tag or key in seen:
                continue
            tags.append(tag)
            seen.add(key)
            if len(tags) >= 10:
                break
        return tags

    def _set_selected(self, scenario: Scenario) -> None:
        self._selected_name = scenario.name
        self._selected_description = scenario.description or ""
        self._current_steps = _deepcopy_steps(scenario.steps or [])
        self._ensure_start_step()
        self._ensure_step_tags()
        if self._selected_step_index >= len(self._current_steps):
            self._selected_step_index = len(self._current_steps) - 1
        if self._selected_step_index < 0 and self._current_steps:
            self._selected_step_index = 0
        self._rebuild_steps_model()
        self.selectedChanged.emit()
        self.selectedStepChanged.emit()

    def _ensure_start_step(self) -> None:
        if self._current_steps and str(self._current_steps[0].get("action") or "").lower() == "start":
            self._current_steps[0].setdefault("tag", "Start")
            return
        first_tag = str(self._current_steps[0].get("tag") or "") if self._current_steps else ""
        start: Dict[str, Any] = {"action": "start", "tag": "Start"}
        if first_tag:
            start["next_success_step"] = first_tag
        self._current_steps.insert(0, start)

    def _ensure_step_tags(self) -> None:
        seen: set[str] = set()
        counter = 1
        for index, step in enumerate(self._current_steps):
            tag = str(step.get("tag") or "").strip()
            if index == 0:
                tag = tag or "Start"
            if not tag or tag in seen:
                while f"Step{counter}" in seen:
                    counter += 1
                tag = f"Step{counter}"
            step["tag"] = tag
            seen.add(tag)

    def _rebuild_steps_model(self) -> None:
        rows = []
        for index, step in enumerate(self._current_steps):
            action = str(step.get("action") or "start")
            pos = step.get("_pos") if isinstance(step.get("_pos"), dict) else {}
            x = self._float_or(pos.get("x"), 48 + index * 290)
            y = self._float_or(pos.get("y"), 170 + (1 if self._is_error_target(index) else 0) * 110)
            rows.append({
                "row": index,
                "index": index + 1,
                "title": self._title_for_step(step, index),
                "subtitle": self._subtitle_for_step(step),
                "action": action,
                "tag": str(step.get("tag") or ""),
                "nextOk": str(step.get("next_success_step") or ""),
                "nextErr": str(step.get("next_error_step") or ""),
                "x": x,
                "y": y,
                "accent": "#06b6d4" if index == 0 else "#ef4444" if self._is_error_target(index) else "#8b5cf6",
                "selected": index == self._selected_step_index,
            })
        self._steps_model.set_rows(rows)
        self.selectedStepChanged.emit()

    @staticmethod
    def _float_or(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _is_error_target(self, index: int) -> bool:
        tag = str(self._current_steps[index].get("tag") or "") if 0 <= index < len(self._current_steps) else ""
        return bool(tag and any(str(step.get("next_error_step") or "") == tag for step in self._current_steps))

    def _title_for_step(self, step: Dict[str, Any], index: int) -> str:
        action = str(step.get("action") or "start")
        return ACTION_LABELS.get(action, str(step.get("label") or step.get("description") or action.replace("_", " ").title() or f"Step {index + 1}"))

    def _subtitle_for_step(self, step: Dict[str, Any]) -> str:
        for key in ("url", "value", "selector", "text", "message", "name", "to_var", "scenario", "pattern"):
            value = step.get(key)
            if value not in (None, ""):
                return str(value)
        ok = step.get("next_success_step")
        err = step.get("next_error_step")
        if ok or err:
            return " / ".join(part for part in [f"ok?{ok}" if ok else "", f"err?{err}" if err else ""] if part)
        return ""

    def _selected_step(self) -> Optional[Dict[str, Any]]:
        if 0 <= self._selected_step_index < len(self._current_steps):
            return self._current_steps[self._selected_step_index]
        return None

    def _save_current(self) -> None:
        if not self._selected_name:
            return
        self._ensure_start_step()
        self._ensure_step_tags()
        self._save_scenario(self._selected_name, self._current_steps, self._selected_description)
        self._rebuild_steps_model()
        self.refresh()

    @pyqtSlot(str)
    def setCategory(self, name: str) -> None:  # noqa: N802
        name = str(name or "")
        if name not in {category for category, _ in ACTION_CATEGORY_PRESETS}:
            return
        self._selected_category = name
        self._refresh_static_models()
        self.categoryChanged.emit()

    @pyqtSlot(str)
    def selectScenario(self, name: str) -> None:  # noqa: N802
        scenario = self._get_scenario(str(name or ""))
        if scenario:
            self._selected_step_index = 0
            self._set_selected(scenario)

    @pyqtSlot()
    def createScenario(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        base = "New scenario"
        existing = {s.name.lower() for s in self._list_scenarios()}
        name = base
        index = 2
        while name.lower() in existing:
            name = f"{base} {index}"
            index += 1
        self._save_scenario(name, [{"action": "start", "tag": "Start"}], "")
        self._selected_name = name
        self._selected_description = ""
        self._selected_step_index = 0
        self.refresh()
        self._emit_message(f"Scenario {name} created")

    @pyqtSlot(str, str)
    def saveSelected(self, name: str, description: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        target = str(name or self._selected_name or "Scenario").strip() or "Scenario"
        old = self._selected_name
        self._selected_description = str(description or "")
        self._ensure_start_step()
        self._ensure_step_tags()
        self._save_scenario(target, self._current_steps, self._selected_description)
        if old and old != target:
            self._delete_scenario(old)
        self._selected_name = target
        self.refresh()
        self.selectScenario(target)
        self._emit_message(f"Scenario {target} saved")

    @pyqtSlot()
    def duplicateSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        if not self._selected_name:
            return
        base = f"{self._selected_name} copy"
        existing = {s.name.lower() for s in self._list_scenarios()}
        name = base
        index = 2
        while name.lower() in existing:
            name = f"{base} {index}"
            index += 1
        self._save_scenario(name, _deepcopy_steps(self._current_steps), self._selected_description)
        self._selected_name = name
        self.refresh()
        self.selectScenario(name)
        self._emit_message(f"Scenario duplicated as {name}")

    @pyqtSlot()
    def deleteSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("admin"):
            return
        if not self._selected_name:
            return
        old = self._selected_name
        self._delete_scenario(old)
        self._selected_name = ""
        self._selected_description = ""
        self._selected_step_index = -1
        self._current_steps = []
        self._steps_model.set_rows([])
        self.refresh()
        self._emit_message(f"Scenario {old} deleted")

    @pyqtSlot(int)
    def selectStep(self, row: int) -> None:  # noqa: N802
        row = int(row)
        if 0 <= row < len(self._current_steps):
            self._selected_step_index = row
            self._rebuild_steps_model()

    @pyqtSlot(str)
    def addAction(self, action: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        if not self._selected_name:
            self.createScenario()
        action = str(action or "sleep")
        insert_at = len(self._current_steps)
        step = self._default_step(action)
        self._current_steps.insert(insert_at, step)
        self._selected_step_index = insert_at
        self._save_current()

    @pyqtSlot()
    def duplicateStep(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        step = self._selected_step()
        if not step:
            return
        clone = copy.deepcopy(step)
        clone.pop("tag", None)
        clone.pop("_pos", None)
        self._current_steps.insert(self._selected_step_index + 1, clone)
        self._selected_step_index += 1
        self._save_current()

    @pyqtSlot()
    def deleteStep(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        idx = self._selected_step_index
        if idx <= 0 or idx >= len(self._current_steps):
            self._emit_message("Start step cannot be deleted")
            return
        removed_tag = str(self._current_steps[idx].get("tag") or "")
        self._current_steps.pop(idx)
        for step in self._current_steps:
            if step.get("next_success_step") == removed_tag:
                step.pop("next_success_step", None)
            if step.get("next_error_step") == removed_tag:
                step.pop("next_error_step", None)
        self._selected_step_index = min(idx, len(self._current_steps) - 1)
        self._save_current()

    @pyqtSlot(int)
    def moveStep(self, delta: int) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        idx = self._selected_step_index
        target = idx + int(delta)
        if idx <= 0 or target <= 0 or idx >= len(self._current_steps) or target >= len(self._current_steps):
            return
        self._current_steps[idx], self._current_steps[target] = self._current_steps[target], self._current_steps[idx]
        self._selected_step_index = target
        self._save_current()

    @pyqtSlot(int, float, float)
    def setStepPosition(self, row: int, x: float, y: float) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        row = int(row)
        if 0 <= row < len(self._current_steps):
            self._current_steps[row]["_pos"] = {"x": round(float(x), 2), "y": round(float(y), 2)}
            self._save_current()

    @pyqtSlot(int, int, str)
    def linkSteps(self, source_row: int, target_row: int, kind: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        source_row = int(source_row)
        target_row = int(target_row)
        if not (0 <= source_row < len(self._current_steps) and 0 <= target_row < len(self._current_steps)):
            return
        target_tag = str(self._current_steps[target_row].get("tag") or "").strip()
        if not target_tag:
            self._ensure_step_tags()
            target_tag = str(self._current_steps[target_row].get("tag") or "").strip()
        key = "next_error_step" if str(kind).lower() == "err" else "next_success_step"
        self._current_steps[source_row][key] = target_tag
        self._selected_step_index = source_row
        self._save_current()
        self._emit_message(f"Linked {self._current_steps[source_row].get('tag')} -> {target_tag}")

    @pyqtSlot(int, int, str)
    def deleteLink(self, source_row: int, target_row: int, kind: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        source_row = int(source_row)
        target_row = int(target_row)
        if not (0 <= source_row < len(self._current_steps) and 0 <= target_row < len(self._current_steps)):
            return
        key = "next_error_step" if str(kind).lower() == "err" else "next_success_step"
        target_tag = str(self._current_steps[target_row].get("tag") or "")
        if str(self._current_steps[source_row].get(key) or "") != target_tag:
            return
        self._current_steps[source_row].pop(key, None)
        self._selected_step_index = source_row
        self._save_current()
        self._emit_message("Link deleted")

    @pyqtSlot(str)
    def setRunProfile(self, name: str) -> None:  # noqa: N802
        self._run_profile = str(name or "").strip()
        self.runProfileChanged.emit()

    @pyqtSlot()
    def refreshMarket(self) -> None:  # noqa: N802
        client = self._public_client()
        category = "" if self._market_category == "All" else self._market_category
        try:
            rows = client.market_scenarios(self._market_query, category, self._market_sort)
        except ServerClientError as exc:
            self._market_rows = []
            self._selected_market = {}
            self._rebuild_market_model()
            self._emit_message(f"Marketplace error: {exc}")
            return
        self._market_rows = [row for row in rows if isinstance(row, dict)]
        selected_id = str(self._selected_market.get("id") or "")
        self._selected_market = next((row for row in self._market_rows if str(row.get("id") or "") == selected_id), {})
        if not self._selected_market and self._market_rows:
            self._selected_market = self._market_rows[0]
        self._rebuild_market_model()

    @pyqtSlot(str)
    def searchMarket(self, query: str) -> None:  # noqa: N802
        self._market_query = str(query or "").strip()
        self.refreshMarket()

    @pyqtSlot(str)
    def setMarketCategory(self, category: str) -> None:  # noqa: N802
        value = str(category or "All").strip() or "All"
        if value not in MARKET_CATEGORIES:
            value = "All"
        self._market_category = value
        self.refreshMarket()

    @pyqtSlot(str)
    def setMarketSort(self, sort: str) -> None:  # noqa: N802
        value = str(sort or "popular").strip().lower()
        self._market_sort = "new" if value == "new" else "popular"
        self.refreshMarket()

    @pyqtSlot(str)
    def selectMarketScenario(self, scenario_id: str) -> None:  # noqa: N802
        scenario_id = str(scenario_id or "")
        selected = next((row for row in self._market_rows if str(row.get("id") or "") == scenario_id), None)
        if selected is None:
            try:
                selected = self._public_client().market_scenario(scenario_id)
            except ServerClientError as exc:
                self._emit_message(f"Marketplace error: {exc}")
                return
        if isinstance(selected, dict):
            self._selected_market = selected
            self._rebuild_market_model()

    @pyqtSlot(str)
    def installMarketScenario(self, scenario_id: str) -> None:  # noqa: N802
        scenario_id = str(scenario_id or self._selected_market.get("id") or "")
        if not scenario_id:
            self._emit_message("Select marketplace scenario first")
            return
        try:
            scenario = self._public_client().download_market_scenario(scenario_id)
        except ServerClientError as exc:
            self._emit_message(f"Install failed: {exc}")
            return
        if not self._valid_market_definition(scenario):
            self._emit_message("Invalid marketplace scenario")
            return
        name = self._unique_scenario_name(str(scenario.get("title") or "Scenario"))
        description = str(scenario.get("description") or "")
        steps = _deepcopy_steps(self._market_steps(scenario))
        client = self._server_client()
        try:
            if server_enabled() and client:
                client.create_scenario({"name": name, "description": description, "definition": {"steps": steps}})
            else:
                init_db()
                db_save_scenario(name, steps, description)
        except ServerClientError as exc:
            self._emit_message(f"Install failed: {exc}")
            return
        self._selected_name = name
        self.refresh()
        self.selectScenario(name)
        self.refreshMarket()
        self._emit_message(f"Installed scenario: {name}")

    @pyqtSlot(str, str, str, str)
    def publishSelectedToMarket(self, title: str, description: str, category: str, tags: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        client = self._server_client()
        if not (server_enabled() and client):
            self._emit_message("Login to Cloud to publish")
            return
        if not self._selected_name:
            self._emit_message("Select scenario first")
            return
        self._ensure_start_step()
        self._ensure_step_tags()
        payload = {
            "title": str(title or self._selected_name).strip() or self._selected_name,
            "description": str(description or self._selected_description or "").strip(),
            "category": str(category or "Utility").strip() or "Utility",
            "tags": self._tags_from_text(tags),
            "version": 1,
            "source_scenario_id": self._server_scenario_ids.get(self._selected_name) or None,
            "definition": {"steps": _deepcopy_steps(self._current_steps)},
        }
        try:
            client.publish_market_scenario(payload)
        except ServerClientError as exc:
            self._emit_message(f"Publish failed: {exc}")
            return
        self.refreshMarket()
        self._emit_message(f"Published to marketplace: {payload['title']}")

    @pyqtSlot(str, result="QVariant")
    def selectedValue(self, key: str) -> Any:  # noqa: N802
        step = self._selected_step() or {}
        return step.get(str(key or ""), "")

    @pyqtSlot(result="QVariant")
    def selectedStep(self) -> Dict[str, Any]:  # noqa: N802
        return dict(self._selected_step() or {})

    @pyqtSlot(str, str, str, str, str, str, str, int, float, str, str, str)
    def saveStep(
        self,
        tag: str,
        action: str,
        selector: str,
        selector_type: str,
        value: str,
        variable: str,
        pattern: str,
        timeout_ms: int,
        seconds: float,
        next_success: str,
        next_error: str,
        extra_json: str,
    ) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        if self._selected_step_index < 0:
            return
        old = dict(self._current_steps[self._selected_step_index])
        action = str(action or old.get("action") or "sleep")
        step: Dict[str, Any] = {"action": action}
        clean_tag = str(tag or old.get("tag") or "").strip()
        if clean_tag:
            step["tag"] = clean_tag
        selector = str(selector or "").strip()
        if selector:
            step["selector"] = selector
            step["selector_type"] = str(selector_type or "css").strip() or "css"
        value = str(value or "").strip()
        variable = str(variable or "").strip()
        pattern = str(pattern or "").strip()
        if value:
            step["value"] = value
        if action == "goto" and value:
            step["url"] = value
        if action == "type" and value:
            step["text"] = value
            step["clear"] = bool(old.get("clear", True))
        if action == "set_var" and variable:
            step["name"] = variable
        if action in {"extract_text", "http_request"} and variable:
            step["to_var"] = variable
        if action == "parse_var":
            if variable:
                step["from_var"] = variable
            if pattern:
                step["pattern"] = pattern
                step["targets_string"] = pattern
        if action == "pop_shared" and pattern:
            step["pattern"] = pattern
            step["targets_string"] = pattern
        if timeout_ms:
            step["timeout_ms"] = int(timeout_ms)
        if seconds:
            step["seconds"] = float(seconds)
        if next_success:
            step["next_success_step"] = str(next_success).strip()
        if next_error:
            step["next_error_step"] = str(next_error).strip()
        if isinstance(old.get("_pos"), dict):
            step["_pos"] = old["_pos"]
        extra_json = str(extra_json or "").strip()
        if extra_json:
            try:
                extra = json.loads(extra_json)
                if isinstance(extra, dict):
                    step.update(extra)
            except Exception as exc:
                self._emit_message(f"Extra JSON error: {exc}")
                return
        if self._selected_step_index == 0:
            step["action"] = "start"
            step["tag"] = "Start"
        self._current_steps[self._selected_step_index] = step
        self._save_current()
        self._emit_message("Step saved")

    def _default_step(self, action: str) -> Dict[str, Any]:
        if action == "start":
            return {"action": "start", "tag": "Start"}
        if action == "goto":
            return {"action": "goto", "url": "https://example.com", "value": "https://example.com"}
        if action == "wait_for_load_state":
            return {"action": action, "state": "load", "timeout_ms": 60000}
        if action == "wait_element":
            return {"action": action, "selector": "body", "selector_type": "css", "timeout_ms": 10000}
        if action == "sleep":
            return {"action": action, "seconds": 1.0}
        if action == "click":
            return {"action": action, "selector": "button", "selector_type": "css"}
        if action == "type":
            return {"action": action, "selector": "input", "selector_type": "css", "text": "text", "value": "text", "clear": True}
        if action == "set_var":
            return {"action": action, "name": "variable", "value": "value"}
        if action == "parse_var":
            return {"action": action, "from_var": "variable", "pattern": "{{value}}", "targets_string": "{{value}}"}
        if action == "extract_text":
            return {"action": action, "selector": "body", "selector_type": "css", "to_var": "text"}
        if action == "http_request":
            return {"action": action, "method": "GET", "value": "https://example.com", "response_var": "response"}
        if action == "compare":
            return {"action": action, "left_var": "variable", "op": "equals", "value": "value"}
        if action == "new_tab":
            return {"action": action, "value": "https://example.com"}
        if action in {"switch_tab", "close_tab"}:
            return {"action": action, "tab_index": 0}
        if action == "set_tag":
            return {"action": action, "value": "tag"}
        if action == "run_scenario":
            return {"action": action, "scenario": ""}
        if action == "log":
            return {"action": action, "message": "message", "value": "message"}
        if action == "write_file":
            return {"action": action, "filename": "output.txt", "value": "{{variable}}"}
        return {"action": action}

    @pyqtSlot()
    def runSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("operator"):
            return
        if not self._selected_name:
            self._emit_message("Select scenario first")
            return
        self._save_current()
        scenario = self._get_scenario(self._selected_name)
        if not scenario:
            self._emit_message("Select scenario first")
            return
        if server_enabled() and self._profiles_bridge is not None and hasattr(self._profiles_bridge, "_server_accounts"):
            all_accounts = self._profiles_bridge._server_accounts()
        else:
            all_accounts = db_get_accounts()
        if self._run_profile:
            accounts = [acc for acc in all_accounts if str(acc.get("name") or "") == self._run_profile]
        else:
            accounts = all_accounts[:1]
        if not accounts:
            self._emit_message("Select profile to run")
            return

        def worker() -> None:
            started = time.monotonic()
            run_ids = self._create_cloud_runs(scenario, accounts)
            try:
                scenario_path = None if server_enabled() else db_get_scenario_path(scenario.name)
                processed = run_scenario(accounts, scenario, max_accounts=1, scenario_path=scenario_path)
                self._finish_cloud_runs(run_ids, accounts, processed, started)
                self._emit_message(f"Scenario finished: {len(processed)} profile(s)")
            except Exception as exc:
                LOGGER.exception("Scenario run failed")
                self._fail_cloud_runs(run_ids, started, exc)
                self._emit_message(f"Scenario failed: {exc}")
            finally:
                self._refresh_runs()

        self._emit_message(f"Running {scenario.name}")
        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(str, str, int)
    def runForTag(self, tag: str, scenario_name: str, max_accounts: int) -> None:  # noqa: N802
        if not self._ensure_allowed("operator"):
            return
        tag = str(tag or "").strip()
        scenario_name = str(scenario_name or self._selected_name or "").strip()
        if tag == "All tags":
            tag = ""
        if not scenario_name:
            self._emit_message("Select scenario first")
            return
        scenario = self._get_scenario(scenario_name)
        if not scenario:
            self._emit_message("Scenario not found")
            return
        try:
            limit = max(1, int(max_accounts or 1))
        except Exception:
            limit = 1
        if server_enabled() and self._profiles_bridge is not None and hasattr(self._profiles_bridge, "_server_accounts"):
            all_accounts = self._profiles_bridge._server_accounts()
        else:
            all_accounts = db_get_accounts()
        accounts = [
            acc for acc in all_accounts
            if not tag or str(acc.get("stage") or "No tag") == tag
        ]
        if not accounts:
            self._emit_message("No profiles for selected tag")
            return

        def worker() -> None:
            started = time.monotonic()
            run_ids = self._create_cloud_runs(scenario, accounts[:limit])
            try:
                scenario_path = None if server_enabled() else db_get_scenario_path(scenario.name)
                processed = run_scenario(
                    accounts,
                    scenario,
                    max_accounts=limit,
                    scenario_path=scenario_path,
                )
                self._finish_cloud_runs(run_ids, accounts[:limit], processed, started)
                self._emit_message(f"Scenario finished: {len(processed)} profile(s)")
            except Exception as exc:
                LOGGER.exception("Scenario batch run failed")
                self._fail_cloud_runs(run_ids, started, exc)
                self._emit_message(f"Scenario failed: {exc}")
            finally:
                self._refresh_runs()

        self._emit_message(f"Running {scenario.name} for {tag or 'all tags'}")
        threading.Thread(target=worker, daemon=True).start()

    def _create_cloud_runs(self, scenario: Scenario, accounts: List[Dict[str, Any]]) -> Dict[str, str]:
        client = self._server_client()
        if not (server_enabled() and client):
            return {}
        scenario_id = self._server_scenario_ids.get(scenario.name, "")
        run_ids: Dict[str, str] = {}
        for acc in accounts:
            profile_name = str(acc.get("name") or "")
            try:
                run = client.create_scenario_run({
                    "scenario_id": scenario_id or None,
                    "profile_id": str(acc.get("id") or "") or None,
                    "scenario_name": scenario.name,
                    "profile_name": profile_name,
                    "logs": {"source": "desktop"},
                })
                run_ids[profile_name] = str(run.get("id") or "")
            except ServerClientError as exc:
                self._emit_message(f"Cannot create scenario run: {exc}")
        self._refresh_runs()
        return run_ids

    def _finish_cloud_runs(
        self,
        run_ids: Dict[str, str],
        accounts: List[Dict[str, Any]],
        processed: List[Dict[str, Any]],
        started: float,
    ) -> None:
        if not run_ids:
            return
        processed_names = {str(acc.get("name") or "") for acc in processed}
        duration_ms = int((time.monotonic() - started) * 1000)
        client = self._server_client()
        if not client:
            return
        for acc in accounts:
            name = str(acc.get("name") or "")
            run_id = run_ids.get(name)
            if not run_id:
                continue
            status = "success" if name in processed_names else "failed"
            error = "" if status == "success" else "Scenario returned unsuccessful result"
            try:
                client.update_scenario_run(run_id, {
                    "status": status,
                    "error": error,
                    "duration_ms": duration_ms,
                    "logs": {"processed": status == "success"},
                })
            except ServerClientError as exc:
                self._emit_message(f"Cannot update scenario run: {exc}")

    def _fail_cloud_runs(self, run_ids: Dict[str, str], started: float, exc: Exception) -> None:
        if not run_ids:
            return
        duration_ms = int((time.monotonic() - started) * 1000)
        client = self._server_client()
        if not client:
            return
        for run_id in run_ids.values():
            if not run_id:
                continue
            try:
                client.update_scenario_run(run_id, {
                    "status": "failed",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                    "logs": {"exception": type(exc).__name__},
                })
            except ServerClientError:
                continue
