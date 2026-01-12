"""Profile and account list helpers."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, cast
import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import weakref
from PyQt6.QtCore import QPoint, Qt, QSize
from PyQt6.QtGui import QBrush, QFont, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from app.utils.parsing import DEFAULT_ACCOUNT_TEMPLATE, parse_account_line
from app.storage.db import (
    cleanup_profiles,
    clear_profile_cookies,
    db_add_account,
    db_delete_account,
    db_get_accounts,
    db_get_scenario,
    db_update_account,
    db_update_stage,
    delete_profile_for_account,
    profile_dir_for_email,
)


class AccountsMixin:
    def _open_import_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add profiles")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        intro = QLabel("Paste accounts below (one per line). Templates define placeholder order.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        accounts_input = QTextEdit()
        accounts_input.setPlaceholderText("email;password;secret_key;extra;twofa_url")
        layout.addWidget(accounts_input)

        template_label = QLabel("Account parse template")
        template_label.setProperty("class", "muted")
        layout.addWidget(template_label)
        template_input = QLineEdit(self.account_parse_template)
        layout.addWidget(template_input)

        selectors = QHBoxLayout()
        selectors.addWidget(QLabel("Default tag"))
        stage_combo = QComboBox()
        stage_combo.addItem("")
        for st in sorted(self.stages):
            stage_combo.addItem(st)
        selectors.addWidget(stage_combo, 1)

        selectors.addWidget(QLabel("Proxy pool"))
        pool_combo = QComboBox()
        pool_combo.addItem("No proxy pool", "")
        for name, pool in sorted(self.proxy_pools.items()):
            free = sum(1 for entry in pool.get("proxies", []) if not entry.get("assigned_to"))
            pool_combo.addItem(f"{name} ({free} free)", name)
        selectors.addWidget(pool_combo, 1)
        layout.addLayout(selectors)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(buttons)

        def submit() -> None:
            template_value = template_input.text().strip() or self.account_parse_template
            text = accounts_input.toPlainText()
            stage_value = stage_combo.currentText().strip()
            pool_value = pool_combo.currentData()
            pool_text = pool_combo.currentText().strip()
            pool_choice = pool_value if isinstance(pool_value, str) else pool_text
            result = self._import_accounts(text, stage_value, pool_choice, template_value)
            if result is None:
                return
            added, skipped, remaining = result
            msg = f"Added {added} profiles."
            if skipped:
                msg += f" Skipped {skipped} duplicates."
            if pool_choice and remaining:
                msg += f" {len(remaining)} profiles need proxies in pool {pool_choice}."
            QMessageBox.information(self, "Import complete", msg)
            if remaining:
                accounts_input.setPlainText("\n".join(remaining))
            else:
                accounts_input.clear()
                dlg.accept()

        buttons.accepted.connect(submit)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def refresh_accounts_list(self) -> None:
        accounts = db_get_accounts()
        cleanup_profiles(accounts)
        snapshot: List[Dict[str, object]] = []
        undefined = 0
        for idx, acc in enumerate(accounts):
            acc_id = str(acc.get("name") or f"account{idx+1}")
            proxy_host = acc.get("proxy_host")
            proxy_port = acc.get("proxy_port")
            proxy_user = acc.get("proxy_user")
            proxy_password = acc.get("proxy_password")
            if proxy_host and proxy_port:
                proxy_info = f"{proxy_host}:{proxy_port}:{proxy_user or ''}:{proxy_password or ''}"
            else:
                proxy_info = "-"
            scenario = acc.get("stage") or "-"
            if not acc.get("stage"):
                undefined += 1
            # show parsed variables (short) inline
            parsed_preview = []
            for key, val in acc.items():
                if key in {"stage", "proxy_host", "proxy_port", "proxy_user", "proxy_password", "extra_fields", "name", "camoufox_settings"}:
                    continue
                if val:
                    parsed_preview.append(f"{key}={val}")
            preview_str = "; ".join(parsed_preview)
            display = f"{acc_id} {proxy_info}  |  tag {scenario}"
            if preview_str:
                display += f"  |  {preview_str}"
            search_blob = f"{acc_id} {proxy_info} {scenario} {preview_str}".lower()
            snapshot.append({"account": dict(acc), "search": search_blob})
        self._accounts_snapshot = snapshot
        if hasattr(self, "profile_count_label"):
            self.profile_count_label.setText(f"{len(snapshot)} profiles")
        if hasattr(self, "profile_status_label"):
            self.profile_status_label.setText(f"{undefined} undefined")
        self._apply_accounts_filter()
        self._refresh_delete_tag_combo()

    def _refresh_delete_tag_combo(self) -> None:
        combo = getattr(self, "delete_tag_combo", None)
        if combo is None:
            return
        accounts = db_get_accounts()
        counts: Dict[str, int] = {}
        for acc in accounts:
            tag = str(acc.get("stage") or "")
            counts[tag] = counts.get(tag, 0) + 1
        current = combo.currentData() if combo.count() else None
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Select tag", None)
        for tag in sorted(t for t in counts.keys() if t):
            combo.addItem(f"{tag} ({counts[tag]})", tag)
        if "" in counts:
            combo.addItem(f"No tag ({counts['']})", "")
        if current is not None:
            for idx in range(combo.count()):
                if combo.itemData(idx) == current:
                    combo.setCurrentIndex(idx)
                    break
        combo.blockSignals(False)

    def _is_account_running(self, account_name: str) -> bool:
        try:
            live = getattr(self, "live_browsers", {}) or {}
            return str(account_name or "") in live
        except Exception:
            return False

    def _build_account_row_widget(self, acc: Dict[str, object], item: QListWidgetItem) -> QWidget:
        row = QWidget()
        row.setObjectName("profileRow")
        row.setMinimumHeight(70)
        row.setProperty("selected", False)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(24)

        avatar = QLabel((str(acc.get("name") or "PF")[:2]).upper())
        avatar.setFixedSize(20, 20)
        avatar.setProperty("class", "avatarBadge")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_block = QHBoxLayout()
        name_block.setSpacing(12)
        name_block.addWidget(avatar)
        name_meta = QVBoxLayout()
        name_meta.setSpacing(2)
        primary_name = QLabel(str(acc.get("name") or "Profile"))
        primary_name.setProperty("class", "cardTitle")
        name_meta.addWidget(primary_name)
        subtitle = acc.get("description") or "No description"
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("class", "muted")
        name_meta.addWidget(subtitle_label)
        name_meta.addStretch(1)
        name_block.addLayout(name_meta)
        row_layout.addLayout(name_block, 3)

        account_name = str(acc.get("name") or "")
        proxy_host = str(acc.get("proxy_host") or "")
        proxy_port = str(acc.get("proxy_port") or "")
        proxy_user = str(acc.get("proxy_user") or "")
        proxy_password = str(acc.get("proxy_password") or "")
        pool_name = str(acc.get("proxy_pool") or "—")
        has_proxy = bool(proxy_host and proxy_port)
        if has_proxy:
            proxy_label = f"{proxy_host}:{proxy_port}"
            auth_label = f"{proxy_user or '—'}:{proxy_password or '—'}"
        else:
            proxy_label = "No proxy"
            auth_label = "No authentication"
        proxy_col = QVBoxLayout()
        proxy_col.setSpacing(2)
        proxy_row = QHBoxLayout()
        proxy_row.setSpacing(8)
        proxy_main = QLabel(proxy_label)
        proxy_main.setProperty("class", "cardTitle")
        proxy_row.addWidget(proxy_main)
        pool_label = QLabel(pool_name)
        pool_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        pool_label.setProperty("class", "pillLabel")
        proxy_row.addWidget(pool_label, 0)
        proxy_row.addStretch(1)
        proxy_col.addLayout(proxy_row)
        proxy_secondary = QLabel(auth_label)
        proxy_secondary.setProperty("class", "muted")
        proxy_col.addWidget(proxy_secondary)
        proxy_col.addStretch(1)
        row_layout.addLayout(proxy_col, 2)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(12)
        tags_row.setContentsMargins(0, 0, 0, 0)
        tags_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        stage = str(acc.get("stage") or "No tag")
        tag_label = QLabel(stage)
        tag_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        tag_label.setProperty("class", "tagLabel")
        tags_row.addWidget(tag_label, 0)
        tags_row.addStretch(1)
        row_layout.addLayout(tags_row, 2)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addStretch(1)
        action_btn = QPushButton("Start")
        action_btn.setProperty("class", "primary")
        action_btn.setFixedHeight(32)
        action_btn.clicked.connect(
            lambda _, name=account_name, btn=action_btn: self._handle_account_start_click(name, btn)
        )
        actions_row.addWidget(action_btn)
        if not hasattr(self, "_account_action_buttons"):
            self._account_action_buttons = {}
        self._account_action_buttons[str(account_name or "").lower()] = weakref.ref(action_btn)
        if self._is_account_running(account_name):
            self._set_account_action_button_state(account_name, "running")
        more_btn = QPushButton()
        icon_color = more_btn.palette().color(QPalette.ColorRole.ButtonText)
        icon_size = 14
        dot_radius = 2
        spacing = 5
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QBrush(icon_color))
        painter.setPen(Qt.PenStyle.NoPen)
        center_y = icon_size // 2
        center_x = icon_size // 2
        for offset in (-spacing, 0, spacing):
            painter.drawEllipse(center_x + offset - dot_radius, center_y - dot_radius, dot_radius * 2, dot_radius * 2)
        painter.end()
        more_btn.setIcon(QIcon(pixmap))
        more_btn.setIconSize(QSize(icon_size, icon_size))
        more_btn.setProperty("class", "ghost iconButton")
        more_btn.setFixedWidth(36)
        more_btn.setFixedHeight(32)
        more_btn.clicked.connect(
            lambda _, name=str(acc.get("name") or ""), btn=more_btn: self._open_account_menu(name, btn.mapToGlobal(btn.rect().bottomRight()))
        )
        actions_row.addWidget(more_btn)
        row_layout.addLayout(actions_row, 1)
        row.installEventFilter(self)
        self._account_row_widgets[row] = item
        return row

    def _handle_account_start_click(self, account_name: str, button: QPushButton) -> None:
        if not account_name:
            return
        self._set_account_action_button_state(account_name, "launching")
        self.open_browser_for_account(account_name)

    def _set_account_action_button_state(self, account_name: str, state: str) -> None:
        key = str(account_name or "").lower()
        ref = getattr(self, "_account_action_buttons", {}).get(key)
        btn = ref() if ref else None
        if btn is None:
            return
        state = (state or "").strip().lower()
        if state == "running":
            btn.setText("Running")
            btn.setEnabled(False)
            btn.setProperty("class", "ghost")
        elif state == "launching":
            btn.setText("Launching")
            btn.setEnabled(False)
            btn.setProperty("class", "primary")
        else:
            btn.setText("Start")
            btn.setEnabled(True)
            btn.setProperty("class", "primary")
        style = btn.style()
        if style is not None:
            style.unpolish(btn)
            style.polish(btn)
        btn.update()

    def _update_row_selection_styles(self) -> None:
        if not hasattr(self, "accounts_list"):
            return
        for widget, item in self._account_row_widgets.items():
            selected = bool(item.isSelected())
            widget.setProperty("selected", selected)
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
            widget.update()

    def _apply_accounts_filter(self) -> None:
        if not hasattr(self, "accounts_list"):
            return
        query = ""
        if hasattr(self, "accounts_search_input"):
            query = self.accounts_search_input.text().strip().lower()
        stage_filter = (self._active_stage_filter or "").strip().lower() if self._active_stage_filter else ""
        for widget in list(self._account_row_widgets.keys()):
            widget.removeEventFilter(self)
        self._account_row_widgets = {}
        self._account_action_buttons = {}
        self.accounts_list.clear()
        for record in self._accounts_snapshot:
            acc = record.get("account") or {}
            blob = str(record.get("search") or "")
            if query and query not in blob:
                continue
            scenario_value = str(acc.get("stage") or "").lower()
            if stage_filter and scenario_value != stage_filter:
                continue
            acc_id = str(acc.get("name") or "")
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, acc_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, acc.get("stage"))
            row_widget = self._build_account_row_widget(acc, item)
            item.setSizeHint(row_widget.sizeHint())
            self.accounts_list.addItem(item)
            self.accounts_list.setItemWidget(item, row_widget)
        self._update_row_selection_styles()

    def _import_accounts(
        self,
        accounts_raw: str,
        stage_name: Optional[str],
        pool_name: Optional[str],
        template: Optional[str] = None,
    ) -> Optional[Tuple[int, int, List[str]]]:
        accounts_raw = (accounts_raw or "").strip()
        if not accounts_raw:
            QMessageBox.warning(self, "Error", "No accounts provided")
            return None

        acc_lines = [line.strip() for line in accounts_raw.splitlines() if line.strip()]
        stage_name = (stage_name or "").strip() or None
        pool_name = (pool_name or "").strip() or None

        template_value = (template or self.account_parse_template or DEFAULT_ACCOUNT_TEMPLATE).strip()
        if not template_value:
            template_value = DEFAULT_ACCOUNT_TEMPLATE
        self._save_account_template(template_value)

        added = 0
        skipped = 0
        remaining: List[str] = []

        for idx, line in enumerate(acc_lines):
            try:
                account = parse_account_line(line, template_value)
            except ValueError as e:
                QMessageBox.warning(self, "Account line error", f"{e}\nLine:\n{line}")
                return None

            account["stage"] = stage_name or account.get("stage")

            try:
                created = db_add_account(account)
            except Exception:
                skipped += 1
                continue

            assigned = True
            if pool_name:
                assigned = self._assign_proxy_to_account_from_pool(str(created.get("name")), pool_name)
                if not assigned:
                    db_delete_account(str(created.get("name")))
                    remaining = acc_lines[idx:]
                    break

            if assigned:
                added += 1

        self.refresh_accounts_list()
        self.log(f"Added accounts: {added}, skipped (duplicates): {skipped}")
        return added, skipped, remaining

    def _get_selected_names(self) -> List[str]:
        names: List[str] = []
        for item in self.accounts_list.selectedItems():
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                names.append(name)
        return names

    def _show_account_context_menu(self, pos) -> None:
        item = self.accounts_list.itemAt(pos)
        if item is None:
            return
        account_name = item.data(Qt.ItemDataRole.UserRole) or item.text().split("|")[0].strip()
        self._open_account_menu(str(account_name), self.accounts_list.mapToGlobal(pos))

    def _open_account_menu(self, account_name: str, global_pos: QPoint) -> None:
        if not account_name:
            return
        menu = QMenu(self)
        act_info = menu.addAction("Profile settings")
        act_open = menu.addAction("Open browser")
        act_delete = menu.addAction("Delete account")
        act_clear_profile = menu.addAction("Clear profile")
        assign_stage_menu = menu.addMenu("Assign tag")
        stage_actions: Dict[object, str] = {}
        for st in self.stages:
            act = assign_stage_menu.addAction(st)
            stage_actions[act] = st
        act_clear_stage = assign_stage_menu.addAction("Clear tag")
        run_menu = menu.addMenu("Run scenario")
        run_actions: Dict[object, str] = {}
        for scenario in self.scenarios_cache:
            act = run_menu.addAction(scenario.name)
            run_actions[act] = scenario.name
        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen == act_info:
            self._show_profile_settings(account_name)
            return
        if chosen == act_open:
            self.open_browser_for_account(account_name)
            return
        if chosen == act_delete:
            self._delete_account(account_name)
            return
        if chosen == act_clear_profile:
            self._clear_profile_data(account_name)
            return
        if chosen == act_clear_stage:
            db_update_stage(account_name, None)
            self.refresh_accounts_list()
            self.log(f"Account {account_name} tag cleared")
            return
        if chosen in stage_actions:
            db_update_stage(account_name, stage_actions[chosen])
            self.refresh_accounts_list()
            self.log(f"Account {account_name} tag -> {stage_actions[chosen]}")
            return
        if chosen in run_actions:
            scenario = db_get_scenario(run_actions[chosen])
            if not scenario:
                QMessageBox.warning(self, "Error", f"Scenario {run_actions[chosen]} not found")
                return
            acc = next((a for a in db_get_accounts() if str(a.get("name") or "") == account_name), None)
            if not acc:
                QMessageBox.warning(self, "Error", f"Account {account_name} not found")
                return
            self.log(f"Run scenario {scenario.name} for {account_name}")
            self._run_scenario_async([acc], scenario, f"account {account_name}")
            return

    def _delete_account(self, account_name: str) -> None:
        self._release_proxy_for_account(account_name)
        db_delete_account(account_name)
        delete_profile_for_account(account_name)
        self.refresh_accounts_list()
        self.log(f"Deleted account {account_name}")

    def _delete_profiles_by_tag(self) -> None:
        combo = getattr(self, "delete_tag_combo", None)
        tag_data = combo.currentData() if combo else None
        if tag_data is None:
            QMessageBox.warning(self, "Error", "Select a tag to delete")
            return
        stage_target = "" if tag_data == "" else str(tag_data)
        tag_name = "No tag" if stage_target == "" else stage_target
        accounts = db_get_accounts()
        matches = [acc for acc in accounts if str(acc.get("stage") or "") == stage_target]
        if not matches:
            QMessageBox.warning(self, "Error", f"No profiles with tag {tag_name}")
            return
        running: List[str] = []
        to_delete: List[str] = []
        for acc in matches:
            name = str(acc.get("name") or "")
            if not name:
                continue
            if self._is_account_running(name):
                running.append(name)
                continue
            to_delete.append(name)
        if not to_delete:
            QMessageBox.warning(self, "Error", f"All profiles with tag {tag_name} are running")
            return
        delete_proxies = bool(getattr(self, "delete_tag_proxy_check", None) and self.delete_tag_proxy_check.isChecked())
        proxy_note = "This releases proxies back to the pool." if not delete_proxies else "This removes proxies from the pool."
        details = f"Delete {len(to_delete)} profiles with tag {tag_name}? {proxy_note}"
        if running:
            details += f"\n{len(running)} running profiles will be skipped."
        confirm = QMessageBox.question(self, "Delete profiles", details)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for name in to_delete:
            if delete_proxies:
                if not self._remove_proxy_for_account(name):
                    QMessageBox.warning(self, "Error", "Delete aborted. Fix permissions and try again.")
                    return
            else:
                self._release_proxy_for_account(name)
            db_delete_account(name)
            delete_profile_for_account(name)
        self.refresh_accounts_list()
        self.log(f"Deleted {len(to_delete)} profiles with tag {tag_name}")
        if running:
            self.log(f"Skipped {len(running)} running profiles with tag {tag_name}")

    def _clear_account_cookies(self, account_name: str) -> None:
        try:
            cleared = clear_profile_cookies(account_name)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Cannot clear cookies for {account_name}: {exc}")
            return
        message = "Cookies cleared" if cleared else "No cookies to clear"
        self.log(f"{message} for {account_name}")

    def _clear_profile_data(self, account_name: str) -> None:
        if self._is_account_running(account_name):
            QMessageBox.warning(self, "Error", f"Profile {account_name} is running. Close it first.")
            return
        confirm = QMessageBox.question(
            self,
            "Clear profile",
            f"Delete profile data for {account_name}? This removes the profile folder.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            cleared = clear_profile_cookies(account_name)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Cannot clear profile for {account_name}: {exc}")
            return
        if cleared:
            self.log(f"Profile data cleared for {account_name}")
        else:
            self.log(f"No profile data to clear for {account_name}")

    def _camoufox_ui_values_for_account(self, acc: Dict[str, object]) -> Dict[str, object]:
        return dict(self._camoufox_settings_for_account(acc))

    @staticmethod
    def _cookie_key(cookie: Dict[str, object]) -> Tuple[str, str, str]:
        return (
            str(cookie.get("domain") or ""),
            str(cookie.get("name") or ""),
            str(cookie.get("path") or "/"),
        )

    def _fetch_profile_cookies_via_camoufox(self, account_name: str) -> List[Dict[str, object]]:
        import asyncio

        async def _run() -> List[Dict[str, object]]:
            from camoufox import AsyncCamoufox
            from app.core.camoufox_profile_fingerprint import load_or_create_profile_fingerprint

            user_data_dir_path = profile_dir_for_email(account_name)
            user_data_dir = str(user_data_dir_path)
            fp = load_or_create_profile_fingerprint(user_data_dir_path)
            ctx = AsyncCamoufox(
                headless=True,
                persistent_context=True,
                user_data_dir=user_data_dir,
                enable_cache=True,
                i_know_what_im_doing=True,
                fingerprint=fp,
            )
            result = await ctx.__aenter__()
            context = result
            try:
                cookies = await context.cookies()
                return [dict(c) for c in (cookies or [])]
            finally:
                await ctx.__aexit__(None, None, None)

        return asyncio.run(_run())

    def _write_profile_cookies_via_camoufox(self, account_name: str, cookies: List[Dict[str, object]]) -> None:
        import asyncio

        async def _run() -> None:
            from camoufox import AsyncCamoufox
            from app.core.camoufox_profile_fingerprint import load_or_create_profile_fingerprint

            user_data_dir_path = profile_dir_for_email(account_name)
            user_data_dir = str(user_data_dir_path)
            fp = load_or_create_profile_fingerprint(user_data_dir_path)
            ctx = AsyncCamoufox(
                headless=True,
                persistent_context=True,
                user_data_dir=user_data_dir,
                enable_cache=True,
                i_know_what_im_doing=True,
                fingerprint=fp,
            )
            result = await ctx.__aenter__()
            context = result
            try:
                await context.clear_cookies()
                payload: List[Dict[str, object]] = []
                for cookie in cookies or []:
                    if not isinstance(cookie, dict):
                        continue
                    name = str(cookie.get("name") or "").strip()
                    value = str(cookie.get("value") or "")
                    domain = str(cookie.get("domain") or "").strip()
                    path = str(cookie.get("path") or "/").strip() or "/"
                    if not name or not domain:
                        continue
                    item: Dict[str, object] = {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                    }
                    for key in ("expires", "httpOnly", "secure", "sameSite"):
                        if key in cookie:
                            item[key] = cookie.get(key)
                    payload.append(item)
                if payload:
                    await context.add_cookies(payload)
            finally:
                await ctx.__aexit__(None, None, None)

        asyncio.run(_run())

    @staticmethod
    def _format_cookie_expiry(value: object, source: str) -> str:
        try:
            if value in (None, "", 0):
                return ""
            if source == "firefox":
                ts = int(value)
                return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat(timespec="seconds")
            if source == "chromium":
                # microseconds since 1601-01-01 UTC
                micros = int(value)
                if micros <= 0:
                    return ""
                epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
                return (epoch + datetime.timedelta(microseconds=micros)).isoformat(timespec="seconds")
        except Exception:
            return ""
        return ""

    def _read_sqlite_rows(self, db_path: str, query: str, params: Tuple[object, ...] = ()) -> List[Tuple]:
        # Cookies DB may be locked when a browser is running; read from a temp copy when needed.
        source_path = db_path
        tmp_path: Optional[str] = None
        try:
            try:
                uri = f"file:{source_path}?mode=ro"
                con = sqlite3.connect(uri, uri=True, timeout=1.0)
            except Exception:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
                tmp_path = tmp.name
                tmp.close()
                shutil.copy2(source_path, tmp_path)
                uri = f"file:{tmp_path}?mode=ro"
                con = sqlite3.connect(uri, uri=True, timeout=1.0)
            try:
                cur = con.cursor()
                cur.execute(query, params)
                return list(cur.fetchall())
            finally:
                con.close()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _load_profile_cookies(self, account_name: str) -> List[Dict[str, object]]:
        profile_dir = profile_dir_for_email(account_name)
        if not profile_dir.exists():
            return []
        candidates = [
            ("firefox", profile_dir / "cookies.sqlite"),
            ("chromium", profile_dir / "Cookies"),
            ("chromium", profile_dir / "Network" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Network" / "Cookies"),
        ]
        # De-duplicate and keep existing.
        seen: set[str] = set()
        paths: List[Tuple[str, str]] = []
        for source, path in candidates:
            p = str(path)
            if p in seen:
                continue
            seen.add(p)
            if path.exists() and path.is_file():
                paths.append((source, p))
        # Fallback: scan for a few common cookie db names.
        if not paths:
            for path in profile_dir.rglob("cookies.sqlite"):
                p = str(path)
                if p not in seen and path.is_file():
                    paths.append(("firefox", p))
                    seen.add(p)
            for path in profile_dir.rglob("Cookies"):
                p = str(path)
                if p not in seen and path.is_file():
                    paths.append(("chromium", p))
                    seen.add(p)

        out: List[Dict[str, object]] = []
        for source, db_path in paths:
            try:
                if source == "firefox":
                    rows = self._read_sqlite_rows(
                        db_path,
                        "SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies",
                    )
                    for host, name, value, path, expiry, is_secure, is_http_only in rows:
                        out.append(
                            {
                                "source": source,
                                "domain": host,
                                "name": name,
                                "value": value,
                                "path": path,
                                "expires": self._format_cookie_expiry(expiry, source),
                                "secure": bool(is_secure),
                                "http_only": bool(is_http_only),
                            }
                        )
                else:
                    rows = self._read_sqlite_rows(
                        db_path,
                        "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly FROM cookies",
                    )
                    for host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_http_only in rows:
                        cookie_value = value
                        if (cookie_value is None or cookie_value == "") and encrypted_value:
                            cookie_value = "<encrypted>"
                        out.append(
                            {
                                "source": source,
                                "domain": host_key,
                                "name": name,
                                "value": cookie_value,
                                "path": path,
                                "expires": self._format_cookie_expiry(expires_utc, source),
                                "secure": bool(is_secure),
                                "http_only": bool(is_http_only),
                            }
                        )
            except Exception as exc:
                self.log(f"Cookie read failed for {account_name}: {exc}")
                continue
        return out

    def _show_profile_settings(self, account_name: str) -> None:
        acc = next((a for a in db_get_accounts() if str(a.get("name") or "") == account_name), None)
        if not acc:
            QMessageBox.warning(self, "Error", f"Account {account_name} not found")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Profile settings — {account_name}")
        dlg.setSizeGripEnabled(False)
        dlg.setWindowTitle(f"Profile settings - {account_name}")
        layout = QVBoxLayout(dlg)
        tabs = QTabWidget(dlg)
        layout.addWidget(tabs, 1)

        # Variables tab
        vars_tab = QWidget(tabs)
        vars_layout = QVBoxLayout(vars_tab)
        vars_scroll = QScrollArea(vars_tab)
        vars_scroll.setWidgetResizable(True)
        vars_container = QWidget(vars_scroll)
        vars_container_layout = QVBoxLayout(vars_container)
        form = QFormLayout()
        vars_container_layout.addLayout(form)
        vars_scroll.setWidget(vars_container)
        vars_layout.addWidget(vars_scroll, 1)

        name_input = QLineEdit(str(acc.get("name") or ""))
        form.addRow("Profile name (ID):", name_input)

        fields: List[Tuple[str, QLineEdit, QPushButton, QHBoxLayout]] = []
        fields_layout = QVBoxLayout()
        form.addRow(fields_layout)

        def add_field_row(key: str, value: str = "") -> None:
            val_edit = QLineEdit(value)
            del_btn = QPushButton("Remove")
            row = QHBoxLayout()
            row.addWidget(QLabel(key))
            row.addWidget(val_edit)
            row.addWidget(del_btn)
            fields_layout.addLayout(row)
            fields.append((key, val_edit, del_btn, row))

            def remove_row():
                # remove widgets from layout and list
                while row.count():
                    item = row.takeAt(0)
                    w = item.widget()
                    if w:
                        w.setParent(None)
                fields_layout.removeItem(row)
                fields[:] = [(k, v, b, r) for (k, v, b, r) in fields if b is not del_btn]
                removed_keys.add(key)

            del_btn.clicked.connect(remove_row)

        for key, val in sorted(acc.items()):
            if key == "name":
                continue
            add_field_row(str(key), "" if val is None else str(val))

        btn_add_field = QPushButton("Add var")
        vars_container_layout.addWidget(btn_add_field)

        removed_keys: set[str] = set()

        def on_add_field():
            # prompt for new key
            key, ok = QInputDialog.getText(self, "New variable", "Variable name:")
            if not ok:
                return
            key = key.strip()
            if not key:
                return
            # avoid duplicates
            existing = {k for k, _, _, _ in fields}
            if key in existing or key == "name":
                QMessageBox.warning(self, "Error", "Variable already exists or reserved")
                return
            add_field_row(key, "")

        btn_add_field.clicked.connect(on_add_field)

        vars_container_layout.addStretch()
        tabs.addTab(vars_tab, "Variables")

        # Camoufox tab
        cam_tab = QWidget(tabs)
        cam_layout = QVBoxLayout(cam_tab)
        cam_scroll = QScrollArea(cam_tab)
        cam_scroll.setWidgetResizable(True)
        cam_container = QWidget(cam_scroll)
        cam_container_layout = QVBoxLayout(cam_container)
        cam_scroll.setWidget(cam_container)
        cam_layout.addWidget(cam_scroll, 1)
        cam_info = QLabel("Override defaults for this profile. Leave values on Auto to inherit global settings.")
        cam_info.setWordWrap(True)
        cam_container_layout.addWidget(cam_info)
        cam_controls, cam_tabs_widget = self._build_camoufox_controls(dlg)
        cam_actions = QHBoxLayout()
        cam_actions.addStretch(1)
        cam_container_layout.addLayout(cam_actions)
        cam_container_layout.addWidget(cam_tabs_widget, 1)
        cam_buttons = QDialogButtonBox()
        cam_defaults_btn = QPushButton("Use defaults", dlg)
        cam_buttons.addButton(cam_defaults_btn, QDialogButtonBox.ButtonRole.ResetRole)
        cam_container_layout.addWidget(cam_buttons)

        effective_values = self._camoufox_ui_values_for_account(acc)
        self._apply_camoufox_controls(cam_controls, effective_values)
        def clear_camoufox_override() -> None:
            self._apply_camoufox_controls(cam_controls, getattr(self, "camoufox_defaults", {}))

        cam_defaults_btn.clicked.connect(clear_camoufox_override)
        cam_container_layout.addStretch()
        tabs.addTab(cam_tab, "Camoufox")

        # Cookies tab
        cookies_tab = QWidget(tabs)
        cookies_layout = QVBoxLayout(cookies_tab)
        cookies_title = QLabel("Cookies for this profile")
        cookies_title.setProperty("class", "cardTitle")
        cookies_layout.addWidget(cookies_title)
        cookies_hint = QLabel("Chromium profiles may store encrypted cookie values on Windows.")
        cookies_hint.setProperty("class", "muted")
        cookies_layout.addWidget(cookies_hint)

        cookies_table = QTableWidget(0, 9, cookies_tab)
        cookies_table.setHorizontalHeaderLabels(
            ["Domain", "Name", "Value", "Path", "Expires (UTC)", "Secure", "HttpOnly", "SameSite", "Source"]
        )
        cookies_table.setWordWrap(False)
        cookies_table.setSortingEnabled(True)
        cookies_table.verticalHeader().setVisible(False)
        header = cookies_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Value
        cookies_layout.addWidget(cookies_table, 1)

        cookies_actions = QVBoxLayout()
        cookies_row1 = QHBoxLayout()
        cookies_row2 = QHBoxLayout()
        btn_refresh_cookies = QPushButton("Refresh", cookies_tab)
        cookies_row1.addWidget(btn_refresh_cookies)
        btn_copy_json = QPushButton("Copy JSON", cookies_tab)
        cookies_row1.addWidget(btn_copy_json)
        btn_import_json = QPushButton("Import JSON", cookies_tab)
        cookies_row1.addWidget(btn_import_json)

        cookies_row1.addStretch()
        btn_add_cookie = QPushButton("Add", cookies_tab)
        cookies_row2.addWidget(btn_add_cookie)
        btn_delete_selected = QPushButton("Delete selected", cookies_tab)
        cookies_row2.addWidget(btn_delete_selected)
        btn_clear_all = QPushButton("Clear all", cookies_tab)
        cookies_row2.addWidget(btn_clear_all)
        btn_save_cookies = QPushButton("Save cookies", cookies_tab)
        btn_save_cookies.setProperty("class", "primary")
        cookies_row1.addWidget(btn_save_cookies)
        cookies_row2.addStretch()

        cookies_actions.addLayout(cookies_row1)
        cookies_actions.addLayout(cookies_row2)
        cookies_layout.addLayout(cookies_actions)
        tabs.addTab(cookies_tab, "Cookies")

        cookies_state: List[Dict[str, object]] = []

        def _render_cookies() -> None:
            cookies_table.setSortingEnabled(False)
            cookies_table.setRowCount(0)
            for cookie in cookies_state:
                row = cookies_table.rowCount()
                cookies_table.insertRow(row)
                domain = str(cookie.get("domain") or cookie.get("host") or "")
                name = str(cookie.get("name") or "")
                value = str(cookie.get("value") or "")
                path = str(cookie.get("path") or "/")
                expires = cookie.get("expires")
                expires_text = ""
                if isinstance(expires, (int, float)) and expires:
                    try:
                        expires_text = datetime.datetime.fromtimestamp(float(expires), tz=datetime.timezone.utc).isoformat(
                            timespec="seconds"
                        )
                    except Exception:
                        expires_text = str(expires)
                secure_text = "Yes" if cookie.get("secure") else ""
                http_only_text = "Yes" if cookie.get("httpOnly") else ""
                same_site = str(cookie.get("sameSite") or "")
                source = str(cookie.get("source") or "camoufox")
                values = [
                    domain,
                    name,
                    value,
                    path,
                    expires_text,
                    secure_text,
                    http_only_text,
                    same_site,
                    source,
                ]
                for col, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if col in {0, 1, 3, 4, 5, 6, 7, 8}:
                        item.setFont(QFont("Segoe UI", 9))
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, self._cookie_key(cookie))
                    cookies_table.setItem(row, col, item)
            for col in (0, 1, 3, 4, 5, 6, 7, 8):
                cookies_table.resizeColumnToContents(col)
            cookies_table.setSortingEnabled(True)

        def _set_cookies_busy(is_busy: bool, label: str = "") -> None:
            for btn in (
                btn_refresh_cookies,
                btn_copy_json,
                btn_import_json,
                btn_add_cookie,
                btn_delete_selected,
                btn_clear_all,
                btn_save_cookies,
            ):
                btn.setEnabled(not is_busy)
            if is_busy:
                btn_refresh_cookies.setText(label or "Working...")
            else:
                btn_refresh_cookies.setText("Refresh")

        def load_cookies_async() -> None:
            def run() -> None:
                try:
                    cookies = self._fetch_profile_cookies_via_camoufox(account_name)
                except Exception as exc:
                    cookies = []

                    def fail() -> None:
                        _set_cookies_busy(False)
                        QMessageBox.warning(self, "Error", f"Cannot read cookies for {account_name}: {exc}")

                    self._invoke_ui(fail)
                    return

                def apply() -> None:
                    nonlocal cookies_state
                    cookies_state = cookies
                    _render_cookies()
                    _set_cookies_busy(False)

                self._invoke_ui(apply)

            _set_cookies_busy(True, "Loading...")
            threading.Thread(target=run, daemon=True).start()

        btn_refresh_cookies.clicked.connect(load_cookies_async)
        load_cookies_async()

        def copy_json() -> None:
            try:
                import json

                text = json.dumps(cookies_state, ensure_ascii=False, indent=2)
                clip = QGuiApplication.clipboard() if QGuiApplication.instance() else None
                if clip:
                    clip.setText(text)
                self.log(f"Copied {len(cookies_state)} cookies to clipboard (JSON)")
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Cannot copy JSON: {exc}")

        btn_copy_json.clicked.connect(copy_json)

        def import_json() -> None:
            dlg_json = QDialog(dlg)
            dlg_json.setWindowTitle("Import cookies (JSON)")
            dlg_layout = QVBoxLayout(dlg_json)
            editor = QTextEdit(dlg_json)
            editor.setPlaceholderText("Paste a JSON array of cookies here")
            clip = QGuiApplication.clipboard() if QGuiApplication.instance() else None
            if clip:
                editor.setPlainText(clip.text() or "")
            dlg_layout.addWidget(editor, 1)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            dlg_layout.addWidget(btns)

            def accept() -> None:
                try:
                    import json

                    data = json.loads(editor.toPlainText() or "[]")
                    if not isinstance(data, list):
                        raise ValueError("JSON must be an array")
                    cleaned: List[Dict[str, object]] = []
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        if not item.get("name") or not item.get("domain"):
                            continue
                        cleaned.append(dict(item))
                except Exception as exc:
                    QMessageBox.warning(dlg_json, "Error", f"Invalid JSON: {exc}")
                    return
                nonlocal cookies_state
                cookies_state = cleaned
                _render_cookies()
                dlg_json.accept()

            btns.accepted.connect(accept)
            btns.rejected.connect(dlg_json.reject)
            dlg_json.exec()

        btn_import_json.clicked.connect(import_json)

        def add_cookie() -> None:
            add_dlg = QDialog(dlg)
            add_dlg.setWindowTitle("Add cookie")
            form = QFormLayout(add_dlg)
            domain_in = QLineEdit(add_dlg)
            name_in = QLineEdit(add_dlg)
            value_in = QLineEdit(add_dlg)
            path_in = QLineEdit(add_dlg)
            path_in.setText("/")
            expires_in = QLineEdit(add_dlg)
            expires_in.setPlaceholderText("Unix timestamp seconds (optional)")
            secure_cb = QCheckBox(add_dlg)
            http_only_cb = QCheckBox(add_dlg)
            same_site_in = QComboBox(add_dlg)
            same_site_in.addItems(["", "Lax", "Strict", "None"])
            form.addRow("Domain", domain_in)
            form.addRow("Name", name_in)
            form.addRow("Value", value_in)
            form.addRow("Path", path_in)
            form.addRow("Expires", expires_in)
            form.addRow("Secure", secure_cb)
            form.addRow("HttpOnly", http_only_cb)
            form.addRow("SameSite", same_site_in)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            form.addRow(btns)

            def accept() -> None:
                domain = domain_in.text().strip()
                name = name_in.text().strip()
                if not domain or not name:
                    QMessageBox.warning(add_dlg, "Error", "Domain and Name are required")
                    return
                cookie: Dict[str, object] = {
                    "domain": domain,
                    "name": name,
                    "value": value_in.text(),
                    "path": path_in.text().strip() or "/",
                    "secure": bool(secure_cb.isChecked()),
                    "httpOnly": bool(http_only_cb.isChecked()),
                }
                exp_raw = expires_in.text().strip()
                if exp_raw:
                    try:
                        cookie["expires"] = float(exp_raw)
                    except Exception:
                        QMessageBox.warning(add_dlg, "Error", "Expires must be a unix timestamp (number)")
                        return
                same_site = same_site_in.currentText().strip()
                if same_site:
                    cookie["sameSite"] = same_site
                nonlocal cookies_state
                cookies_state.append(cookie)
                _render_cookies()
                add_dlg.accept()

            btns.accepted.connect(accept)
            btns.rejected.connect(add_dlg.reject)
            add_dlg.exec()

        btn_add_cookie.clicked.connect(add_cookie)

        def delete_selected() -> None:
            keys: set[Tuple[str, str, str]] = set()
            for item in cookies_table.selectedItems():
                if item.column() == 0:
                    key = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(key, tuple) and len(key) == 3:
                        keys.add(key)
            if not keys:
                return
            nonlocal cookies_state
            cookies_state = [c for c in cookies_state if self._cookie_key(c) not in keys]
            _render_cookies()

        btn_delete_selected.clicked.connect(delete_selected)

        def clear_all() -> None:
            nonlocal cookies_state
            cookies_state = []
            _render_cookies()

        btn_clear_all.clicked.connect(clear_all)

        def save_cookies() -> None:
            confirm = QMessageBox.question(
                dlg,
                "Save cookies",
                f"Overwrite profile cookies with {len(cookies_state)} cookies?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            def run() -> None:
                try:
                    self._write_profile_cookies_via_camoufox(account_name, cookies_state)
                except Exception as exc:
                    def fail() -> None:
                        _set_cookies_busy(False)
                        QMessageBox.warning(self, "Error", f"Cannot save cookies for {account_name}: {exc}")

                    self._invoke_ui(fail)
                    return

                def ok() -> None:
                    _set_cookies_busy(False)
                    self.log(f"Cookies saved for {account_name} ({len(cookies_state)} items)")
                    load_cookies_async()

                self._invoke_ui(ok)

            _set_cookies_busy(True, "Saving...")
            threading.Thread(target=run, daemon=True).start()

        btn_save_cookies.clicked.connect(save_cookies)

        def save():
            updates: Dict[str, object] = {"name": name_input.text().strip()}
            for key, val_edit, _, _ in fields:
                k = str(key).strip()
                if not k:
                    continue
                updates[k] = val_edit.text().strip()
            if removed_keys:
                updates["__delete_keys__"] = list(removed_keys)
            new_name = str(updates.get("name") or account_name)
            try:
                db_update_account(account_name, updates)
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Cannot update account: {exc}")
                return
            # Save camoufox overrides (if changed from defaults).
            try:
                overrides = self._collect_camoufox_controls(cam_controls)
                if overrides == getattr(self, "camoufox_defaults", overrides):
                    db_update_account(new_name, {"__delete_keys__": ["camoufox_settings"]})
                else:
                    db_update_account(new_name, {"camoufox_settings": overrides})
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Cannot save Camoufox settings: {exc}")
                return
            if new_name != account_name:
                self._rename_proxy_assignment(account_name, new_name)
            dlg.accept()
            self.refresh_accounts_list()
            self.log(f"Account {new_name} updated")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(save)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        screen = QGuiApplication.primaryScreen() if QGuiApplication.instance() else None
        if screen is not None:
            avail = screen.availableGeometry()
            target_w = min(800, max(520, avail.width() - 40))
            target_h = min(600, max(420, avail.height() - 60))
            dlg.setWindowState(dlg.windowState() & ~Qt.WindowState.WindowMaximized)
            dlg.setFixedSize(target_w, target_h)
            frame = dlg.frameGeometry()
            frame.moveCenter(avail.center())
            dlg.move(frame.topLeft())
        else:
            dlg.setFixedSize(800, 600)
        dlg.exec()

    # Backward compatibility alias
    def _show_account_info(self, account_name: str) -> None:
        self._show_profile_settings(account_name)

    def _open_camoufox_override_dialog(self, account_name: str) -> None:
        acc = next((a for a in db_get_accounts() if str(a.get("name") or "") == account_name), None)
        if not acc:
            QMessageBox.warning(self, "Error", f"Account {account_name} not found")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Camoufox settings · {account_name}")
        layout = QVBoxLayout(dlg)
        info = QLabel("Override defaults for this profile. Leave values as default to inherit global settings.")
        info.setWordWrap(True)
        layout.addWidget(info)
        controls, tabs_widget = self._build_camoufox_controls(dlg)
        layout.addWidget(tabs_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        clear_btn = QPushButton("Use defaults", dlg)
        buttons.addButton(clear_btn, QDialogButtonBox.ButtonRole.ResetRole)
        layout.addWidget(buttons)

        effective_values = self._camoufox_ui_values_for_account(acc)
        self._apply_camoufox_controls(controls, effective_values)

        def save_override():
            overrides = self._collect_camoufox_controls(controls)
            try:
                if overrides == getattr(self, "camoufox_defaults", overrides):
                    db_update_account(account_name, {"__delete_keys__": ["camoufox_settings"]})
                else:
                    db_update_account(account_name, {"camoufox_settings": overrides})
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Cannot save settings: {exc}")
                return
            self.refresh_accounts_list()
            self.log(f"Camoufox settings updated for {account_name}")
            dlg.accept()

        def clear_override():
            try:
                db_update_account(account_name, {"__delete_keys__": ["camoufox_settings"]})
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Cannot reset settings: {exc}")
                return
            self.refresh_accounts_list()
            self.log(f"Camoufox settings reset for {account_name}")
            dlg.accept()

        buttons.accepted.connect(save_override)
        buttons.rejected.connect(dlg.reject)
        clear_btn.clicked.connect(clear_override)
        dlg.exec()
