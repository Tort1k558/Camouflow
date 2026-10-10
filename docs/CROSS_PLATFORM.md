# Native platform verification

Windows remains the published desktop release. Linux and macOS are development
targets: adding a CI matrix is not proof that either platform is ready for release.
Check the exact commit's `desktop` workflow before using its native artifacts.

## Latest observed platform evidence — 2026-10-11

For source `a0c16c4`, desktop CI run
[38093125586](https://github.com/Tort1k558/Camouflow/actions/runs/38093125586)
passed the Windows/Linux native packaging jobs. Downloaded runtime reports for
both platforms confirmed real Camoufox/CloakBrowser execution, imports and
hard-loop timeout enforcement. These are development artifacts, not stable releases.

macOS passed its first Python/QML job but failed the repeated pre-build test gate:
switching Tasks/Scenarios pages could destroy a context while offscreen list
delegates were still being created. No macOS package was published by that run.
[Qt incubation](https://doc.qt.io/qt-6/qqmlincubator.html) can continue creating
offscreen list delegates across rendering frames.

The issue was reproduced locally with a populated task list and 100 rapid page
switches. Lists now release their models during destruction to cancel pending
delegates before their Loader context is destroyed. Unchanged task searches and
refreshes also avoid redundant model resets and search-field binding loops.
The same local probe now reports zero QML warnings; the new regression fails on
the preceding source and passes with the fix. The full local suite passed 607
tests. A fresh native CI run is still required to confirm macOS readiness.

## What CI verifies

The existing full Python tests and QML page/interaction smoke run on Windows,
Ubuntu 22.04 and the current GitHub-hosted macOS runner. After all three pass,
native packaging runs on each OS, using the project's pinned dependencies.
`scripts/verify_release.py --build --runtime` checks the actual packaged executable
with both Camoufox and CloakBrowser, including runtime timeout enforcement.

Packages are uploaded only after these checks succeed. Linux and macOS use
tar archives to preserve executable modes and macOS app symlinks. Artifact names
include the runner OS and architecture. They are CI artifacts, not stable releases.

Builds are native, not cross-compiled. The macOS output is `CamouFlow.app`; it has
no Developer ID identity or notarization. PyInstaller may apply the platform's
required ad-hoc signature. Gatekeeper acceptance is not established by CI.

## Storage

- Windows and source checkouts keep the existing data-root behavior.
- Packaged macOS uses `~/Library/Application Support/CamouFlow`.
- Packaged Linux uses `$XDG_DATA_HOME/CamouFlow`, or
  `~/.local/share/CamouFlow` when the variable is unset. A relative XDG path is
  rejected instead of silently writing to another location.
- `CAMOUFLOW_DATA_DIR` remains an explicit override. `CAMOUFLOW_PORTABLE=1` or
  `portable.flag` explicitly selects storage beside the executable.

No existing profiles are moved automatically. To use an existing workspace,
configure the explicit data-directory override before starting the application.
Protect that directory: it contains browser state and local provider credentials.

## Local build

Install `requirements.txt` and `pytest` into a virtual environment, then run:

```shell
python scripts/verify_release.py --python /absolute/path/to/venv/python --build --runtime
```

On Windows the existing default `.venv/Scripts/python.exe` and `build.bat` remain
valid. On Unix the default is `.venv/bin/python`. Browser downloads require network
access. Linux needs the browser and Qt system libraries installed by the workflow.

Passing headless CI does not prove every desktop environment, display server,
GPU configuration, proxy or macOS security prompt works. Do not describe these
as universally supported platforms without further native user-session testing.

References: [PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html)
and [native-build requirements](https://pyinstaller.org/en/latest/).
