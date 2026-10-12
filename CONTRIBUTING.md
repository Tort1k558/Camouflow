# Contributing to CamouFlow

[Русская инструкция](CONTRIBUTING.ru.md)

Contributions are welcome: reproducible bug reports, documentation, accessible
UI improvements, automation integrations and tested browser-engine changes.
English and Russian reports are accepted. Follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

- Search existing issues and pull requests. Discuss large changes in an issue
  before implementation; include the user problem and proposed scope.
- Use the bug/feature templates. Share a minimal example and sanitized logs,
  never credentials, cookies, real browser profiles or private workspace data.
- Report vulnerabilities **privately**, following [SECURITY.md](SECURITY.md).

## Local development

The application uses Python 3.12, PyQt6 and QML. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest ruff
.\.venv\Scripts\python.exe main.py
```

Browser engines require their own runtime downloads/configuration; do not commit
downloaded binaries. See the [README](README.md) for application setup and
[Glint build guide](native/BUILDING.md) for the separate Chromium workspace.

## Check your changes

```powershell
.\.venv\Scripts\python.exe -m compileall -q app main.py scripts
.\.venv\Scripts\python.exe -m ruff check app --select F821,F822,F823,E9
.\.venv\Scripts\python.exe -m pytest -q
```

For packaging or runtime changes, additionally run
`scripts/verify_release.py --build --runtime` in the project environment.
It builds artifacts and runs browser checks; install/configure the required
engines first. Distinguish source tests, packaged tests and actual browser proof.

## Pull requests

- Target `main`, keep changes focused and explain their user-visible effect.
- Follow existing Python/QML architecture; reuse utilities and avoid unrelated
  refactoring or new dependencies without a clear need.
- Add regression coverage in the existing test suite and update relevant docs.
- Save text as UTF-8 without BOM. Preserve profile schemas, engine IDs and APIs
  unless the change includes a reviewed migration.
- For UI changes, attach screenshots and note desktop sizing/accessibility checks.
- For Glint patches, document upstream revision, lifecycle/partition assumptions,
  negative controls and exact native/runtime checks. Do not edit live build inputs.
  Uncompiled drafts are not verified capabilities or released functionality.

Keep private `server/` sources, credentials, personal profiles, build outputs,
machine-specific reports and autonomous work diaries out of public contributions.
Do not claim guaranteed CAPTCHA bypass, undetectability or protection that has
not been measured. The maintainer reviews compatibility and release admission.
