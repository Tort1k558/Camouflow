"""Headless binary startup checks using owned disposable profiles."""

import tempfile
from pathlib import Path

from .configuration import NativeConfiguration
from .runtime import NativeRuntime


async def probe_native_binary(executable: Path, configuration: NativeConfiguration, work_dir: Path) -> str:
    configuration.validate()
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise ValueError("Configure an installed Native Chromium executable")
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-health-", dir=work_dir.resolve()) as owned:
        runtime = NativeRuntime(Path(owned), executable, configuration)
        try:
            context = await runtime.start(headless=True)
            version = context.browser.version
            if not isinstance(version, str) or not version.strip():
                raise ValueError("Native browser did not report its version")
        finally:
            await runtime.close()
    return version
