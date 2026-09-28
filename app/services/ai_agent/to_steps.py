"""Turn a finished AI session into a clean, replayable scenario definition."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

MAX_SCENARIO_STEPS = 1000


def session_to_scenario_steps(session_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize agent-produced steps into the scenario editor format.

    - guarantees the start step
    - merges consecutive typing into the same selector (like the recorder)
    - re-tags steps sequentially and caps the total
    """
    steps: List[Dict[str, Any]] = [{"action": "start", "tag": "Start"}]
    for raw in session_steps:
        if not isinstance(raw, dict):
            continue
        step = {k: copy.deepcopy(v) for k, v in raw.items() if k not in ("tag",)}
        action = step.get("action")
        if action == "start":
            continue
        previous = steps[-1]
        if (
            action == "type"
            and previous.get("action") == "type"
            and previous.get("selector") == step.get("selector")
            and not previous.get("required_variable")
            and not step.get("required_variable")
        ):
            previous["value"] = step.get("value", "")
            continue
        if len(steps) >= MAX_SCENARIO_STEPS:
            break
        step["tag"] = f"Step{len(steps)}"
        steps.append(step)
    return steps


def scenario_description(task: str) -> str:
    text = " ".join(task.split())
    return f"AI draft: {text[:180]}" if text else "AI draft"


def steps_summary(steps: List[Dict[str, Any]]) -> str:
    """One-line human summary for toasts/logs."""
    actions = [step.get("action", "?") for step in steps[1:]]
    return f"{len(actions)} steps ({', '.join(actions[:8])}{'…' if len(actions) > 8 else ''})"
