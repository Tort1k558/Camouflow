# CamouFlow

CamouFlow is a desktop app for managing browser automation scenarios and profiles based on Camoufox/Playwright. It is built with PyQt6 and stores its working data locally.

![Main window](docs/images/main-window.png)

## Features

- manage profiles and accounts
- configure and run scenarios and steps
- logging and saving run results
- local storage for settings and profiles

## Installation

Requirements: Python 3.11+.

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requiremensts
```

## Run

```bash
python main.py
```

## Data locations

- settings and accounts: `settings/`
- scenarios: `scenaries/`
- profiles: `profiles/`
- run outputs: `outputs/`
- logs: `logs/`
