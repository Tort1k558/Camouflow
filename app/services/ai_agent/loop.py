"""AI agent session loop: DOM snapshot -> LLM -> validated action -> execute.

Emits events through `on_event` for live UI streaming and accumulates
scenario steps, so a finished session can be saved as a deterministic
scenario. No code from the LLM is ever executed — only validated actions.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.services.ai_agent.actions import ActionError, action_protocol_prompt, execute_action, validate_action
from app.services.ai_agent.llm import LLMClient, LLMError

DOM_JS_PATH = Path(__file__).resolve().parent / "dom.js"

DEFAULT_MAX_STEPS = 25
HARD_MAX_STEPS = 100
DEFAULT_SESSION_TIMEOUT_S = 15 * 60
MAX_CONSECUTIVE_ERRORS = 3
MAX_SNAPSHOT_ELEMENTS_IN_PROMPT = 150
MAX_OBSERVATION_CHARS = 14000
KEEP_LAST_TURNS = 8

SYSTEM_PROMPT = (
    "You are CamouFlow's browser agent. You see a compact snapshot of the current "
    "page: indexed interactive elements with their text. You control the browser ONE "
    "action at a time; after each action you receive the next snapshot.\n"
    "Rules:\n"
    "- Use only element indexes present in the latest snapshot; never invent them.\n"
    "- Prefer ids/names (stable) over structural selectors when both exist.\n"
    "- If a page looks wrong or empty, scroll or wait, then reassess.\n"
    "- Never type secrets into non-password fields; leave login flows to saved sessions.\n"
    "- When the task is complete (or provably impossible), answer with the done action "
    "and put the user-facing result in its result field.\n"
) + action_protocol_prompt()


class AgentSession:
    def __init__(
        self,
        page,
        client: LLMClient,
        task: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        session_timeout_s: float = DEFAULT_SESSION_TIMEOUT_S,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[asyncio.Event] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        dom_js: Optional[str] = None,
    ) -> None:
        self.page = page
        self.client = client
        self.task = task.strip()
        self.max_steps = max(1, min(int(max_steps), HARD_MAX_STEPS))
        self.session_timeout_s = session_timeout_s
        self._on_event = on_event or (lambda event: None)
        self._stop_event = stop_event or asyncio.Event()
        self._stop_check = stop_check
        self._dom_js = dom_js if dom_js is not None else DOM_JS_PATH.read_text(encoding="utf-8")
        self.steps: List[Dict[str, Any]] = [{"action": "start", "tag": "Start"}]
        self.secrets: Dict[str, str] = {}
        self.events: List[Dict[str, Any]] = []

    def _emit(self, event: Dict[str, Any]) -> None:
        event.setdefault("at", time.time())
        self.events.append(event)
        self._on_event(event)

    @staticmethod
    def _snapshot_to_observation(snapshot: Dict[str, Any]) -> str:
        lines = [f"PAGE url={snapshot.get('url', '')}", f"title={snapshot.get('title', '')}"]
        page_text = " ".join(str(snapshot.get("text") or "").split())
        if page_text:
            lines.append(f"TEXT: {page_text}")
        elements = snapshot.get("elements", [])[:MAX_SNAPSHOT_ELEMENTS_IN_PROMPT]
        for element in elements:
            parts = [str(element["index"]), element["tag"]]
            if element.get("role"):
                parts.append(f"role={element['role']}")
            if element.get("type"):
                parts.append(f"type={element['type']}")
            if element.get("checked") is not None:
                parts.append(f"checked={str(element['checked']).lower()}")
            if element.get("options") is not None:
                parts.append("options=" + "|".join(element["options"]))
            if element.get("href"):
                parts.append(f"href={element['href']}")
            if element.get("disabled"):
                parts.append("disabled")
            if element.get("text"):
                parts.append(repr(element["text"]))
            lines.append(" ".join(parts))
        if len(snapshot.get("elements", [])) > MAX_SNAPSHOT_ELEMENTS_IN_PROMPT:
            lines.append("(list truncated)")
        text = "\n".join(lines)
        if len(text) > MAX_OBSERVATION_CHARS:
            text = text[:MAX_OBSERVATION_CHARS] + "\n(snapshot truncated)"
        return text

    async def _snapshot(self) -> Dict[str, Any]:
        return await self.page.evaluate(self._dom_js)

    def _stopped(self) -> bool:
        if self._stop_event.is_set():
            return True
        return bool(self._stop_check and self._stop_check())

    async def run(self) -> Dict[str, Any]:
        started = time.monotonic()
        self._emit({"type": "info", "text": f"AI session started: {self.task[:200]}"})
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"TASK: {self.task}"},
        ]
        status, result = "error", ""
        consecutive_errors = 0
        step_index = 0
        repeated = 0
        self._last_action = None
        self._pending_note = ""

        try:
            while True:
                if self._stopped():
                    status, result = "stopped", "Stopped by user"
                    break
                if step_index >= self.max_steps:
                    status, result = "max_steps", f"Stopped at the step limit ({self.max_steps})"
                    break
                if time.monotonic() - started > self.session_timeout_s:
                    status, result = "timeout", "Session timed out"
                    break

                try:
                    snapshot = await self._snapshot()
                    if not snapshot.get("elements") and len(str(snapshot.get("text") or "")) < 50:
                        # SPA hydration race: give the page a moment and retry once.
                        await asyncio.sleep(1.5)
                        snapshot = await self._snapshot()
                except Exception as exc:  # page crashed / navigation race
                    consecutive_errors += 1
                    self._emit({"type": "error", "text": f"snapshot failed: {exc}"})
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        status, result = "error", f"could not read the page: {exc}"
                        break
                    messages.append({"role": "user", "content": f"ERROR: page snapshot failed ({exc}). Try goto or done."})
                    continue

                observation = self._snapshot_to_observation(snapshot)
                if self._pending_note:
                    observation = f"{self._pending_note}\n{observation}"
                    self._pending_note = ""
                messages.append({"role": "user", "content": observation})
                messages = self._trim(messages)

                try:
                    thought, action = await self.client.next_action(messages, element_count=len(snapshot["elements"]))
                except LLMError as exc:
                    status, result = "error", str(exc)
                    self._emit({"type": "error", "text": str(exc)})
                    break

                step_index += 1
                self._emit({"type": "thought", "step": step_index, "text": thought})
                messages.append({"role": "assistant", "content": json.dumps({"thought": thought, "action": action}, ensure_ascii=False)})
                self._emit({"type": "action", "step": step_index, "action": action["name"], "text": _action_text(action, snapshot["elements"])})

                if action == self._last_action and action["name"] != "done":
                    repeated += 1
                else:
                    repeated = 0
                self._last_action = action
                if repeated >= 2:
                    self._pending_note = "NOTE: you repeated the same action and the page did not change. Re-read TEXT above, then use done with the answer or change approach."

                if action["name"] == "done":
                    status, result = "done", action.get("result", "")
                    self._emit({"type": "done", "text": result or "(no result)"})
                    break

                try:
                    new_steps, secret, description = await execute_action(
                        self.page, action, snapshot["elements"], secret_serial=len(self.secrets) + 1
                    )
                    consecutive_errors = 0
                    if secret:
                        self.secrets[secret["variable"]] = secret["value"]
                    for step in new_steps:
                        step["tag"] = f"Step{len(self.steps)}"
                        self.steps.append(step)
                    self._emit({"type": "observation", "step": step_index, "text": description, "url": self.page.url})
                except (ActionError, Exception) as exc:  # noqa: BLE001 - executor failures are agent-observable
                    consecutive_errors += 1
                    self._emit({"type": "error", "step": step_index, "text": f"action failed: {exc}"})
                    messages.append({"role": "user", "content": f"ERROR: {action['name']} failed: {exc}. Adjust and retry, or use done."})
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        status, result = "error", f"action kept failing: {exc}"
                        break
        finally:
            self._emit({"type": "end", "status": status, "text": result})

        return {
            "status": status,
            "result": result,
            "steps": self.steps,
            "secrets": dict(self.secrets),
            "events": self.events,
            "task": self.task,
            "duration_s": round(time.monotonic() - started, 1),
        }

    @staticmethod
    def _trim(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep the system prompt, the task and the last turns."""
        if len(messages) <= 2 + KEEP_LAST_TURNS * 2:
            return messages
        return [messages[0], messages[1]] + messages[-(KEEP_LAST_TURNS * 2):]


def _action_text(action: Dict[str, Any], elements: List[Dict[str, Any]]) -> str:
    try:
        from app.services.ai_agent.actions import describe_action

        return describe_action(action, elements)
    except Exception:
        return action["name"]


def save_transcript(result: Dict[str, Any], artifacts_dir: Path) -> Path:
    """Persist a finished session (steps, events, secrets excluded)."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": result.get("task"),
        "status": result.get("status"),
        "result": result.get("result"),
        "duration_s": result.get("duration_s"),
        "steps": result.get("steps", []),
        "events": [
            {k: v for k, v in event.items() if k != "at"}
            for event in result.get("events", [])
        ],
    }
    path = artifacts_dir / "transcript.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
