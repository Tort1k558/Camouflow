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
| P2 | Saved task navigation/input UX | Implemented | Search by name/description, preserves selected task and input draft; real Qt screenshots and tests |
| P2 | Run results/search/filter usability | Pending | Reuse current queue/history, avoid new execution architecture |
| P2 | Queue/storage failure and concurrency audit | Implemented initial safeguards | Reproduced disk-write failure leaving running job with no worker; rollback, pause and visible errors added |
| P2 | Useful server functionality | Pending | Select from observed workflow gaps, preserve RBAC |
| P2 | Current-source browser and packaging smoke | Verified through d49930f | Clean Windows build, both fresh engine/Python reports passed, isolated packaged GUI startup passed |

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

## Iteration 2 — saved task search and production reset UX

- Added Tasks search using existing `SearchBox` and cached `DictListModel` rows,
  following Profiles search patterns. Case-insensitive name/description matching;
  no cloud request per keystroke. No-results state does not clear task selection
  or user input. UI column width is bounded after screenshot verification exposed
  an expanding-column layout issue during development.
- Regression: Unicode/description search and source refresh; existing real-QML
  task test now checks filtering, no-results, draft preservation and geometry.
  Task input tests: **23 passed**; QML tests: **4 passed**; full desktop suite
  before the final geometry assertions: **136 passed**. Final full suite pending.
- Private server frontend: removed new-password field from the reset-link request
  stage; token confirmation retains new/repeat inputs with associated labels,
  appropriate autocomplete and accessible error feedback. Build passed.
- Local built-browser checks: request success, mismatch validation, confirmation
  success/redirect, using synthetic intercepted API responses only.
- Source comparison confirmed only `App.tsx` differed from deployed frontend.
  Frontend assets published without restarting any service. New hashes uploaded
  before atomic index replacement; old assets retained for existing clients.
  Production browser verified both reset form stages at 375px; health remains ok.
- Private rollback backup: `/opt/camouflow/frontend-backup-20261009T224346Z/`.
  Host source/dist and running container dist updated. Current image is unchanged:
  recreating from the old image reverts the frontend until a controlled rebuild.
- Created/pushed commits `6b07975` (cancellation history) and `4a2dead` (CI coverage).
  Fresh GitHub workflow outcomes still need inspection.

## Iteration 3 — persistence failures and cloud status compatibility

- Reproduced queue startup write failure: `running`, one active profile, zero
  workers. Execution state now persists before registering active work; a failed
  write restores pending state and pauses new starts. The Qt timer catches and
  reports failures rather than allowing exceptions to escape the event loop.
- Enqueue, configuration, queue cleanup, pending cancellation and history writes
  roll back in-memory changes if their atomic write fails. Completed browser work
  cannot be rolled back: keep its result in memory, pause, log a safe diagnostic
  and still record independent history. History callback failures are no longer
  silent; diagnostics omit exception payloads to avoid leaking sensitive data.
- Storage faults now have deterministic regression tests including pending
  cancellation and history retention. Combined desktop/backend tests:
  **218 passed**, one existing backend deprecation warning. Focused Ruff critical
  rules passed; release build/runtime verification currently running.
- Cloud compatibility bug reproduced: API rejected desktop `canceled` statuses
  with HTTP 400. Private backend now accepts `canceled` and `interrupted` as terminal
  statuses and timestamps them. Four status tests plus RBAC/team/invalid-status
  regressions pass. Runtime verified in a separate temporary VPS container with
  **no network**, read-only image, synthetic credentials and tmpfs SQLite; all four
  terminal statuses passed. Temporary container stopped/removed after verification.
  **Production API remains unchanged**; private code is not committed or pushed.
- GitHub CI is freshly green for both `4a2dead` and `471de99`.
- Final iteration-2 desktop suite was **136 passed**, including geometry checks;
  task search committed and pushed as `471de99`.
- Post-frontend-deploy landing has no document overflow at 375px; desktop
  screenshot captured at 1440px. No production service restarted.

## Iteration 4 — release proof, docs and private security fixes

- `scripts/verify_release.py --build --runtime`: **passed**, desktop **145 tests**.
  Build: `dist/release-20261010-024802/CamouFlow/CamouFlow.exe`. Fresh reports for
  Camoufox and CloakBrowser both have `passed: true`; real browser/import and hard
  timeout checks passed. Packaged GUI stayed running for five seconds with a
  disposable offscreen workspace. Optional PyInstaller warnings for unused
  PySide6/undetected_playwright were observed; both required engines worked.
- Corrected timestamped build paths in both READMEs and installation docs;
  documentation install uses pinned `npm ci`, not adding dependencies.
- Private production docs source corrected unsupported `wait_load`, `fill` and
  `tabs` action names; added supported recorded/Python actions, queue resume and
  storage locations. Publication pending; currently only locally built.
- Private security review found and reproduced concurrent refresh token reuse
  (`200,200`) and previously issued reset reactivating an inactive account.
  Conditional atomic token consumption fixes refresh/reset races. Blocking now
  invalidates old reset/refresh tokens; existing `created_by` preserves new
  authorized administrator recovery without a schema change. Auth suite:
  **12 passed**, including simultaneous requests and recovery boundaries.
- React client shares one in-flight refresh and prevents token restoration after
  logout. Actual Node 24 module checks passed for three parallel API calls and
  logout during refresh; frontend build passed.
- Built web HTML gets CSP/frame/referrer/nosniff headers locally. Live production
  inspection confirmed their prior absence. API/Swagger serving stays unchanged.
  Backend suite before the latest reset additions: **81 passed**. Updated full
  private suite and isolated PostgreSQL runtime proof pending.
- `d49930f` fresh GitHub desktop CI is green. Production API security/status changes
  are not yet deployed; no production API restart or migration performed.
