"""Turn a finished AI session into a clean, replayable scenario definition."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

MAX_SCENARIO_STEPS = 1000
RESERVED_VARIABLES = {"name", "timestamp", "cookies"}


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


def parameterize_steps(steps, parameters):
    """Replace exact input values; callers supply parameters explicitly."""
    if not isinstance(parameters, dict) or len(parameters) > 20:
        raise ValueError("Inputs must be an object with at most 20 parameters")
    result = copy.deepcopy(steps)
    for name, value in parameters.items():
        if name in RESERVED_VARIABLES or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,49}", name) or not isinstance(value, str) or not value:
            raise ValueError("Each input needs a variable name and a non-empty string value")
        matched = False
        for step in result:
            if step.get("action") not in {"goto", "type", "select_option"} or step.get("required_variable"):
                continue
            for key in ("value", "url", "text"):
                if step.get(key) == value:
                    step[key] = "{{" + name + "}}"
                    matched = True
        if not matched:
            raise ValueError(f"Input {name} does not match a recorded navigation or field value")
    result[0]["_required_inputs"] = list(dict.fromkeys([*result[0].get("_required_inputs", []), *parameters]))
    return result


def compile_workflow(steps, parameters, outputs):
    result = parameterize_steps(session_to_scenario_steps(steps), parameters)
    for name, value in outputs.items():
        if name in RESERVED_VARIABLES or name in parameters or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,49}", name):
            raise ValueError("Invalid or conflicting output variable")
        if not isinstance(value, str) and not (isinstance(value, list) and value
                and all(isinstance(row, dict) and row and all(isinstance(k, str) and isinstance(v, str) for k, v in row.items()) for row in value)
                and all(set(row) == set(value[0]) for row in value)):
            raise ValueError("Outputs must be text or a non-empty table with consistent string columns")
        if not any(step.get("action") == "extract_text" and step.get("to_var") == name for step in result):
            raise ValueError("Output has no reproducible extraction step")
        extension = "json" if isinstance(value, list) else "txt"
        result.append({"action": "write_file", "filename": f"ai-results/{{{{name}}}}/{name}-{{{{timestamp}}}}.{extension}",
                       "value": "{{" + name + "}}", "tag": f"Step{len(result)}"})
    result[0]["_ai_outputs"] = list(outputs)
    return result
