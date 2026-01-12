import re
from typing import Dict, List, Optional

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from app.storage.db import db_get_selector_index


_VAR_PATTERN = re.compile(r"{{\s*([\w.-]+)\s*}}")


class TemplateSteps:
    # Template helpers
    def _apply_template(self, raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None

        def repl(match: re.Match) -> str:
            key = match.group(1)
            return str(self.variables.get(key, ""))

        return _VAR_PATTERN.sub(repl, str(raw))

    def _apply_template_recursive(self, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            return self._apply_template(value)
        if isinstance(value, dict):
            out: Dict[object, object] = {}
            for key, val in value.items():
                new_key = self._apply_template(key) if isinstance(key, str) else key
                out[new_key] = self._apply_template_recursive(val)
            return out
        if isinstance(value, list):
            return [self._apply_template_recursive(item) for item in value]
        return value

    def _parse_json_object(self, raw: object, *, expected_type: type) -> Optional[object]:
        if raw is None:
            return None
        if isinstance(raw, expected_type):
            return raw
        if isinstance(raw, str):
            rendered = (self._apply_template(raw) or "").strip()
            if not rendered:
                return None
            try:
                import json

                parsed = json.loads(rendered)
            except Exception:
                return None
            if isinstance(parsed, expected_type):
                return parsed
            return None
        return None

    @staticmethod
    def _json_path_get(payload: object, path: str) -> Optional[object]:
        if payload is None:
            return None
        path = (path or "").strip()
        if not path:
            return None
        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$"):
            path = path[1:]
        if not path:
            return payload

        cur: object = payload
        token_re = re.compile(r"([^[.]+)(?:\\[(\\d+)\\])?")
        for part in path.split("."):
            part = part.strip()
            if not part:
                continue
            m = token_re.fullmatch(part)
            if not m:
                return None
            key = m.group(1)
            idx_raw = m.group(2)
            if isinstance(cur, dict):
                if key not in cur:
                    return None
                cur = cur.get(key)
            else:
                return None
            if idx_raw is not None:
                if not isinstance(cur, list):
                    return None
                idx = int(idx_raw)
                if idx < 0 or idx >= len(cur):
                    return None
                cur = cur[idx]
        return cur


class LocatorSteps:
    async def _resolve_frame(self, step: Dict):
        raw = step.get("frame_selector")
        if not raw:
            return self.page

        selectors: List[str] = []
        if isinstance(raw, list):
            for item in raw:
                rendered = str(self._apply_template(item) or "").strip()
                if rendered:
                    selectors.append(rendered)
        else:
            rendered = str(self._apply_template(raw) or "").strip()
            if not rendered:
                return self.page
            if ">>" in rendered:
                selectors = [part.strip() for part in rendered.split(">>") if part.strip()]
            else:
                selectors = [rendered]

        if not selectors:
            return self.page

        timeout = step.get("frame_timeout_ms") or step.get("timeout_ms") or 10000
        current = self.page
        for frame_selector in selectors:
            iframe_el = await current.wait_for_selector(frame_selector, timeout=timeout)
            frame = await iframe_el.content_frame()
            if frame is None:
                raise RuntimeError(f"Failed to resolve iframe by selector {frame_selector}")
            current = frame
        return current

    def _selector_state(self, step: Dict) -> str:
        state = str(step.get("state") or "").lower()
        allowed = {"attached", "detached", "visible", "hidden"}
        return state if state in allowed else "visible"

    def _build_locator(self, frame, step: Dict):
        selector = self._apply_template(step.get("selector") or "")
        selector_type = str(step.get("selector_type") or step.get("selector_kind") or "css").lower()
        if not selector:
            return None
        base_locator = None
        if selector_type in {"text", "get_by_text", "by_text"}:
            exact = bool(step.get("exact"))
            base_locator = frame.get_by_text(selector, exact=exact)
        elif selector_type in {"xpath", "xp"}:
            cleaned = selector[len("xpath=") :] if selector.lower().startswith("xpath=") else selector
            base_locator = frame.locator(f"xpath={cleaned}")
        elif selector_type in {"id", "#"}:
            cleaned = selector.lstrip("#")
            base_locator = frame.locator(f"#{cleaned}")
        elif selector_type in {"name"}:
            safe = selector.replace('"', '\\"')
            base_locator = frame.locator(f"[name=\"{safe}\"]")
        elif selector_type in {"test_id", "testid", "data-testid", "data_testid"}:
            base_locator = frame.get_by_test_id(selector)
        else:
            # default: treat as CSS or Playwright auto-detected selector string
            base_locator = frame.locator(selector)

        idx_override = step.get("selector_index")
        try:
            idx_override = int(idx_override) if idx_override is not None else None
        except Exception:
            idx_override = None
        if idx_override is None:
            idx_override = db_get_selector_index(selector) or db_get_selector_index(f"{selector_type}:{selector}")
        if idx_override is not None and base_locator is not None:
            try:
                return base_locator.nth(int(idx_override))
            except Exception:
                pass
        return base_locator

    async def _locate_element(self, step: Dict, wait: bool = False):
        attempts = 2 if step.get("frame_selector") else 1
        timeout = step.get("timeout_ms")
        state = self._selector_state(step)
        for attempt in range(attempts):
            frame = await self._resolve_frame(step)
            locator = self._build_locator(frame, step)
            if locator is None:
                return None
            if wait or step.get("wait_first", True):
                try:
                    await locator.wait_for(state=state, timeout=timeout)
                except PlaywrightTimeoutError:
                    return None
                except PlaywrightError as exc:
                    # Retry once if the frame detached while we were waiting.
                    if "frame was detached" in str(exc).lower() and attempt + 1 < attempts:
                        await self.page.wait_for_timeout(200)
                        continue
                    raise
            return locator
        return None
