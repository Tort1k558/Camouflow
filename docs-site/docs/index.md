---
order: 100
---
# CamouFlow

CamouFlow is a local-first desktop workspace for isolated browser profiles and reusable automation on Camoufox and CloakBrowser.

## AI workflows

Describe a task, inspect structured data, then replay a reviewed parameterized workflow without another model request. Start with a separate demo profile and a synthetic catalog; no personal profile is needed.

[Try the AI catalog demo](ai-agent.md) · [Download the Windows release](https://github.com/Tort1k558/Camouflow/releases/latest)

AI page data goes to your configured provider. Model-reported success is distinct from a read-only replay check; review interactive scenarios before running them.

## Features

- Stores profiles (accounts) and their assigned proxies.
- Imports profiles in bulk using a configurable account template.
- Uses tags to group profiles and run scenarios for the selected tag.
- Edits scenarios as a chain of steps (transitions, nested scenarios, variables).
- Supports shared variables to exchange data across profiles/runs.
- Manages proxy pools with health checks, selection, release and removal actions.
- Keeps execution logs.

## Data locations

- Profiles: `settings/accounts.json`
- Scenarios: `scenaries/*.json`
- Settings: `settings/settings.json`
- Browser profile folders: `profiles/`
- Scenario outputs (write_file): `outputs/`
- Logs: `logs/`
