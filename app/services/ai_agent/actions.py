"""AI agent action space: validation, LLM protocol text and page execution.

The LLM never returns code — only one validated JSON action per turn. Each
executed action also produces CamouFlow scenario step dicts (same shape as
scenario_recorder output), which is what makes an AI session compilable into
a deterministic, replayable scenario.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple

TEXT_IS_RE = re.compile(r"^([a-zA-Z][\w-]*):text-is\((.*)\)$", re.DOTALL)

ALLOWED_KEYS = {
    "Enter", "Escape", "Tab", "Backspace", "Delete",
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    "Home", "End", "PageUp", "PageDown",
}
ALLOWED_URL_SCHEMES = ("http://", "https://", "file://")
MAX_TYPE_LENGTH = 2000
MAX_URL_LENGTH = 2000
MAX_DONE_RESULT = 8000

ACTION_NAMES = ("goto", "click", "type", "select_option", "set_checked", "press", "scroll", "wait", "done")


class ActionError(ValueError):
    """Invalid agent action (bad name, missing/extra args, out-of-range values)."""


def _require_str(action: Dict[str, Any], key: str, max_length: int) -> str:
    value = action.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ActionError(f"'{key}' must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise ActionError(f"'{key}' is too long (max {max_length} chars)")
    return value


def _require_index(action: Dict[str, Any], element_count: int) -> int:
    value = action.get("index")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ActionError("'index' must be an integer element index from the snapshot")
    if value < 0 or value >= max(element_count, 1):
        raise ActionError(f"'index' {value} is not in the current snapshot (0..{max(element_count - 1, 0)})")
    return value


def validate_action(payload: Any, element_count: int = 250) -> Dict[str, Any]:
    """Normalize and validate one LLM action. Raises ActionError."""
    if not isinstance(payload, dict):
        raise ActionError("action must be a JSON object")
    unknown = set(payload) - {"name"}
    name = payload.get("name")
    if not isinstance(name, str) or name not in ACTION_NAMES:
        raise ActionError(f"'name' must be one of {', '.join(ACTION_NAMES)}")
    action: Dict[str, Any] = {"name": name}

    if name == "goto":
        url = _require_str(payload, "url", MAX_URL_LENGTH)
        if not url.startswith(ALLOWED_URL_SCHEMES):
            raise ActionError("'url' must start with http://, https:// or file://")
        unknown -= {"url"}
        action["url"] = url
    elif name == "click":
        action["index"] = _require_index(payload, element_count)
        unknown -= {"index"}
    elif name == "type":
        action["index"] = _require_index(payload, element_count)
        action["text"] = _require_str(payload, "text", MAX_TYPE_LENGTH)
        action["submit"] = bool(payload.get("submit", False))
        unknown -= {"index", "text", "submit"}
    elif name == "select_option":
        action["index"] = _require_index(payload, element_count)
        action["value"] = _require_str(payload, "value", 500)
        unknown -= {"index", "value"}
    elif name == "set_checked":
        action["index"] = _require_index(payload, element_count)
        if not isinstance(payload.get("checked"), bool):
            raise ActionError("'checked' must be true or false")
        action["checked"] = payload["checked"]
        unknown -= {"index", "checked"}
    elif name == "press":
        action["key"] = _require_str(payload, "key", 20)
        if action["key"] not in ALLOWED_KEYS:
            raise ActionError(f"'key' must be one of {', '.join(sorted(ALLOWED_KEYS))}")
        unknown -= {"key"}
    elif name == "scroll":
        direction = payload.get("direction", "down")
        if direction not in ("up", "down"):
            raise ActionError("'direction' must be 'up' or 'down'")
        amount = payload.get("amount", 600)
        if not isinstance(amount, int) or isinstance(amount, bool) or not 100 <= amount <= 3000:
            raise ActionError("'amount' must be an integer between 100 and 3000")
        action.update(direction=direction, amount=amount)
        unknown -= {"direction", "amount"}
    elif name == "wait":
        seconds = payload.get("seconds", 2)
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0.5 <= float(seconds) <= 10:
            raise ActionError("'seconds' must be between 0.5 and 10")
        action["seconds"] = float(seconds)
        unknown -= {"seconds"}
    elif name == "done":
        action["result"] = _require_str(payload, "result", MAX_DONE_RESULT) if payload.get("result") else ""
        unknown -= {"result"}

    if unknown:
        raise ActionError(f"unknown argument(s): {', '.join(sorted(unknown))}")
    return action


def action_protocol_prompt() -> str:
    return (
        "Reply with EXACTLY ONE JSON object and nothing else:\n"
        '{"thought": "<one short sentence of reasoning>", "action": {<one action below>}}\n\n'
        "Actions (use element indexes from the CURRENT page snapshot only):\n"
        '- {"name":"goto","url":"https://..."} — navigate\n'
        '- {"name":"click","index":<int>} — click an element\n'
        '- {"name":"type","index":<int>,"text":"...","submit":false} — fill a field; submit=true presses Enter after\n'
        '- {"name":"select_option","index":<int>,"value":"<option value>"} — pick a dropdown option\n'
        '- {"name":"set_checked","index":<int>,"checked":true} — check/uncheck a box\n'
        '- {"name":"press","key":"Enter"} — press a key (Enter, Escape, Tab, arrows...)\n'
        '- {"name":"scroll","direction":"down","amount":600} — scroll the page\n'
        '- {"name":"wait","seconds":2} — wait for content to load\n'
        '- {"name":"done","result":"<final answer for the user>"} — task complete; ALWAYS use this to finish\n'
    )


def describe_action(action: Dict[str, Any], elements: Optional[List[Dict[str, Any]]] = None) -> str:
    name = action["name"]
    if name == "goto":
        return f"goto {action['url']}"
    if name in ("click", "type", "select_option", "set_checked"):
        element = (elements or [{}])[action["index"]] if elements and action["index"] < len(elements) else {}
        label = element.get("text") or element.get("selector", "?")
        if name == "type":
            tail = " +Enter" if action.get("submit") else ""
            if element.get("type") == "password":
                return f"type •••••• into {label!r}{tail}"
            return f"type {action['text'][:40]!r} into {label!r}{tail}"
        if name == "select_option":
            return f"select {action['value'][:40]!r} in {label!r}"
        if name == "set_checked":
            return f"set {label!r} checked={action['checked']}"
        return f"click {label!r}"
    if name == "press":
        return f"press {action['key']}"
    if name == "scroll":
        return f"scroll {action['direction']} {action['amount']}"
    if name == "wait":
        return f"wait {action['seconds']}s"
    return "done"


async def _click(page, selector: str) -> None:
    """Click with a JS fallback for elements obscured by sticky headers/overlays."""
    try:
        await page.locator(selector).click(timeout=8000)
        return
    except Exception:
        match = TEXT_IS_RE.match(selector.strip())
        if match:
            tag, raw_text = match.group(1), match.group(2)
            try:
                text = json.loads(raw_text)
            except json.JSONDecodeError:
                text = raw_text.strip('"')
            await page.evaluate(
                """([tag, text]) => {
                    const clip = s => String(s == null ? '' : s).replace(/\\s+/g, ' ').trim();
                    const found = [...document.querySelectorAll(tag)].filter(el => clip(el.textContent) === text);
                    if (found.length === 1) { found[0].click(); return true; }
                    return false;
                }""",
                [tag, text],
            )
        else:
            await page.evaluate(
                "(sel) => { const el = document.querySelector(sel); if (el) el.click(); return Boolean(el); }",
                selector,
            )


async def execute_action(page, action: Dict[str, Any], elements: List[Dict[str, Any]], secret_serial: int = 0) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, str]], str]:
    """Run one action on the live page.

    Returns (scenario_steps, secret_or_None, description). `secret` is
    {"variable": "recorded_secret_N", "value": <typed text>} for password-like
    fields so callers can store it as a profile variable instead of the step.
    Exploration-only actions (scroll/wait) return no steps.
    """
    name = action["name"]
    steps: List[Dict[str, Any]] = []
    secret: Optional[Dict[str, str]] = None

    if name == "goto":
        await page.goto(action["url"], wait_until="domcontentloaded", timeout=45000)
        steps.append({"action": "goto", "url": action["url"], "value": action["url"]})
    elif name == "click":
        element = elements[action["index"]]
        url_before = page.url
        await _click(page, element["selector"])
        steps.append({"action": "click", "selector": element["selector"]})
        await _settle(page)
        if _normalized_url(page.url) != _normalized_url(url_before):
            steps.append({"action": "wait_for_load_state", "state": "domcontentloaded"})
    elif name == "type":
        element = elements[action["index"]]
        selector = element["selector"]
        sensitive = element.get("type") == "password"
        text = action["text"]
        if sensitive:
            await page.locator(selector).fill(text, timeout=10000)
            variable = f"recorded_secret_{secret_serial}"
            steps.append({"action": "type", "selector": selector, "value": "{{" + variable + "}}", "clear": True, "required_variable": variable})
            secret = {"variable": variable, "value": text}
        else:
            await page.locator(selector).fill(text, timeout=10000)
            steps.append({"action": "type", "selector": selector, "value": text, "clear": True})
        if action.get("submit"):
            await page.locator(selector).press("Enter", timeout=10000)
            steps.append({"action": "press", "selector": selector, "value": "Enter"})
    elif name == "select_option":
        element = elements[action["index"]]
        await page.locator(element["selector"]).select_option(action["value"], timeout=10000)
        steps.append({"action": "select_option", "selector": element["selector"], "value": action["value"]})
    elif name == "set_checked":
        element = elements[action["index"]]
        await page.locator(element["selector"]).set_checked(action["checked"], timeout=10000)
        steps.append({"action": "set_checked", "selector": element["selector"], "value": "true" if action["checked"] else "false"})
    elif name == "press":
        await page.keyboard.press(action["key"])
        steps.append({"action": "press", "selector": "body", "value": action["key"]})
    elif name == "scroll":
        delta = action["amount"] if action["direction"] == "down" else -action["amount"]
        await page.evaluate("(delta) => window.scrollBy(0, delta)", delta)
    elif name == "wait":
        await asyncio.sleep(action["seconds"])
    elif name == "done":
        return [], None, "done"

    return steps, secret, describe_action(action, elements)


def _normalized_url(url: str) -> str:
    return str(url or "").split("#", 1)[0]


async def _settle(page) -> None:
    """Give SPA navigations a moment to settle after a click."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
