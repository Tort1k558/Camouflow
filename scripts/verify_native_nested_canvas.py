"""Owned nested-worker Canvas fixtures; no identity or anti-bot admission."""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

from scripts.verify_native_canvas import READ
from scripts.verify_native_worker_startup import NESTED_CASES

PARENT_PATH = "/surface-nested-parent.js"
CHILD_PATH = "/surface-nested-child.js"
PROBE = """async ({url, parentType, parentId, childId}) => {
  let worker;
  try {
    return await new Promise(resolve => {
      const timer = setTimeout(() => resolve({status: 'timeout'}), 15000);
      const finish = value => { clearTimeout(timer); resolve(value); };
      worker = new Worker(url, {type: parentType});
      worker.onmessage = event => finish({status: 'reply', ...event.data});
      worker.onerror = event => { event.preventDefault(); finish({status: 'worker-error'}); };
      worker.postMessage('probe');
    });
  } finally { worker?.terminate(); }
}"""


def fixture_source(path: str, query: dict[str, list[str]]) -> str:
    required = {"id", "type"} | ({"childId", "childType"} if path == PARENT_PATH else set())
    if path not in {PARENT_PATH, CHILD_PATH} or set(query) != required:
        raise ValueError("Unknown nested Canvas fixture")
    if any(not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str)
           for values in query.values()):
        raise ValueError("Nested Canvas fixture parameters must be unique")
    identifier, script_type = query["id"][0], query["type"][0]
    if not re.fullmatch(r"[0-9a-f]{32}", identifier) or script_type not in {"classic", "module"}:
        raise ValueError("Invalid nested Canvas execution identifier or script type")
    prefix = "export {};\n" if script_type == "module" else ""
    # Start readback in the script body, before any message or awaited network event.
    prefix += f"const read = {READ};\nconst first = read();\n"
    prefix += f"const executed = fetch('/surface-executed?id={identifier}');\n"
    if path == CHILD_PATH:
        return prefix + f"""
self.onmessage = async () => {{
  try {{
    await executed;
    self.postMessage({{id: {json.dumps(identifier)}, first: await first, repeat: await read()}});
  }} catch (error) {{ self.postMessage({{error: String(error)}}); }}
}};
"""
    child_id, child_type = query["childId"][0], query["childType"][0]
    if (not re.fullmatch(r"[0-9a-f]{32}", child_id) or child_id == identifier
            or (script_type, child_type) not in NESTED_CASES):
        raise ValueError("Invalid nested Canvas child")
    child_url = CHILD_PATH + "?" + urlencode({"id": child_id, "type": child_type})
    return prefix + f"""
const child = new Worker({json.dumps(child_url)}, {{type: {json.dumps(child_type)}}});
child.onmessage = async event => {{
  try {{
    await executed;
    self.postMessage({{id: {json.dumps(identifier)}, parent: {{first: await first, repeat: await read()}},
      child: event.data}});
  }} catch (error) {{ self.postMessage({{error: String(error)}}); }}
  finally {{ child.terminate(); }}
}};
child.onerror = event => {{ event.preventDefault(); child.terminate(); self.postMessage({{error: 'child-error'}}); }};
self.onmessage = () => child.postMessage('probe');
"""


def serve_fixture(handler) -> bool:
    parsed = urlsplit(handler.path)
    if parsed.path not in {PARENT_PATH, CHILD_PATH}:
        return False
    try:
        query = parse_qs(parsed.query, keep_blank_values=True)
        body = fixture_source(parsed.path, query).encode("utf-8")
    except ValueError:
        handler.send_error(400, "Invalid nested Canvas fixture")
        return True
    handler.server.record(query["id"][0], "requests")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    return True


def validate_observation(observed: dict, expected: dict, *, parent_id: str, child_id: str) -> None:
    if (not isinstance(observed, dict) or set(observed) != {"status", "id", "parent", "child", "counts"}
            or observed["status"] != "reply" or observed["id"] != parent_id):
        raise ValueError("Nested Canvas parent did not return an exact owned reply")
    if observed["counts"] != {"parent": {"requests": 1, "executions": 1},
                              "child": {"requests": 1, "executions": 1}} or any(
            type(value) is not int for counts in observed["counts"].values() for value in counts.values()):
        raise ValueError("Nested Canvas must execute both worker bodies exactly once")
    for role, fields in (("parent", {"first", "repeat"}), ("child", {"id", "first", "repeat"})):
        values = observed[role]
        if not isinstance(values, dict) or set(values) != fields:
            raise ValueError("Nested Canvas first-script and repeated measurements are incomplete")
        if role == "child" and values["id"] != child_id:
            raise ValueError("Nested Canvas reply came from another child")
        if values["first"] != expected or values["repeat"] != expected:
            raise ValueError(f"Nested Canvas readback disagrees with the same-partition dedicated worker: {role}")


async def observe(page, server, expected: dict, evidence: dict) -> dict:
    results = {}
    for parent_type, child_type in NESTED_CASES:
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        query = urlencode({"id": parent_id, "type": parent_type, "childId": child_id, "childType": child_type})
        observed = await asyncio.wait_for(page.evaluate(PROBE, {
            "url": PARENT_PATH + "?" + query, "parentType": parent_type,
            "parentId": parent_id, "childId": child_id,
        }), timeout=25)
        observed["counts"] = {"parent": server.counts(parent_id), "child": server.counts(child_id)}
        name = f"{parent_type}-{child_type}"
        evidence[name] = {"passed": False, "observed": observed}
        validate_observation(observed, expected, parent_id=parent_id, child_id=child_id)
        evidence[name]["passed"] = True
        # Keep raw identifiers in evidence but not in restart equality comparisons.
        results[name] = {"parent": observed["parent"],
            "child": {key: value for key, value in observed["child"].items() if key != "id"}}
    return results
