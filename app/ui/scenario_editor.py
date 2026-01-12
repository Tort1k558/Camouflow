import math
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QContextMenuEvent, QFont, QPainter, QPen
from PyQt6.QtWidgets import QMenu, QWidget


class ScenarioEditor(QWidget):
    """Simple node/arrow map renderer for scenario steps using QPainter."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.steps: List[Dict] = []
        self.label_index: Dict[str, int] = {}
        self.tag_index: Dict[str, int] = {}
        self.selected_idx: int = -1
        self.custom_positions: Dict[int, QPointF] = {}
        self.setMinimumHeight(200)
        self.node_w = 210
        self.node_h = 44
        self.v_gap = 36
        self.h_gap = 80
        self.font = QFont("Consolas", 9)
        self.offset = QPointF(0, 0)
        self.zoom = 1.0
        self._dragging = False
        self._drag_button = None
        self._drag_start = QPointF(0, 0)
        self._offset_start = QPointF(0, 0)
        self.on_select: Optional[callable] = None
        self.on_add_after: Optional[callable] = None
        self.on_move: Optional[callable] = None
        self.on_drag_end: Optional[callable] = None
        self.on_delete: Optional[callable] = None
        self.on_edit: Optional[callable] = None
        # on_add_detached(pos: QPointF) -> None
        self.on_add_detached: Optional[callable] = None
        self._dragging_node = False
        self._drag_node_idx = -1
        self._drag_offset = QPointF(0, 0)
        self.ok_links: Dict[int, Set[int]] = {}
        self.err_links: Dict[int, Set[int]] = {}
        self._linking_from: Optional[int] = None
        self._linking_kind: Optional[str] = None  # "ok" | "err"
        self._linking_pos: Optional[QPointF] = None
        self._last_positions: Dict[int, Tuple[float, float, float, float]] = {}
        self._row_map: Dict[int, int] = {}
        self.action_labels: Dict[str, str] = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_steps(self, steps: List[Dict]) -> None:
        self.steps = steps or []
        self.label_index = {}
        self.tag_index = {}
        self.custom_positions = {}
        self.ok_links = {}
        self.err_links = {}
        self._row_map = {}
        for idx, step in enumerate(self.steps):
            label = step.get("label")
            if label:
                self.label_index[label] = idx
            tag = step.get("tag")
            if tag:
                self.tag_index[str(tag)] = idx
            pos = step.get("_pos")
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                try:
                    self.custom_positions[idx] = QPointF(float(pos["x"]), float(pos["y"]))
                except Exception:
                    pass

        for idx, step in enumerate(self.steps):
            ok_raw = step.get("_ok_links") or []
            err_raw = step.get("_err_links") or []
            ok_set: Set[int] = set()
            err_set: Set[int] = set()

            # Prefer tag-based next pointers
            succ_tag = step.get("next_success_step")
            if succ_tag and succ_tag in self.tag_index and self.tag_index[succ_tag] != idx:
                ok_set.add(self.tag_index[succ_tag])
            err_tag = step.get("next_error_step")
            if err_tag and err_tag in self.tag_index and self.tag_index[err_tag] != idx:
                err_set.add(self.tag_index[err_tag])

            # legacy index-based links
            for target in ok_raw:
                if isinstance(target, int) and 0 <= target < len(self.steps) and target != idx:
                    ok_set.add(target)
            for target in err_raw:
                if isinstance(target, int) and 0 <= target < len(self.steps) and target != idx:
                    err_set.add(target)

            self.ok_links[idx] = ok_set
            self.err_links[idx] = err_set
        # place nodes primarily in one row, error targets slightly lower at same x
        self._row_map = {idx: 0 for idx in range(len(self.steps))}
        for src, targets in self.err_links.items():
            for t in targets:
                if t == src:
                    continue
                self._row_map[t] = 1
        self.update()

    def set_selected(self, idx: int) -> None:
        self.selected_idx = idx
        self.update()

    def set_action_labels(self, mapping: Optional[Dict[str, str]]) -> None:
        self.action_labels = mapping or {}
        self.update()

    def _scene_pos_from_view(self, view_point: QPointF) -> QPointF:
        base_x = float(view_point.x()) / max(self.zoom, 1e-9)
        base_y = float(view_point.y()) / max(self.zoom, 1e-9)
        scene_x = base_x - self.offset.x()
        scene_y = base_y - self.offset.y()
        return QPointF(scene_x - self.node_w / 2, scene_y - self.node_h / 2)

    def _base_position(self, idx: int) -> Optional[Tuple[float, float]]:
        if idx < 0 or idx >= len(self.steps):
            return None
        if idx in self.custom_positions:
            pos = self.custom_positions[idx]
            return pos.x(), pos.y()
        row = self._row_map.get(idx, 0)
        base_x = self.h_gap + idx * (self.node_w + self.h_gap)
        base_y = self.v_gap + (row * (self.node_h + self.v_gap))
        return float(base_x), float(base_y)

    def focus_on_index(self, idx: int, anchor: Optional[Tuple[float, float]] = None) -> None:
        base = self._base_position(idx)
        if base is None:
            return
        ax, ay = anchor if anchor is not None else (self.h_gap, self.v_gap)
        try:
            ax = float(ax)
            ay = float(ay)
        except Exception:
            ax, ay = float(self.h_gap), float(self.v_gap)
        self.offset = QPointF(ax - base[0], ay - base[1])
        self.update()

    def focus_on_tag(self, tag: str, anchor: Optional[Tuple[float, float]] = None) -> None:
        if not self.steps:
            return
        idx = None
        if tag:
            idx = self.tag_index.get(str(tag))
        if idx is None and tag and str(tag).lower() == "start":
            idx = next(
                (i for i, step in enumerate(self.steps) if str(step.get("action", "")).lower() == "start"),
                None,
            )
        if idx is None:
            idx = 0
        self.focus_on_index(idx, anchor=anchor)

    def focus_on_start(self) -> None:
        self.focus_on_tag("Start")

    def _node_rect(self, idx: int):
        row = self._row_map.get(idx, 0)
        base_x = self.h_gap + idx * (self.node_w + self.h_gap)
        base_y = self.v_gap + (row * (self.node_h + self.v_gap))
        if idx in self.custom_positions:
            base = self.custom_positions[idx]
            base_x = base.x()
            base_y = base.y()
        x = base_x + self.offset.x()
        y = base_y + self.offset.y()
        return x, y, self.node_w, self.node_h

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, color: QColor) -> None:
        painter.setPen(QPen(color, 2))
        painter.drawLine(start, end)
        # Arrow head
        angle = 0.0
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if dx or dy:
            angle = math.atan2(dy, dx)
        size = 8
        left = QPointF(
            end.x() - size * math.cos(angle - math.pi / 6),
            end.y() - size * math.sin(angle - math.pi / 6),
        )
        right = QPointF(
            end.x() - size * math.cos(angle + math.pi / 6),
            end.y() - size * math.sin(angle + math.pi / 6),
        )
        painter.drawPolygon(end, left, right)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        bg_color = self.palette().window().color()
        dark = bg_color.value() < 128
        painter.fillRect(self.rect(), QColor("#121212") if dark else QColor("#f7f7f7"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.save()
        painter.scale(self.zoom, self.zoom)
        painter.setFont(self.font)

        if not self.steps:
            painter.setPen(QPen(QColor("#888888"), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No steps")
            return

        node_color = QColor("#2d89ef")
        text_color = QColor("#ffffff")
        ok_color = QColor("#2ecc71")
        error_color = QColor("#e81123")
        selected_pen = QPen(QColor("#ffda57"), 3)
        input_color = QColor("#b0b0b0")

        positions: Dict[int, Tuple[float, float, float, float]] = {}

        for idx, _ in enumerate(self.steps):
            positions[idx] = self._node_rect(idx)
        self._last_positions = positions

        def connector_points(rect):
            x, y, w, h = rect
            input_pt = QPointF(x - 12, y + h * 0.5)
            ok_pt = QPointF(x + w + 14, y + h * 0.32)
            err_pt = QPointF(x + w + 14, y + h * 0.68)
            return input_pt, ok_pt, err_pt

        # Draw arrows first for layering
        for src, targets in self.ok_links.items():
            if src not in positions:
                continue
            _, ok_pt, _ = connector_points(positions[src])
            for dst in targets:
                if dst not in positions:
                    continue
                input_pt, _, _ = connector_points(positions[dst])
                self._draw_arrow(painter, ok_pt, input_pt, ok_color)
        for src, targets in self.err_links.items():
            if src not in positions:
                continue
            _, _, err_pt = connector_points(positions[src])
            for dst in targets:
                if dst not in positions:
                    continue
                input_pt, _, _ = connector_points(positions[dst])
                self._draw_arrow(painter, err_pt, input_pt, error_color)

        # Draw linking preview while dragging from a connector
        if self._linking_from is not None and self._linking_pos is not None:
            if self._linking_from in positions:
                _, ok_pt, err_pt = connector_points(positions[self._linking_from])
                start_pt = ok_pt if self._linking_kind == "ok" else err_pt
                color = ok_color if self._linking_kind == "ok" else error_color
                self._draw_arrow(painter, start_pt, self._linking_pos, color)

        # Draw nodes
        painter.setPen(Qt.PenStyle.NoPen)
        for idx, step in enumerate(self.steps):
            x, y, w, h = positions[idx]
            painter.setBrush(node_color)
            painter.drawRoundedRect(int(x), int(y), int(w), int(h), 6, 6)
            painter.setPen(QPen(text_color, 1))
            tag = step.get("tag", "")
            action = step.get("action", "")
            action_label = self.action_labels.get(str(action), action)
            selector = step.get("selector") or step.get("value") or step.get("url") or ""
            if step.get("selector") and step.get("selector_type"):
                selector = f"[{step.get('selector_type')}] {step.get('selector')}"
            text = f"{idx + 1}. {action_label}"

            # Clip and elide text so it never paints outside the node rect.
            painter.save()
            try:
                painter.setClipRect(int(x), int(y), int(w), int(h))
                metrics = painter.fontMetrics()
                available = max(0, int(w) - 16)
                header = f"{tag} | {text}" if tag else text
                header = metrics.elidedText(str(header), Qt.TextElideMode.ElideRight, available)
                painter.drawText(int(x + 8), int(y + 16), header)
                if selector:
                    line2 = metrics.elidedText(str(selector), Qt.TextElideMode.ElideRight, available)
                    painter.drawText(int(x + 8), int(y + 32), line2)
            finally:
                painter.restore()
            if idx == self.selected_idx:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(selected_pen)
                painter.drawRoundedRect(int(x - 2), int(y - 2), int(w + 4), int(h + 4), 8, 8)
                painter.setPen(QPen(text_color, 1))
            # connectors
            input_pt, ok_pt, err_pt = connector_points((x, y, w, h))
            painter.setBrush(input_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(input_pt, 4, 4)
            painter.setBrush(ok_color)
            painter.drawEllipse(ok_pt, 5, 5)
            painter.setBrush(error_color)
            painter.drawEllipse(err_pt, 5, 5)
        painter.restore()

    def _node_at(self, pos: QPointF) -> int:
        for idx, _ in enumerate(self.steps):
            x, y, w, h = self._node_rect(idx)
            if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                return idx
        return -1

    def _handle_hit(self, pos: QPointF):
        tolerance = 8.0
        for idx, rect in self._last_positions.items():
            x, y, w, h = rect
            input_pt = QPointF(x - 10, y + h / 2)
            ok_pt = QPointF(x + w + 10, y + h * 0.4)
            err_pt = QPointF(x + w + 10, y + h * 0.6)
            for kind, pt, radius in (("in", input_pt, 6.0), ("ok", ok_pt, 7.0), ("err", err_pt, 7.0)):
                if (pos - pt).manhattanLength() <= radius + tolerance:
                    if idx == 0 and kind == "err":
                        continue
                    return idx, kind
        return None
    def _auto_pan(self, cursor_pos):
        margin = 40.0
        step = 20.0 / max(self.zoom, 0.1)
        dx = 0.0
        dy = 0.0
        if cursor_pos.x() < margin:
            dx = step
        elif cursor_pos.x() > self.width() - margin:
            dx = -step
        if cursor_pos.y() < margin:
            dy = step
        elif cursor_pos.y() > self.height() - margin:
            dy = -step
        if dx or dy:
            self.offset = QPointF(self.offset.x() + dx, self.offset.y() + dy)
            self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = event.position() / self.zoom
            hit = self._handle_hit(scene_pos)
            if hit and hit[1] in ("ok", "err"):
                self._linking_from, self._linking_kind = hit[0], hit[1]
                self._linking_pos = scene_pos
                return
            idx = self._node_at(scene_pos)
            if idx >= 0:
                self.selected_idx = idx
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                # No callbacks on plain left click to avoid popping modal editors.
                self.update()
                self._dragging_node = True
                self._drag_node_idx = idx
                x, y, w, h = self._node_rect(idx)
                self._drag_offset = scene_pos - QPointF(x, y)
                self._dragging = False
            else:
                self._dragging = True
                self._drag_button = event.button()
                self._drag_start = event.position()
                self._offset_start = QPointF(self.offset)
        elif event.button() == Qt.MouseButton.RightButton:
            self._dragging = False
            self._dragging_node = False
            super().mousePressEvent(event)
            return
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._dragging = True
            self._drag_button = event.button()
            self._drag_start = event.position()
            self._offset_start = QPointF(self.offset)
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        try:
            key = event.key()
        except Exception:
            return super().keyPressEvent(event)

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            idx = int(getattr(self, "selected_idx", -1) or -1)
            if idx > 0 and callable(self.on_delete):
                try:
                    self.on_delete(idx)
                finally:
                    event.accept()
                return
            event.ignore()
            return

        super().keyPressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._linking_from is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._auto_pan(event.position())
            self._linking_pos = event.position() / self.zoom
            self.update()
            return
        if self._dragging and self._drag_button in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            speed = 1.0 / max(self.zoom, 0.1)
            delta = (event.position() - self._drag_start) * speed
            self.offset = QPointF(self._offset_start.x() + delta.x(), self._offset_start.y() + delta.y())
            self.update()
        elif self._dragging_node and self._drag_node_idx >= 0:
            pos = event.position() / self.zoom - self._drag_offset
            self.custom_positions[self._drag_node_idx] = QPointF(pos.x() - self.offset.x(), pos.y() - self.offset.y())
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._linking_from is not None:
            target_hit = self._handle_hit(event.position() / self.zoom)
            if target_hit and target_hit[1] == "in":
                self._add_link(self._linking_from, target_hit[0], self._linking_kind or "ok")
            self._linking_from = None
            self._linking_kind = None
            self._linking_pos = None
            self.update()
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._dragging = False
            self._drag_button = None
        elif event.button() == Qt.MouseButton.LeftButton and self._dragging_node:
            if self.on_drag_end and self._drag_node_idx >= 0:
                pos = self.custom_positions.get(self._drag_node_idx, QPointF(0, 0))
                self.on_drag_end(self._drag_node_idx, pos)
            self._dragging_node = False
            self._drag_node_idx = -1
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        # Only select node on double-click, no modals/actions.
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = event.position() / self.zoom
            idx = self._node_at(scene_pos)
            if idx >= 0:
                self.selected_idx = idx
                self.update()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        delta = event.angleDelta().y() / 120.0
        if delta == 0:
            event.ignore()
            return
        factor = 1.1 if delta > 0 else 0.9
        old_zoom = self.zoom
        new_zoom = max(0.5, min(2.5, self.zoom * factor))
        if new_zoom == old_zoom:
            event.accept()
            return
        # zoom toward cursor: adjust offset so cursor stays anchored
        cursor_pos = event.position()
        scene_before = (cursor_pos / old_zoom) - self.offset
        self.zoom = new_zoom
        self.offset = (cursor_pos / self.zoom) - scene_before
        self.update()
        event.accept()

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        # Only show menu for real right-click context triggers.
        if isinstance(event, QContextMenuEvent):
            try:
                if event.reason() == QContextMenuEvent.Reason.Mouse and event.mouseButton() != Qt.MouseButton.RightButton:
                    event.ignore()
                    return
            except Exception:
                pass
        view_point = QPointF(event.pos())
        scene_pos = view_point / self.zoom
        target_pos = self._scene_pos_from_view(view_point)

        link_hit = self._find_link_at(scene_pos)
        if link_hit:
            src, dst, kind = link_hit
            menu = QMenu(self)
            act_delete_link = menu.addAction("Delete link")
            chosen = menu.exec(self.mapToGlobal(event.pos()))
            if chosen == act_delete_link:
                self._remove_link(src, dst, kind)
            event.accept()
            return

        idx = self._node_at(scene_pos)
        menu = QMenu(self)
        act_add_detached = menu.addAction("Add step")
        act_edit = menu.addAction("Edit step")
        act_delete = menu.addAction("Delete step")
        if idx < 0 or idx == 0:
            act_delete.setEnabled(False)
            act_edit.setEnabled(False)
        chosen = menu.exec(self.mapToGlobal(event.pos()))
        if chosen == act_delete and self.on_delete and idx >= 0:
            self.on_delete(idx)
        elif chosen == act_edit and self.on_edit and idx >= 0:
            self.on_edit(idx)
        elif chosen == act_add_detached and self.on_add_detached:
            self.on_add_detached(target_pos)
        event.accept()

    def _add_link(self, src: int, dst: int, kind: str) -> None:
        if src == dst or src < 0 or dst < 0:
            return
        if src == 0 and kind == "err":
            return
        links = self.ok_links if kind == "ok" else self.err_links
        src_tag = self.steps[src].get("tag")
        dst_tag = self.steps[dst].get("tag")
        if not src_tag or not dst_tag:
            return
        # Only one outgoing link per kind.
        links[src] = {dst}
        if kind == "err":
            self._row_map[dst] = 1
        step = self.steps[src]
        if kind == "ok":
            step["next_success_step"] = dst_tag
        else:
            step["next_error_step"] = dst_tag
        self.update()

    def _remove_link(self, src: int, dst: int, kind: str) -> None:
        links = self.ok_links if kind == "ok" else self.err_links
        if src in links and dst in links[src]:
            links[src].remove(dst)
            if kind == "ok":
                self.steps[src].pop("next_success_step", None)
            else:
                self.steps[src].pop("next_error_step", None)
                # reset row if no other err links point to dst
                still_err_target = any(dst in tset for tset in self.err_links.values())
                if not still_err_target:
                    self._row_map[dst] = 0
            self.update()

    def _find_link_at(self, pos: QPointF):
        def dist_point_to_segment(p, a, b) -> float:
            ax, ay = a.x(), a.y()
            bx, by = b.x(), b.y()
            px, py = p.x(), p.y()
            abx = bx - ax
            aby = by - ay
            ab_len_sq = abx * abx + aby * aby
            if ab_len_sq == 0:
                return math.hypot(px - ax, py - ay)
            t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))
            proj_x = ax + t * abx
            proj_y = ay + t * aby
            return math.hypot(px - proj_x, py - proj_y)

        for kind, links in (("ok", self.ok_links), ("err", self.err_links)):
            for src, targets in links.items():
                if src not in self._last_positions:
                    continue
                x, y, w, h = self._last_positions[src]
                _, ok_pt, err_pt = QPointF(x - 10, y + h / 2), QPointF(x + w + 10, y + h * 0.4), QPointF(
                    x + w + 10, y + h * 0.6
                )
                start_pt = ok_pt if kind == "ok" else err_pt
                for dst in targets:
                    if dst not in self._last_positions:
                        continue
                    dx, dy, dw, dh = self._last_positions[dst]
                    input_pt = QPointF(dx - 10, dy + dh / 2)
                    if dist_point_to_segment(pos, start_pt, input_pt) <= 8.0:
                        return src, dst, kind
        return None
