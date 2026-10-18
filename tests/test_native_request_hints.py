from copy import deepcopy
import json
import threading
from urllib.request import urlopen

import pytest

from app.core.native.diagnostics import _hint_brands, audit_observed_request_identity


def test_identity_versioned_library_check_closes_context_before_page_measurement(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from scripts import verify_native_identity as identity

    executable = tmp_path / "chrome.exe"
    libraries = tmp_path / "148.0.7778.96"
    measure = Mock(return_value={"chrome.exe": "a" * 64})
    monkeypatch.setattr(identity, "measure_runtime_core", measure)
    context = SimpleNamespace(browser=SimpleNamespace(version="149.0.0.0"), close=AsyncMock())
    launch = AsyncMock(return_value=context)

    class Driver:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(identity, "async_playwright", Driver)
    with pytest.raises(ValueError, match="DLL directory"):
        asyncio.run(identity.verify(executable, tmp_path, "http://127.0.0.1", [], library_directory=libraries))
    measure.assert_called_once_with(executable, libraries)
    context.close.assert_awaited_once()


def coherent_request():
    brands = [{"brand": "Chromium", "version": "148"}, {"brand": 'Not"A\\Brand', "version": "99"}]
    versions = [{"brand": value["brand"], "version": "148.0.7778.96" if value["brand"] == "Chromium" else "99.0.0.0"}
                for value in brands]
    document = {"userAgent": "Chrome/148.0.0.0", "language": "en-US",
                "userAgentData": {"platform": "Windows", "mobile": False, "brands": brands},
                "userAgentHighEntropy": {"architecture": "x86", "bitness": "64", "model": "",
                    "platformVersion": "19.0.0", "wow64": False, "formFactors": ["Desktop"],
                    "fullVersionList": versions}}
    headers = {"User-Agent": document["userAgent"], "Accept-Language": "en-US,en;q=0.9",
               "Sec-CH-UA-Platform": '"Windows"', "Sec-CH-UA-Mobile": "?0"}
    for name, values in (("Sec-CH-UA", brands), ("Sec-CH-UA-Full-Version-List", versions)):
        headers[name] = ", ".join(f'{json.dumps(value["brand"])};v={json.dumps(value["version"])}' for value in values)
    for header, key in (("Sec-CH-UA-Arch", "architecture"), ("Sec-CH-UA-Bitness", "bitness"),
                        ("Sec-CH-UA-Model", "model"), ("Sec-CH-UA-Platform-Version", "platformVersion")):
        headers[header] = json.dumps(document["userAgentHighEntropy"][key])
    headers["Sec-CH-UA-WoW64"] = "?0"
    headers["Sec-CH-UA-Form-Factors"] = '"Desktop"'
    return headers, {"document": document}


def test_strict_request_hints_accept_native_values_and_escaped_grease_without_order_assumptions():
    headers, observed = coherent_request()
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True) == []
    observed["document"]["userAgentData"]["brands"].reverse()
    observed["document"]["userAgentHighEntropy"]["fullVersionList"].reverse()
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True) == []


@pytest.mark.parametrize("header", ["Sec-CH-UA", "Sec-CH-UA-Full-Version-List", "Sec-CH-UA-Arch",
    "Sec-CH-UA-Bitness", "Sec-CH-UA-Model", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors"])
@pytest.mark.parametrize("missing", [False, True])
def test_strict_request_hints_require_each_measured_header_and_reject_contradictions(header, missing):
    headers, observed = coherent_request()
    if missing:
        del headers[header]
    else:
        headers[header] = "invented"
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True)


@pytest.mark.parametrize("invalid", ['"Chromium"', '"Chromium";v="148",', '"Chromium";v="148" junk',
    '"Chromium";v=148', '"Chromium";v="148";v="99"', '"bad\\q";v="148"',
    '"bad\nbrand";v="148"', '"badé";v="148"', '"Chromium";v="148"' * 1000])
def test_hint_brand_parser_rejects_ambiguous_unbounded_or_non_structured_values(invalid):
    with pytest.raises(ValueError):
        _hint_brands(invalid)


def test_hint_brand_parser_preserves_multiplicity_and_observation_budget():
    assert _hint_brands('"Chromium"; v="148", "Chromium";v="148"') == [("Chromium", "148")] * 2
    with pytest.raises(ValueError):
        _hint_brands(", ".join('"Chromium";v="148"' for _ in range(17)))
    headers, observed = coherent_request()
    headers["Sec-CH-UA"] += ', "Chromium";v="148"'
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True)


