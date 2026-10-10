import asyncio
from pathlib import Path

import pytest

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


@pytest.mark.parametrize("values", [
    {"environment": "ios"}, {"environment": "android"}, {"width": True}, {"height": 0},
    {"device_scale_factor": float("nan")}, {"device_scale_factor": True},
    {"locale": "en_US"}, {"timezone": "invalid/zone"}, {"permissions": ("unknown",)},
    {"permissions": ({},)},
])
def test_native_configuration_rejects_unsupported_or_inconsistent_inputs(values):
    with pytest.raises(ValueError):
        NativeConfiguration(**values).context_options()


def test_mobile_web_configuration_does_not_claim_android_identity():
    configuration = NativeConfiguration(environment="mobile_web", width=390, height=844, device_scale_factor=3)
    options = configuration.context_options()
    assert options["is_mobile"] and options["has_touch"]
    assert options["viewport"] == {"width": 390, "height": 844}
    assert "user_agent" not in options
    assert "not an Android Chrome" in " ".join(configuration.limitations())
    assert options["permissions"] == []


def test_native_missing_binary_does_not_touch_profile(tmp_path):
    profile = tmp_path / "profile"
    runtime = NativeRuntime(profile, tmp_path / "missing.exe", NativeConfiguration())
    with pytest.raises(NativeRuntimeError, match="not installed"):
        asyncio.run(runtime.start())
    assert not profile.exists()


def test_native_refuses_existing_unrelated_browser_data(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    original = profile / "Preferences"
    original.write_text("customer data", encoding="utf-8")
    runtime = NativeRuntime(profile, Path(__file__), NativeConfiguration())
    with pytest.raises(NativeRuntimeError, match="own empty profile"):
        asyncio.run(runtime.start())
    assert original.read_text(encoding="utf-8") == "customer data"
    assert list(profile.iterdir()) == [original]
