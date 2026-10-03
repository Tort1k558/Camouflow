"""Input forms for recorded and AI-generated scenarios."""

import csv
import io
import re
from pathlib import Path

from app.services.ai_agent.to_steps import RESERVED_VARIABLES, parameterize_steps


def input_fields(steps):
    if not steps or not isinstance(steps[0], dict):
        raise ValueError("Task has no start step")
    names = steps[0].get("_required_inputs", [])
    labels = steps[0].get("_input_labels", {})
    if (not isinstance(names, list) or len(names) > 20 or not isinstance(labels, dict)
            or any(not isinstance(name, str) or name in RESERVED_VARIABLES
                   or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,49}", name) for name in names)
            or len(set(names)) != len(names)):
        raise ValueError("Invalid task input definition")
    fields = []
    for name in names:
        label = labels.get(name, name.replace("_", " ").capitalize())
        if not isinstance(label, str) or not label.strip() or len(label) > 100:
            raise ValueError("Invalid task input label")
        fields.append({"name": name, "label": label, "value": ""})
    return fields


def validate_inputs(steps, values):
    fields = input_fields(steps)
    if not isinstance(values, dict) or set(values) != {field["name"] for field in fields}:
        raise ValueError("Fill all task inputs; unexpected inputs are not allowed")
    if any(not isinstance(value, str) or not value.strip() or len(value) > 10000 for value in values.values()):
        raise ValueError("Each task input needs a non-empty value (up to 10,000 characters)")
    return dict(values)


def csv_rows(steps, payload, delimiter=","):
    """Validate the whole import before any row can enter the queue."""
    names = [field["name"] for field in input_fields(steps)]
    if not names:
        raise ValueError("Choose a task with changing inputs")
    if delimiter not in {",", ";"}:
        raise ValueError("Choose comma or semicolon as the CSV separator")
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise ValueError("CSV must be at most 1 MiB")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), delimiter=delimiter, strict=True)
        header = next(reader, [])
        if len(header) != len(names) or set(header) != set(names):
            raise ValueError("CSV headers must match: " + delimiter.join(names))
        rows, seen = [], {}
        for number, values in enumerate(reader, start=1):
            if number > 200:
                raise ValueError("CSV safety limit: 200 data rows")
            if len(values) != len(header):
                raise ValueError(f"Data row {number}: wrong number of columns")
            try:
                inputs = validate_inputs(steps, dict(zip(header, values)))
            except ValueError as exc:
                raise ValueError(f"Data row {number}: {exc}") from exc
            key = tuple(inputs[name] for name in names)
            rows.append({"row": number, "inputs": inputs, "duplicate_of": seen.get(key, 0)})
            seen.setdefault(key, number)
        if not rows:
            raise ValueError("CSV has no data rows")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Invalid UTF-8 CSV: " + str(exc)) from exc


def csv_template(steps, delimiter=","):
    names = [field["name"] for field in input_fields(steps)]
    if not names or delimiter not in {",", ";"}:
        raise ValueError("Choose a task with changing inputs and a valid separator")
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=delimiter).writerow(names)
    return output.getvalue()


def configure_task_run(runner, job, outputs):
    if "inputs" in job:
        runner._transient_inputs = validate_inputs(job["steps"], job["inputs"])
        runner.variables.update(runner._transient_inputs)
    if job.get("batch_id"):
        if any(not re.fullmatch(r"[a-f0-9]{32}", str(job.get(key, ""))) for key in ("batch_id", "id")):
            raise ValueError("Invalid batch run identity")
        runner._output_directory = Path(outputs) / "batches" / job["batch_id"] / job["id"]


def recording_candidates(steps):
    candidates = []
    seen = set()
    for step in steps:
        action = step.get("action")
        if action not in {"goto", "type", "select_option"} or step.get("required_variable"):
            continue
        value = step.get("url") or step.get("value") or step.get("text")
        if not isinstance(value, str) or not value or "{{" in value or value in seen:
            continue
        seen.add(value)
        label = step.get("field_label") or {"goto": "Website URL", "type": "Text field", "select_option": "Selection"}[action]
        candidates.append({"value": value, "label": label, "step": step.get("tag", "")})
    return candidates


def prepare_recording(steps, fields):
    if not steps or not isinstance(steps[0], dict) or steps[0].get("action") != "start":
        raise ValueError("Recording has no start step")
    if not isinstance(fields, list) or len(fields) > 20:
        raise ValueError("Choose up to 20 changing fields")
    parameters, labels = {}, {}
    for field in fields:
        if not isinstance(field, dict):
            raise TypeError("Invalid recorded input")
        name, label, value = field.get("name"), field.get("label"), field.get("value")
        if not isinstance(name, str) or name in parameters or value in parameters.values():
            raise ValueError("Use a unique variable name and recorded value for each input")
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 100:
            raise ValueError("Give each input a label (1-100 characters)")
        parameters[name] = value
        labels[name] = label.strip()
    result = parameterize_steps(steps, parameters)
    result[0]["_input_labels"] = labels
    result[0]["_task"] = True
    input_fields(result)
    return result
