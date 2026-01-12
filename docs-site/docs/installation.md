---
order: 90
---
# Installation and run

## Requirements

- Windows
- Python (recommended: use `.venv`)

## Run the app

1. Create and activate a virtual environment.
2. Install project dependencies.
3. Run `main.py`.

Example (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requiremensts
python main.py
```

## Documentation (Retype)

Node.js (LTS) and npm are required.

Install Retype:

```powershell
cd docs-site
npm install retypeapp --save-dev
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
