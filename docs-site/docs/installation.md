---
order: 90
---
# Installation and run

## Requirements

- Windows
- Python 3.12 (use the project `.venv`)

## Run the app

1. Create and activate a virtual environment.
2. Install project dependencies.
3. Run `main.py`.

Example (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Documentation (Retype)

Node.js (LTS) and npm are required.

Install the pinned documentation dependencies:

```powershell
cd docs-site
npm ci
```

Local preview:

```powershell
cd docs-site
npx retype watch
```

Build a static site:

```powershell
cd docs-site
npx retype build
```

Retype config is in `docs-site/retype.yml`. By default, sources are in `docs-site/docs/` and output is `docs-site/site/`.

## Windows build and verification

Run `build.bat` from the repository. Every build gets its own timestamped output:
`dist/<build-id>/CamouFlow/CamouFlow.exe`; previous builds and workspaces are retained.

For a clean build plus real packaged-browser/Python checks on both engines:

```powershell
.\.venv\Scripts\python.exe scripts/verify_release.py --build --runtime
```

The verifier runs the tests and requires fresh successful JSON reports from both
engines. Native Python is trusted code, not a sandbox. The runtime smoke uses
disposable synthetic profiles and does not operate personal browser accounts.
