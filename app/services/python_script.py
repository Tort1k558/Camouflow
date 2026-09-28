"""Versioned Python step contract. Execution is allowed only in a supervised worker."""

from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import re
import traceback
from pathlib import Path
from types import MappingProxyType

DEFAULT_CODE = 'async def main(ctx):\n    return await ctx.page.title()\n'
MAX_RESULT_BYTES = 1024 * 1024


def validate_script(step):
    if step.get("script_api_version") != 1:
        raise ValueError("Unsupported Python API version; this client supports version 1")
    code = step.get("code")
    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 256 * 1024:
        raise ValueError("Python code must contain 1 to 262144 UTF-8 bytes")
    try:
        tree = ast.parse(code, filename="scenario_script.py")
    except RecursionError as exc:
        raise ValueError("Python source nesting exceeds the compiler limit") from exc
    definitions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main"]
    if len(definitions) != 1:
        raise ValueError("Define exactly one async def main(ctx)")
    args = definitions[0].args
    if len(args.posonlyargs) + len(args.args) != 1 or args.vararg or args.kwarg or args.kwonlyargs:
        raise ValueError("main must accept exactly one context argument")
    if not isinstance(step.get("inputs", {}), dict):
        raise ValueError("Python inputs must be a JSON object")
    timeout = step.get("timeout_ms", 60000)
    if type(timeout) is not int or not 100 <= timeout <= 3600000:
        raise ValueError("Python timeout must be between 100 and 3600000 ms")
    result = step.get("result_variable", "")
    if not isinstance(result, str) or "{{" in result or len(result) > 200:
        raise ValueError("Invalid result variable name")
    try:
        compile(tree, "scenario_script.py", "exec")
    except RecursionError as exc:
        raise ValueError("Python source nesting exceeds the compiler limit") from exc


def script_bundle(steps, library):
    """Resolve static calls; dynamic calls include the complete frozen library."""
    selected = {}
    pending = [steps]
    scripts = []
    while pending:
        for step in pending.pop():
            action = str(step.get("action", "")).lower()
            if action == "python":
                validate_script(step)
                scripts.append(step)
            if action == "run_scenario":
                name = str(step.get("scenario") or step.get("scenario_name") or step.get("name") or step.get("value") or "").strip()
                names = list(library) if "{{" in name else [name]
                for name in names:
                    if name not in library:
                        raise ValueError(f"Nested scenario not found: {name}")
                    if name not in selected:
                        selected[name] = library[name]
                        pending.append(library[name]["steps"])
    if not scripts:
        return "", ""
    payload = json.dumps({"steps": steps, "library": selected}, sort_keys=True, ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    preview = "\n\n".join(f"# Python block {i + 1}: {s.get('tag', '')}\n{s['code']}" for i, s in enumerate(scripts))
    return digest, preview


class ScriptContext:
    def __init__(self, runner, inputs):
        self._runner = runner
        self.inputs = MappingProxyType(copy.deepcopy(inputs))
        self.variables = MappingProxyType(copy.deepcopy(runner.variables))
        self.log = runner.logger
        self.artifacts_dir = Path(runner._run_artifact_dir)

    @property
    def page(self):
        return self._runner.page

    @property
    def context(self):
        return self._runner.context

    def use_page(self, page):
        if page not in self.context.pages or page.is_closed():
            raise ValueError("Choose an open page belonging to this profile")
        self._runner.page = page

    def check_cancelled(self):
        if self._runner._cancel_event and self._runner._cancel_event.is_set():
            raise asyncio.CancelledError()

    async def sleep(self, seconds):
        self.check_cancelled()
        await asyncio.sleep(seconds)
        self.check_cancelled()


async def execute_script(runner, step):
    from app.services.steps.base import StepResult

    validate_script(step)
    if not getattr(runner, "_python_worker", False):
        raise RuntimeError("Python blocks require the supervised execution queue")
    def resolve(value):
        if isinstance(value, str):
            for name in re.findall(r"{{\s*([\w.-]+)\s*}}", value):
                if name not in runner.variables:
                    raise ValueError(f"Python input variable is missing: {name}")
            return runner._apply_template_recursive(value)
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        return value
    ctx = ScriptContext(runner, resolve(step.get("inputs", {})))
    scope = {"__name__": "camouflow_script"}
    runner._worker_emit({"type": "python_start", "timeout_ms": step.get("timeout_ms", 60000),
                         "code": step["code"], "inputs": dict(ctx.inputs)})
    try:
        exec(compile(step["code"], "scenario_script.py", "exec"), scope)
        async with asyncio.timeout(step.get("timeout_ms", 60000) / 1000):
            result = await scope["main"](ctx)
        ctx.check_cancelled()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_RESULT_BYTES:
            raise ValueError("Python result exceeds 1 MiB")
        key = step.get("result_variable", "").strip()
        if key:
            runner.variables[key] = result if isinstance(result, str) else encoded
            await runner._persist_profile_vars()
        runner._worker_emit({"type": "python_result", "result": result, "variable": key})
        return StepResult.next()
    except Exception:
        detail = traceback.format_exc(limit=12)[-32768:]
        runner.logger.error("%s", detail)
        raise RuntimeError(detail) from None
    finally:
        runner._worker_emit({"type": "python_end"})