@pytest.mark.parametrize("mutation", ["missing-high", "invalid-brands", "non-ascii", "invalid-wow64", "invalid-form-factors"])
def test_strict_request_hints_do_not_invent_missing_or_malformed_js_observations(mutation):
    headers, observed = coherent_request()
    document = observed["document"]
    if mutation == "missing-high":
        del document["userAgentHighEntropy"]
    elif mutation == "invalid-brands":
        document["userAgentData"]["brands"] = [{"brand": "Chromium", "version": 148}]
    elif mutation == "non-ascii":
        document["userAgentHighEntropy"]["model"] = "é"
    elif mutation == "invalid-wow64":
        document["userAgentHighEntropy"]["wow64"] = 0
    else:
        document["userAgentHighEntropy"]["formFactors"] = "Desktop"
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True)


def test_strict_request_hint_audit_preserves_inputs_and_legacy_default_scope():
    headers, observed = coherent_request()
    before = deepcopy((headers, observed))
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True) == []
    assert (headers, observed) == before
    for name in list(headers):
        if name.lower() not in {"user-agent", "accept-language", "sec-ch-ua-platform", "sec-ch-ua-mobile"}:
            del headers[name]
    assert audit_observed_request_identity(headers, observed) == []
    assert audit_observed_request_identity(headers, observed, strict_client_hints=True)


@pytest.mark.parametrize("contradiction", [False, True])
def test_native_identity_runner_strict_mode_checks_real_echo_against_metadata(contradiction):
    from scripts.verify_native_identity import validate_observation

    headers, values = coherent_request()
    document = values["document"]
    baseline = {"userAgent": "HeadlessChrome/148.0.0.0", "language": "en-US",
        "userAgentData": document["userAgentData"], "metadata": document["userAgentHighEntropy"],
        "headers": {name.lower(): value for name, value in headers.items()},
        "getter": "function get userAgent() { [native code] }", "ownProperty": False,
        "illegalInvocation": True, "plugins": ["PDF Viewer"], "chromeType": "object"}
    baseline["headers"]["user-agent"] = baseline["userAgent"]
    observed = deepcopy(baseline)
    observed["userAgent"] = observed["headers"]["user-agent"] = "Chrome/148.0.0.0"
    if contradiction:
        observed["headers"]["sec-ch-ua-arch"] = '"arm"'
        with pytest.raises(ValueError, match="request/JS identity contradictions"):
            validate_observation(observed, baseline, protected=True, worker=False, strict_client_hints=True)
    else:
        validate_observation(observed, baseline, protected=True, worker=False, strict_client_hints=True)


@pytest.mark.parametrize("strict", [False, True])
def test_owned_identity_fixture_delegates_http_hints_only_when_requested(strict):
    from scripts.verify_native_identity import HINT_POLICY_FEATURES, IdentityFixtureHandler, delegated_hint_policy
    from scripts.verify_native_runtime import FixtureServer

    server = FixtureServer(("127.0.0.1", 0), IdentityFixtureHandler)
    server.strict_client_hints = strict
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as response:
            policy = response.headers.get("Permissions-Policy")
            assert response.headers["Accept-CH"]
            if strict:
                assert policy == delegated_hint_policy(server.server_port)
                assert "*" not in policy
                assert policy.count(f'"http://localhost:{server.server_port}"') == len(HINT_POLICY_FEATURES)
            else:
                assert policy is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("port", [True, 0, 65536, "80\r\nInjected"])
def test_hint_delegation_rejects_invalid_or_injectable_origins(port):
    from scripts.verify_native_identity import delegated_hint_policy

    with pytest.raises(ValueError):
        delegated_hint_policy(port)
