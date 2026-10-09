# Autonomous development — 2026-10-10

## Mission and boundaries

Continuous product development until **10:00 Samara (06:00 UTC), 2026-10-10**.
Work on `feat/autonomous-product-20261010`; keep `main` stable. Commit and push
small verified desktop changes. The private sibling `../server/` is outside this
repository: never add or push backend sources, credentials or deployment bundles.
Do not delete user data, touch unrelated VPN services, or run irreversible
production changes. Production updates need backups, rollback and smoke checks.

## Initial evidence

- Clean desktop checkout, `HEAD == origin/main == 37207b9` at start.
- Desktop: PyQt6/QML, local storage, two browser engines; existing queue,
  recorder, task forms/CSV batches, Python workers and optional cloud sync.
- Private backend: FastAPI/SQLAlchemy/Alembic, PostgreSQL, React/Vite console.
- Desktop baseline: **132 passed**, project `.venv`, 2026-10-10 02:37 Samara.
- SSH production inspection: API and PostgreSQL healthy; root disk 43% used;
  `/health` reports `ok`, production. Unrelated VPN/Caddy containers preserved.
- Real production browser opened successfully; landing has RU/EN, feature tabs,
  console and documentation links. More interaction/responsive checks pending.
- CI currently excludes `tests/**` from desktop workflow path triggers, and the
  QML page loop does not visit Tasks. These are test coverage gaps.
- Queue cancellation of pending jobs updates the queue but does not notify the
  history recorder. Clearing finished jobs can erase their cancellation record.
- Queue history callback exceptions are silently discarded: investigate error
  visibility and persistence failures before broader changes.

## Prioritized backlog

| Priority | Work | Status | Reason / verification |
| --- | --- | --- | --- |
| P1 | Preserve canceled pending jobs in history | Implemented | Reproduced empty history after cancel/clear; 6 history tests pass, including workspace/idempotence/running-cancel checks |
| P1 | CI test triggers and Tasks QML coverage | Implemented | Tests/pytest.ini trigger desktop CI; all 13 pages including Tasks load warning-free locally |
| P1 | Production functional/responsive audit | In progress | Browser flows, docs/API, auth boundaries; no real-account automation |
| P1 | Backend baseline and source/runtime comparison | In progress | Isolated test database; inspect deployed vs local source |
| P2 | Saved task navigation/input UX | Pending | Inspect actual Qt rendering before UI changes |
| P2 | Run results/search/filter usability | Pending | Reuse current queue/history, avoid new execution architecture |
| P2 | Queue/storage failure and concurrency audit | Pending | Prevent silent data loss and stuck reservations |
| P2 | Useful server functionality | Pending | Select from observed workflow gaps, preserve RBAC |
| P2 | Current-source browser and packaging smoke | Pending | Fresh reports, real Camoufox/CloakBrowser synthetic scenarios |

## Research direction

Keep local-first recorded tasks and deterministic replay as the core product.
Use Playwright locators and traces for reproducibility, not model claims alone:
[locators](https://playwright.dev/python/docs/locators),
[trace viewer](https://playwright.dev/python/docs/trace-viewer).
Compare reusable workflow UX with
[Browser Use workflows](https://docs.cloud.browser-use.com/usage/workflows-beta),
without introducing a second orchestration system.

## Continuation

Read this document and inspect `git status` before every new iteration. Use
`.venv/Scripts/python.exe` from the desktop repository. Backend tests run from
the parent workspace and use their existing isolated SQLite fixtures. Never
read or print `.env`, provider keys, cookies or account variables. SSH credentials
are supplied in the chat only; do not persist them in files or commits.
Update this log with actual command results, commit IDs, remaining risks and
rollback details. Keep local test proof separate from production/CI proof.

## Iteration 1 — cancellation history

Pending canceled jobs now invoke the same history callback as completed worker
jobs, after the queue is persisted and outside its lock. Repeated cancellation
does not duplicate callbacks; active jobs are still recorded only after worker
cleanup. `tests/test_run_history.py`: **6 passed**. Initial private backend
baseline: **68 passed**, one existing SQLAlchemy `Query.get` deprecation warning.
Production proxy feature tab and EN language control both responded in the real
browser. No production mutations performed.

Full desktop suite after this fix: **135 passed**; `compileall` passed. Independent
offscreen QML smoke loaded all **13 pages** (including Tasks) without warnings.
This proves local QML loadability, not visual quality or fresh GitHub CI.
