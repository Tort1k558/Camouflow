from __future__ import annotations

import asyncio
from copy import deepcopy
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from scripts import verify_native_nested_canvas as probe
from scripts.verify_native_surfaces import SurfaceFixtureServer

PARENT = "a" * 32
CHILD = "b" * 32
EXPECTED = {"pixels": "c" * 64, "repeat": "c" * 64, "blob": "c" * 64,
            "htmlBlob": None, "htmlDataUrl": None, "htmlCapture": None,
            "geometry": {"partialReadback": True}, "errors": {"zeroSize": "IndexSizeError"}}


def observation():
    return {"status": "reply", "id": PARENT,
            "parent": {"first": deepcopy(EXPECTED), "repeat": deepcopy(EXPECTED)},
            "child": {"id": CHILD, "first": deepcopy(EXPECTED), "repeat": deepcopy(EXPECTED)},
            "counts": {"parent": {"requests": 1, "executions": 1},
                       "child": {"requests": 1, "executions": 1}}}


@pytest.mark.parametrize("parent_type,child_type", probe.NESTED_CASES)
def test_nested_canvas_reads_in_first_script_before_messages(parent_type, child_type):
    parent = probe.fixture_source(probe.PARENT_PATH, {
        "id": [PARENT], "type": [parent_type], "childId": [CHILD], "childType": [child_type]})
    child = probe.fixture_source(probe.CHILD_PATH, {"id": [CHILD], "type": [child_type]})
    for source, script_type in ((parent, parent_type), (child, child_type)):
        assert source.startswith("export {};\n") is (script_type == "module")
        assert source.index("const first = read();") < source.index("self.onmessage")
        assert "repeat: await read()" in source
    assert parent.index("const first = read();") < parent.index("new Worker(")
    assert "child.terminate()" in parent
    assert f"id={CHILD}&type={child_type}" in parent


@pytest.mark.parametrize("change", ["duplicate", "blank", "unknown", "same-id", "unknown-type"])
def test_nested_canvas_rejects_ambiguous_fixture_requests(change):
    query = {"id": [PARENT], "type": ["classic"], "childId": [CHILD], "childType": ["module"]}
    if change == "duplicate":
        query["id"].append(PARENT)
    elif change == "blank":
        query["id"] = [""]
    elif change == "unknown":
        query["unreviewed"] = ["value"]
    elif change == "same-id":
        query["childId"] = [PARENT]
    else:
        query["childType"] = ["unreviewed"]
    with pytest.raises(ValueError):
        probe.fixture_source(probe.PARENT_PATH, query)


@pytest.mark.parametrize("change", [None, "parent-id", "child-id", "missing-repeat", "first-differs",
                                    "repeat-differs", "boolean-count", "duplicate-execution", "timeout"])
def test_nested_canvas_validator_requires_complete_consistent_owned_reads(change):
    observed = observation()
    if change == "parent-id":
        observed["id"] = CHILD
    elif change == "child-id":
        observed["child"]["id"] = PARENT
    elif change == "missing-repeat":
        del observed["child"]["repeat"]
    elif change == "first-differs":
        observed["parent"]["first"]["pixels"] = "d" * 64
    elif change == "repeat-differs":
        observed["child"]["repeat"]["blob"] = "d" * 64
    elif change == "boolean-count":
        observed["counts"]["parent"]["executions"] = True
    elif change == "duplicate-execution":
        observed["counts"]["child"]["executions"] = 2
    elif change == "timeout":
        observed = {"status": "timeout", "counts": observed["counts"]}
    if change is None:
        probe.validate_observation(observed, EXPECTED, parent_id=PARENT, child_id=CHILD)
    else:
        with pytest.raises(ValueError):
            probe.validate_observation(observed, EXPECTED, parent_id=PARENT, child_id=CHILD)


@pytest.mark.parametrize("fail", [False, True])
def test_nested_canvas_retains_raw_failed_evidence_and_ignores_ids_only_for_restart(fail):
    class Page:
        async def evaluate(self, javascript, arguments):
            observed = observation()
            observed["id"] = arguments["parentId"]
            observed["child"]["id"] = arguments["childId"]
            del observed["counts"]
            if fail:
                observed["child"]["first"]["pixels"] = "d" * 64
            return observed

    class Server:
        def counts(self, identifier):
            return {"requests": 1, "executions": 1}

    evidence = {}
    if fail:
        with pytest.raises(ValueError):
            asyncio.run(probe.observe(Page(), Server(), EXPECTED, evidence))
        assert len(evidence) == 1 and not next(iter(evidence.values()))["passed"]
    else:
        first = asyncio.run(probe.observe(Page(), Server(), EXPECTED, evidence))
        second = asyncio.run(probe.observe(Page(), Server(), EXPECTED, {}))
        assert first == second and len(first) == 4
        assert all(entry["passed"] for entry in evidence.values())
        assert all("id" not in entry["child"] for entry in first.values())
    assert all("id" in entry["observed"]["child"] for entry in evidence.values())


def test_nested_canvas_http_fixture_counts_fetch_separately_from_body_execution():
    server = SurfaceFixtureServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{origin}{probe.CHILD_PATH}?id={CHILD}&type=module", timeout=5) as response:
            assert response.headers["Content-Type"].startswith("application/javascript")
            assert response.read().decode("utf-8").startswith("export {};\n")
        assert server.counts(CHILD) == {"requests": 1, "executions": 0}
        with pytest.raises(HTTPError) as error:
            urlopen(f"{origin}{probe.CHILD_PATH}?id={CHILD}&type=module&type=classic", timeout=5)
        assert error.value.code == 400
        error.value.close()
        assert server.counts(CHILD) == {"requests": 1, "executions": 0}
        with urlopen(f"{origin}/surface-executed?id={CHILD}", timeout=5):
            pass
        assert server.counts(CHILD) == {"requests": 1, "executions": 1}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
