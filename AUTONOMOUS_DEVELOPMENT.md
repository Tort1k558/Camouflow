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
| P1 | Production functional/responsive audit | Verified anonymous and isolated paths | Current production bundle/mobile/docs checked; authenticated RBAC/auth flows use synthetic isolated APIs, not customer accounts |
| P1 | Backend baseline and source/runtime comparison | Verified and deployed | Private suite 125 passed; immutable candidates tested on disposable PostgreSQL; backups and retained upstream support rollback |
| P2 | Saved task navigation/input UX | Implemented | Search by name/description, preserves selected task and input draft; real Qt screenshots and tests |
| P2 | Run results/search/filter usability | Implemented | Collapsible scheduling, search/status filters, retained-history matching and minimum-window proof |
| P2 | Queue/storage failure and concurrency audit | Implemented initial safeguards | Reproduced disk-write failure leaving running job with no worker; rollback, pause and visible errors added |
| P2 | Useful server functionality | Team run history deployed | Correct terminal statuses/token lifecycle plus read-only team search/filter/pagination; isolated auth/RBAC/browser proof |
| P2 | Current-source browser and packaging smoke | Runtime source 6a773c1 verified | Package 091311: 452 tests, both fresh engine/Python reports and actual authenticated-proxy queue/export checks; current runtime CI successful |

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

## Iteration 5 — verified private backend publication

- Private backend full suite: **84 passed**, one pre-existing SQLAlchemy warning;
  focused critical Ruff checks passed. Added SPA-header/API-boundary tests.
- Candidate image: `camouflow-server:autonomous-20261009T225737Z`, built from the
  original image plus narrow route/frontend patches; no dependency changes.
- Verified on disposable PostgreSQL in network-isolated containers: concurrent
  refresh **5/5 rounds** (one success, one rejection), four terminal run statuses,
  stale reset invalidation and fresh administrator recovery. Temporary containers
  were stopped/removed; original services' start timestamps stayed unchanged.
- Publication was blue-green: new `server-candidate` service on loopback **18082**,
  existing original API retained on **18080**. No production API/DB/VPN restart,
  no schema migration. Caddy validated/gracefully reloaded with only CamouFlow's
  upstream changed; **80/80** healthy responses observed during the switch.
- Private rollback assets: `/opt/camouflow/deployment-backup-20261009T230041Z/`,
  readable 80-KiB PostgreSQL dump, prior Caddy/compose/source files; old image and
  old running API retained. Rollback is an in-place Caddyfile restore and graceful
  reload to 18080, without restoring the database.
- Fresh production browser verified new RU/EN docs, supported load action and
  queue storage reference, corrected reset form and zero console errors. Public
  HTML security headers and anonymous admin-API rejection verified. State-changing
  auth/status tests were isolated, not performed on real production users.
- Browser cache exposed stale HTML after deployment. Added SPA-only `no-cache`
  revalidation at the edge; old JS/CSS retained for open clients. API/assets routes
  left unchanged. Current image contains security headers; cache header at edge
  is also staged in private Python source for the next image build.
- Deployment scripting initially masked missing host `web/dist` copy errors.
  Corrected with fail-fast commands and created/verified host dist. The source
  backup contains six source files, not a dist snapshot; old image/container are
  the actual frontend rollback source. Private deployment doc records this.
- Active private compose: `/opt/camouflow/compose.autonomous-20261009T230041Z.yml`.
  Do not casually recreate/remove candidate or original: public traffic targets
  the candidate. Preserve old assets in future images. No backend file committed.
- New finding: SPA HEAD requests return 405; GET works. Track as a small web
  compatibility improvement, not a current production outage.

## Next iteration priorities (03:07 Samara)

1. Inspect real desktop Runs/profile/proxy screens, not just source/QML loading.
2. Improve run-result navigation/filtering using current queue/history models.
3. Verify authenticated console workflows on the isolated local test backend;
   choose useful team-run visibility improvements, preserving permissions.
4. Add HEAD compatibility and robust candidate/old-asset deployment procedure.
5. Continue security/storage/worker cancellation audit; prioritize reproduced bugs.
6. Build/verify docs and keep main stable; current work stays on the feature branch.

## Iteration 6 — result-first Runs UI and honest workflow smoke

- Inspected real Qt screenshots with synthetic queue/history at 1460x900 and
  minimum 1180x720. Scheduling controls pushed the run history below the fold.
  Runs now collapses scheduling behind **Add jobs**, and selected-profile entry
  automatically expands it. The form stays alive, so hiding does not lose drafts.
  Queue height adapts to short lists; unused artifact/detail controls are hidden.
  Resume/pause/concurrency/cancellation controls remain immediately available.
- Corrected artifact-button enablement for history records with absent artifact
  paths, observed in the synthetic screenshot. Model strings render as plain text.
- Existing real-QML task regression tests cover scheduling toggle and automatic
  selected-profile expansion. Full desktop suite: **147 passed**; focused QML
  suite after final layout adjustment: **4 passed**.
- An incorrectly invoked workflow verifier accepted `--engine` as an engine name
  and reported success after the browser layer normalized it. Do not count that
  output as engine proof. CLI now validates its positional engine via argparse;
  two regressions reject invalid names/options before browser/workspace creation.
- Re-ran correctly on **camoufox** and **cloakbrowser**: both actual-browser,
  fixture-LLM extraction/privacy/scrolling/parameterized replay/JSON/CLI queue
  checks reported `passed: true` with the correct engine names. This is not a
  paid-provider reasoning test. CloakBrowser announced a wrapper update; do not
  change the tested pin automatically.
- Public documentation updated for queue/resume and scheduling controls. Private
  cache/header deployment remains healthy; backend code stays outside Git.

## Iteration 7 — searchable desktop results and team run visibility

- Desktop Runs now searches scenario/profile/error text and filters statuses
  across queue and local history. Searches cover retained records, not just the
  newest 120 displayed matches. Execution/cleanup remain workspace-wide; filters
  never change jobs. Selection/details survive filtering. Identical idle models
  no longer reset, preserving scroll position during refresh.
- Regression tests cover Unicode casefold, older-history search, team isolation,
  invalid filters, unchanged job state, idle model resets and real QML wiring.
  Full desktop suite: **148 passed**. Windows Qt screenshots at 1180x720 verified
  filter placement and results with no QML warnings. Offscreen Windows renders
  font boxes; used the real Windows platform for visual proof instead.
- Current-head desktop CI `38003332010` for `20cea3b4`: **success**.
- Private team console adds read-only scenario runs with server search/status,
  stable pagination, cancellation/interruption labels, duration and error detail.
  Browser checks on isolated 105-row data verified 100+5 pages, combined filters,
  empty state, API error/recovery, in-flight team switch isolation and 375px layout.
  Fixed shared table overflow revealed by mobile testing. No remote execution or
  local artifact access is implied by this screen.
- Fixed existing timezone-offset parsing in console relative times; added SPA
  HEAD responses. Private backend suite: **93 passed**, one pre-existing legacy
  SQLAlchemy warning. Candidate image tested with isolated PostgreSQL: escaped
  wildcard search, deterministic tie ordering/pagination, workspace boundaries,
  viewer read-only permissions and HEAD/security/cache headers passed. Test-only
  HTTP client packages mounted separately; production dependencies unchanged.
- Deployed private Runs image `runs-20261009T232500Z` on loopback 18083 via
  graceful Caddy reload. Both previous APIs remain running for rollback; original
  PostgreSQL/Caddy/VPN start timestamps unchanged. New image includes old hashed
  assets. Verified root-private DB/source/Caddy backup before switching.
- Switch health probe: **79/80**, one unclassified failure (not zero-downtime
  proof). Post-switch repeat: **80/80**; public SPA HEAD/cache headers pass.
  Fresh production browser loads the new bundle and console sign-in. Authenticated
  run interactions were tested only on isolated synthetic local/PostgreSQL data.

## Iteration 8 — bounded and workspace-safe artifact inspection

- Reproduced `UnicodeDecodeError` when selecting a run with malformed Python
  output. Previously the UI read the entire file before trimming, and error JSON
  had no bound. Both previews now read at most the last 32 KiB, label truncation,
  tolerate malformed bytes and report filesystem errors without exception payloads.
- Run lookup checks current workspace even when a direct run ID is supplied.
  Screenshot links resolving outside output storage are rejected; trace-viewer
  logs are checked before writing. No external artifact upload added.
- Removed QML assignments that broke the selected-job binding after clicking
  Details; bridge-driven selection clear remains authoritative.
- Artifact/history regressions: **21 passed**, including an actual filesystem
  link escape test (not skipped on this Windows host). Full suite: **153 passed**.
  Real-QML test clicks Details and verifies bridge selection clear still propagates.
- Retype documentation build: **35 pages, 0 errors, 0 warnings** using locked
  `npm ci` and the repository's `retype.js build` command.

## Iteration 9 — consistent proxy quarantine and cancellation checkpoints

- Reproduced a naive quarantine timestamp causing `TypeError` in proxy UI. One
  shared policy now handles UI/launch quarantine consistently: invalid or timezone-
  ambiguous expiry stays quarantined until manual release; no timezone assumption.
  A malformed candidate no longer prevents trying other explicitly available
  healthy candidates. Explicit quarantine can also be released from existing UI.
- Cancellation during a blocking health probe is checked before returning a
  replacement and again before persisting assignment. A canceled job does not
  proceed merely because the probe succeeded. No direct-connection fallback.
- Browser-settings/proxy regressions: **20 passed**. Existing real launcher
  verifier: **8/8 cases passed**, both engines, auto/custom/ephemeral/blocked,
  browser restart, locale/timezone, typing, persistence and requested blockers.
  Local fixture checks, not a claim of universal anti-detection effectiveness.
  Camoufox canvas exports changed across restarts and were reported as warnings;
  this audit does not prove Camoufox canvas stability. CloakBrowser canvas was stable.
- Private auth forms now have linked labels, proper password-manager autocomplete,
  required email/password and accessible error feedback. Browser checks passed for
  sign-in/signup/invite and corrected reset-session wording. These last private
  patches are staged locally, not deployed. Backend suite now **93 passed without
  warnings** after replacing the one exercised legacy SQLAlchemy lookup.
- Full desktop suite after quarantine/cancellation changes: **163 passed**.

## Iteration 10 — non-destructive concurrent proxy checks

- Reproduced an asynchronous proxy probe restoring its stale pool snapshot: a name
  edit reverted and a newly added row disappeared. Both single/bulk checks now
  capture requested endpoints and merge only health results into latest local
  storage under the existing storage lock. Deleted/changed endpoints are not
  restored or updated; cloud switches discard local results. Duplicate endpoints
  in bulk are probed once. Bulk worker errors are reported instead of silent thread
  failure. No new dependency or parallel-check architecture.
- Six threaded regressions hold the probe while editing/deleting/replacing rows
  and adding another row, for single and bulk checks. Added cloud-switch guard.
  Full desktop suite: **170 passed**; critical Ruff checks passed.
- Updated proxy documentation to actual labels and all-pool/quarantine behavior.
- Fresh desktop CI: `38004888417` (`5cf9aaa3`) and `38004547753` (`9df28357`)
  succeeded; subsequent heads still need their own fresh CI inspection.

## Iteration 11 — desktop single-flight token refresh and atomic session storage

- Reproduced two desktop clients rotating the same refresh token concurrently,
  incompatible with the newly enforced one-use server token. Desktop refresh now
  serializes rotation and adopts an already refreshed token pair when handling a
  stale 401. Captures the token used by the failed request, including shared-client
  races; does not blindly rotate the latest token again.
- Checks session identity before/after network refresh. Logout/account/server
  change cannot resurrect or overwrite a session; changing selected team is
  preserved. Incomplete response leaves the existing saved pair untouched.
- Session fields now save in one existing atomic settings write instead of six
  separate replacements; reads take the same existing storage lock. The new bulk
  setter backs the single-setting API, preserving existing contracts.
- Focused regressions: **11 passed**. Actual HTTP against isolated local backend:
  **6 expired-token requests, 1 refresh, 6 successful replies**; logout held during
  a successful remote rotation stayed logged out. Full desktop: **181 passed**.
  No production account/session used in these state-changing checks.
- Packaged release from `6b5e411` (before these new auth changes) passed build and
  both fresh engine/Python runtime reports:
  `dist/release-20261010-033802/CamouFlow/CamouFlow.exe`.
  The latest auth changes still require a later rebuild; do not treat this package
  as current-head proof.

## Iteration 12 — web workspace isolation, error honesty and auth accessibility

- Reproduced a delayed member response showing old-team rows after switching
  workspace. Private web now remounts page state by team ID, aborts old role fetch,
  and associates role state with its team. Browser verifies old rows and owner
  role cannot populate a viewer team. Backend RBAC was never bypassed.
- Workspace list failures now show an accessible error and Retry instead of
  clearing stored selection and pretending there are zero teams. Browser verified
  failure preservation, retry recovery and initial settings hydration.
- Deployed private console image `console-20261009T235000Z` on 18082. Replaced
  only an owned, unserved earlier candidate; prior serving 18083 and original
  18080 retained. Backup/rollback verified; original API/PostgreSQL/Caddy/VPN
  starts unchanged. Models/startup/dependencies/auth/run routes byte-identical;
  private suite **93 passed, no warnings**.
- Switch health **80/80**; public SPA HEAD/cache checks passed. Fresh production
  browser validates updated sign-in/signup labels/autocomplete, reset wording and
  mobile width, with zero console errors/warnings. No production account mutation.
- Documentation rebuilt: **35 pages, zero errors/warnings**.
- Fresh CI `38005684654` (`c1e72c23`), `38005347486` (`6b5e4118`) and
  `38005203849` (`aef395f5`): **success**.

## Iteration 13 — metadata must not fetch images or become rich text

- Reproduced a profile name containing an HTML image causing one actual network
  request to an isolated loopback fixture. After explicit plain-text labels: zero
  requests and literal tag display in real Windows Qt screenshots.
- [Qt documents automatic rich-text detection and remote inline images](https://doc.qt.io/qt-6/qml-qtquick-text.html#textFormat-prop).
  Applied plain-text rendering to user/cloud/profile/proxy/scenario/marketplace
  names, descriptions, logs, metadata and shared presentation components. This is
  not a browser-JavaScript execution finding; no secret exfiltration was demonstrated.
- Native CheckBox also fetched the fixture image. Native ItemDelegate rendered
  ordinary text but crashed with an inline-image label on this Qt 6.11 host.
  Added small plain-text CheckBox/ComboBox data-label components, retaining native
  interaction/background/indicator behavior. Only untrusted-data selectors and
  checkboxes use them; engine/status option controls remain unchanged.
- Real-QML regression covers ten common components and opened selector popups
  for string arrays, object arrays and the actual DictListModel. Selection and
  activation still work, image requests remain zero, no QML warnings.
  Focused QML suite: **5 passed**. Final full suite after selector wrappers:
  **182 passed**. Current-source packaged rebuild still pending.

## Iteration 14 — credential-free proxy presentation

- Proxy list addresses and dashboard running/failure summaries displayed raw
  connection strings, including credentials. Added a display-only formatter using
  the existing proxy parser. Lists show scheme/host/port; stored connection and
  manager edit dialog remain unchanged. Invalid input never falls back to raw text.
- Tests cover nine cases: URL/legacy formats, userinfo without scheme, encoded
  passwords, IPv6, invalid port and malformed input. No real credentials used.
  Browser-settings suite: **36 passed**; critical Ruff checks passed.
  Full desktop suite: **191 passed**.
- Next reproduced finding: a newly imported `unchecked` proxy appears Active and
  increments active statistics before any probe. Fix status honesty before adding
  inventory search/filter controls.

## Iteration 15 — honest proxy health and limited cloud checks

- Reproduced an unchecked import appearing Active. Desktop now distinguishes
  Unchecked, Checking, TCP Reachable, internet Active, Failed and Quarantined;
  the stat strip includes unchecked entries and counts actual geolocation only.
  Legacy cloud check results are conservatively classified as TCP. Payloads and
  connection values are not mutated by presentation.
- Private backend adds explicit TCP mode and UTC check time to stored results.
  It still performs only the existing TCP probe, with unchanged dependencies.
  Private web masks proxy addresses/tooltips, labels TCP scope and renders 0ms
  instead of treating zero as missing. These private changes are staged locally,
  not yet deployed; the server directory remains outside public Git.
- Full desktop **193 passed**, private backend **96 passed**. Real Windows Qt
  minimum-window screenshot verifies five proxy states. Real browser on isolated
  local API verifies three states, no credential text/tooltips, zero latency and
  no document overflow at 375px. TypeScript/Vite production build passed.
- Passive production observation is running to the mission deadline. Interim
  15 rounds / 27 checks / zero failures is not a final stability result.

## Iteration 16 — cloud proxy actions retain displayed identity

- Reproduced a displayed proxy A resolving to newly inserted C because actions
  reloaded the server and addressed its current numeric position. Bulk deletion
  could also shift positions after each request and target an unselected row.
- Cloud actions now resolve IDs from the displayed snapshot, not a new list.
  Refresh clears positional selection if the cloud inventory changes. Edit and
  delete dialogs capture the cloud ID, retain it through reorder and reject
  removed identities or local/cloud/workspace changes. Existing slot signatures
  remain available; no server API or storage format changes.
- Seven regressions cover insertion, bulk deletion/reorder, refresh selection,
  missing IDs and local/cloud dialog switches. Full desktop **200 passed**;
  critical Ruff passed; real Windows Proxies page loads without QML warnings.

## Iteration 17 — proxy inventory search and status filters

- Added compact cached search and status selector using existing QML components.
  Search covers visible name/address/location/group/type, never credentials;
  Unicode casefold works. Original pool indices are retained for row actions.
  No requests per keystroke, no storage/API changes or dependencies.
- Filtering clears selection to avoid hidden bulk-action targets. Group stats
  remain unfiltered; bulk checks still cover all pools. Empty results show a
  filter-specific reset hint rather than claiming there are no connections.
- Full desktop **201 passed**. Real Windows 1180x720 check exercises search,
  status binding, reset, empty results, selection clearing and stable indices;
  screenshots reviewed, no QML warnings. Documentation updated.

## Iteration 18 — proxy credential parsing and CONNECT framing

- Reproduced encoded account credentials not round-tripping and IPv6 browser
  configuration losing brackets. Existing core parser now decodes URL userinfo,
  brackets IPv6, validates ports/schemes and accepts documented bare formats.
  Internet probe reuses this parser instead of its independent parsing logic.
- Reproduced standard HTTP CONNECT 200 without Content-Length timing out before
  TLS started. Probe now reads CONNECT headers only; authenticated HTTP forwarding
  also sends proxy auth. Authentication is never forwarded into the target tunnel.
- Baseline isolated TLS fixture timed out; fixed code passed three rounds of
  real TLS 1.3 with certificate and hostname verification enabled. This fixture
  proves framing/auth, not a real provider's egress. Unit CONNECT framing test
  deliberately mocks TLS; it is not the TLS proof.
- HTTPS-to-proxy was previously treated as plaintext. It now explicitly refuses
  unsupported TLS-to-proxy checks, without downgrading or sending credentials.
  HTTPS sites via ordinary HTTP CONNECT remain supported. No dependency added;
  [HTTPX also documents its HTTPS-proxy limitation](https://www.python-httpx.org/troubleshooting/).
- Existing BrowserInterface.start already blocked malformed proxies; retained
  that behavior, made its constructor warning truthful and added launch-guard
  regressions. A proposed early constructor raise was discarded after auditing
  call sites, avoiding a new UI exception/lock-leak contract.
- Focused **59 passed**; final full desktop **214 passed**. Both actual source
  engine AI-workflow verifiers returned passed:true (fixture LLM, no paid provider).
- Private backend now parses documented legacy/IPv6 TCP endpoints without
  echoing credentials in format errors. New proxy-update audit records retain a
  value_changed flag, not the connection string; historical records untouched.
  Private full suite **108 passed**, focused route/test Ruff clean (FastAPI B008
  excluded); legacy schema typing style warnings were not mass-refactored.
- Fresh CI through `cbfcc57` passed (`38009033137`); prior identity/health and
  plain-text/privacy commits also have completed successful current-head runs.

## Iteration 19 — web data failures are not empty workspaces

- Browser reproduced HTTP 503 silently becoming No pools yet / Members 0;
  invite errors were discarded too. Private web now shows loading, accessible
  errors and Retry for members, invites, pools and proxies. Pool actions/data
  wait for successful inventory reads; retry recovers without reloading the page.
- Overview statistics wait for data; invitations and sharing are fetched only
  for admins/owners instead of hiding expected permission failures as empty data.
  Share reads also retain the selected request identity through pool changes.
- Real browser injected four independent 503 cases and verified visible errors,
  no misleading empty counts and successful Retry. Previous-team row/owner-role
  race still passes; proxy masking/TCP status/0ms/mobile checks still pass.
  TypeScript/Vite build passed. Injected 503 console messages are expected, not
  a claim of zero console errors during failure testing.
- These private web/backend changes remain local pending the next backed-up
  candidate deployment. No server sources are committed/pushed. Public desktop
  clean packaging/runtime verification is running for source commit `19990a8`.

## Iteration 20 — verified proxy/data console rollout and fresh package

- Reproduced web role mismatch: operators lacked Check, while managers saw
  Remove that backend forbids. Corrected UI boundaries to existing API rules;
  four-role browser matrix passed, lower roles issue no invite/share reads.
  Private full suite **110 passed**, operator/manager route regressions included.
- Private image `proxies-20261010T004300Z` deployed on 18083 after backup and
  final-image PostgreSQL QA with an actual isolated TCP listener. Public switch
  **80/80**, no probe failures; retained assets/SPA HEAD/cache verified on both
  domains. Models/startup/auth/dependencies unchanged, no new migrations.
  Replaced only an owned, unserved candidate; 18082 and original 18080 retained.
  Original API/PostgreSQL/Caddy/VPN start times unchanged. No real account tests.
- Active bundle `index-DNx3-1Qt.js`; private deployment handoff records immutable
  image hash, context, backup and in-place Caddy rollback to retained 18082.
  Backend directory remains uncommitted/unpushed.
- Clean Windows package `dist/release-20261010-043712/CamouFlow/CamouFlow.exe`
  built from source `19990a8`: **214 tests**, compileall and both fresh parsed
  runtime reports passed:true (imports/browser plus expected hard-timeout case).
  Optional PyInstaller GUI/undetected-playwright module warnings remain; core
  packaged checks succeeded. Documentation **35 pages, zero errors/warnings**.
- Passive production soak interim: **40 rounds / 72 checks / zero failures**;
  final observation still pending the mission deadline.

## Iteration 21 — valid JSON is not proof of a proxy exit

- Reproduced HTTP 200 with JSON [] being accepted as a healthy internet check,
  without an exit IP. Probe now requires a successful object/recognized success
  flag and valid IPv4/IPv6 exit address; redirects and empty/invalid shapes fail.
  No response-body contents are echoed in structural validation errors.
- Added nine response-shape/status regressions. Auth/CONNECT fixtures still pass;
  repeated actual TLS fixture remains three successful verified TLS 1.3 rounds.
  Full desktop **223 passed**; critical Ruff passed.
- Fresh anonymous production browser loads the deployed DNx3 bundle, labels and
  375px layout, zero console errors/warnings. This is not authenticated production
  proof; role/failure behavior remains verified on isolated data.
- Next reproduced routing defect: interleaved geo contexts leave process-wide
  socket.socket patched and a global SOCKS proxy set. Fix per-request routing
  before additional multi-profile launch verification.

## Iteration 22 — isolate profile proxy routing, including IPv6

- Reproduced interleaved contexts leaving socket.socket patched and a global
  SOCKS proxy set. Also reproduced NO_PROXY=* bypassing the explicitly configured
  HTTP proxy: one request went direct, zero reached the proxy fixture.
- Replaced global socket/default-proxy mutation with per-request native HTTP/
  HTTPS handlers and explicit PySocks connections. HTTP bypass/environment proxy
  settings cannot change profile routing; target TLS still verifies certificate
  and hostname, and proxy auth is removed before entering the target tunnel.
  No new dependency; no SOCKS local-DNS fallback. Context interface retained.
  [PySocks warns against global monkeypatching](https://github.com/Anorov/PySocks).
- Health probe and local SOCKS adapter reuse PySocks.create_connection instead
  of an IPv4-only socket, gaining IPv6 upstream/address-family handling and
  connection-failure cleanup. Existing protocol/auth contracts preserved.
- Fixed route fixture: one proxy request / zero direct requests; interleaved
  contexts leave socket/default-proxy unchanged. Five regressions added;
  full desktop **228 passed**, focused critical/import Ruff passed.
- Real isolated TLS matrix: HTTP IPv4 **6/6**, authenticated SOCKS5 IPv4 **9/9**,
  authenticated SOCKS5 IPv6 **9/9**. Each covers three health and three profile
  geo lookups; SOCKS also covers three local-adapter lookups. All TLS 1.3, with
  certificate/hostname verification and NO_PROXY=*; fixture credentials only.
  This proves routing/framing/auth, not a commercial proxy provider's egress.
- Current-source packaged rebuild required after this change; earlier 214-test
  package is not presented as including the new routing implementation.

## Iteration 23 — packaged routing and staged web resilience

- Rebuilt current source with **228 tests passing** into
  `dist/release-20261010-050028/CamouFlow/CamouFlow.exe`. Both fresh parsed engine
  smoke reports have `passed: true`; optional packaging warnings remain.
- Executed the packaged CLI queue on Camoufox and CloakBrowser through an
  authenticated local HTTP proxy: both histories succeeded and exported page
  content was verified. Four geo TLS requests, four page requests, two auth
  challenges, zero blocked/unexpected routes. Certificate and hostname verified;
  synthetic data only, no external forwarding or real accounts.
- Fresh GitHub CI for **6c09c40**, run **38011300894**, succeeded.
- Private server (not Git): reproduced timestamp ties dropping audit rows;
  composite timestamp/ID cursor retains all rows, preserves legacy before-only
  requests and existing RBAC. Backend **113 passed**. Browser fixture reads
  60 + 60 + 5 tied records; failed append retains rows, Retry recovers, stale
  filter responses cannot replace current results. PostgreSQL rollout pending.
- Private web (not deployed): reproduced temporary auth/me 503 deleting tokens
  and two tabs racing one-use refresh tokens (two refreshes, one request failed).
  Typed HTTP errors preserve sessions on transient failures with visible Retry;
  origin-scoped native Web Locks serialize rotation across tabs (one refresh,
  both protected requests succeed). No unsupported-browser fallback. Requires
  HTTPS/localhost and native Web Locks. See the
  [Web Locks specification](https://www.w3.org/TR/web-locks/).
- Seven real-browser module boundaries passed: malformed pair, foreign identity,
  logout during refresh, account switch, refresh 503, public auth 401 (no refresh),
  late same-user 401 (adopts already rotated credentials). These use controlled
  local responses; concurrent tabs separately use the isolated real auth API.
  Actual built UI auth/me 503 retains both tokens and Retry recovers.
- Production remains the earlier DNx3 proxy-console deployment. Passive soak
  interim **90 rounds / 162 checks / zero failures**; final deadline pending.

## Iteration 24 — avoid copying private scenario values into progress logs

- Reproduced six automatic value leaks with synthetic markers: profile/shared/
  both variable assignment, extracted content, popped credential-pool items,
  and HTTP URLs containing userinfo/query tokens. Explicit log action was the
  seventh case and intentionally remains unchanged.
- Five progress messages now retain variable/pool names or HTTP method/status,
  not values/URLs. No generic secret-pattern guessing, new dependency or changes
  to scenario variables, account updates, requests, persistence and exports.
- Seven regressions: baseline **6 failed / 1 passed**, fixed full desktop
  **235 passed**. Critical/import Ruff passed. Broad Ruff still reports 32 existing
  legacy typing/exception-style findings in the two touched modules; no unrelated
  modernization. Logs guide documents explicit-output/error boundaries and that
  historical logs are not rewritten. Fresh package rebuild pending.
- Private audit image passed actual isolated PostgreSQL **125 timestamp ties**,
  both action filters, legacy cursor, team scope, viewer/auth RBAC and retained
  assets. Browser verified viewer issues zero restricted reads and initial/recent
  activity failures recover via Retry instead of appearing empty.
- First audit cutover observed **79/80**, one external TLS EOF (not an HTTP 5xx);
  automatically rolled back to retained 18083. Both candidates healthy, next
  passive preflight **20/20**. Retrying only after that check; no zero-downtime
  claim. Production soak and cutover evidence are separate measurements.

## Iteration 25 — audit/session rollout and fresh packaged verification

- Private audit/session/docs candidate now serves production on 18082, image
  `audit-20261010T015300Z`, SHA256
  `336e846f77c7a80adfd378f78c98188a8e76a73e669f4629a3fa521ee89b8ed7`.
  Previous 18083 remains healthy for rollback. Original API/PostgreSQL/Caddy/VPN
  start times unchanged; no schema migrations, new dependencies or customer
  account mutations. Private source/docs synced; none committed/pushed.
- Two initial switches each saw one external connection-close and rolled back.
  Final cutover **79/80**, one TLS EOF near reload, then independent steady-state
  **80/80**. Exact failures retained, not silently retried. Root cause/path scope
  of transport closure remains unproven; no zero-downtime claim.
- Root-private validated DB dump/config/source backups retained. The first source
  archive missed README; complete source archive plus separate README is the
  usable snapshot. Rollback restores Caddyfile in place to retained 18083.
- Fresh anonymous production browser loads Brov4sEH, supports secure Web Locks,
  auth 375px has no overflow, both language guides show accurate proxy scope,
  zero page errors. Authenticated behavior is isolated proof, not production
  customer-account proof. Older hashed assets remain available.
- Latest package `dist/release-20261010-054247/CamouFlow/CamouFlow.exe` includes
  progress-log changes and **235 passing tests**. Both fresh parsed engine smoke
  reports `passed: true`; packaged authenticated proxy/queue/export proof again
  succeeds on both engines (four verified geo TLS / four pages / zero unexpected
  routes). Privacy semantics are regression-tested; pure recording CLI does not
  emit python.jsonl, so no fabricated packaged-log capture claim.
- Focused Ruff passed, Retype **35 pages / zero errors/warnings**. Fresh GitHub
  CI **38014212609**, head **fadc3c0**, succeeded. Passive production soak interim
  **102 rounds / 186 checks / zero failures**, still running until the deadline.

## Iteration 26 — local proxy dialogs must not act on shifted rows

- Reproduced opening local B at index 1, removing preceding A, then saving or
  confirming deletion: both actions modified/deleted C now occupying index 1.
  Also reproduced replacing a connection while retaining old successful health.
- Current dialogs capture a content snapshot (name/value/assignment), without
  adding persisted IDs or migration. Changed/shifted snapshots fail explicitly,
  not by guessing another row. Existing four/two-argument programmatic slots
  remain compatible, cloud UUID behavior unchanged. Local/cloud switches reject
  both legacy and snapshot markers. Local save/delete read-check-write uses the
  existing storage lock, preventing a health merge from interleaving persistence.
- Value edits clear old last_check/history/score; name-only edits retain them.
  Assignment/quarantine remain unchanged. No silent quarantine release.
- Six added cases: baseline subset **5 failed / 5 passed**, fixed full desktop
  **241 passed**. Browser-settings subset **79 passed**; focused critical/import
  Ruff passed after sorting touched-file imports, no broad typing refactor.
- Real Windows QML opened B's dialog, changed the synthetic inventory, then
  clicked Save: rejection displayed, C unchanged, dialog closed, zero warnings.
  No real profiles/endpoints or user data touched. Current package rebuild pending.

## Iteration 27 — reset selection before a workspace fetch can fail

- Reproduced workspace refresh clearing proxy rows but retaining old positional
  bulk selection until a successful inventory read. Switching cloud → local with
  a delayed/failed read could leave stale bulk targets available in the new mode.
- Clear selection synchronously with the existing workspace-cache reset, before
  background submission. One focused regression failed before and passes after;
  browser-settings **80 passed**, critical/import Ruff passed. Same-workspace
  ordinary refresh retains existing behavior.
- Private staged follow-up: reproduced cloud value edits inheriting old TCP
  health, probes marking an edited endpoint healthy, and deletion during a probe
  raising StaleDataError. Endpoint edits reset implicit health; conditional SQL
  persistence discards stale results. Explicit caller-supplied health remains
  supported. Private full suite **117 passed**; PostgreSQL rollout still pending.
- Private staged post-login recovery: actual successful login followed by auth/me
  503 erased newly issued tokens. Built UI now retains them, opens explicit session
  recovery and Retry succeeds. Normal superadmin navigation remains unchanged.
- Read-only production investigation: five HTTPS health requests bound to the
  physical Ethernet interface succeeded with verified TLS 1.3; active VPN/core
  untouched. This is a separate path, not proof of the earlier default-path EOF
  cause. Next cutover should measure both paths simultaneously.
- Synthetic performance baseline: 10,000 cached proxy entries, five unmatched
  searches **175.9–180.7ms**, median **179.3ms**. URL parsing still repeats on each
  filter despite no network calls; investigate bounded display-cache reuse.

## Iteration 28 — avoid repeated proxy parsing while typing

- Reuse sanitized display addresses within the current inventory; clear the
  cache on every applied refresh and workspace reset. Bound to entries currently
  rendered from that inventory, not a process-global credential cache. Status,
  quarantine, selection, pool statistics and search predicates still recompute.
- Same synthetic 10,000-entry benchmark: cold **191.3ms**, five warm searches
  **31.6–32.5ms**, median **31.8ms**, versus prior **179.3ms** median (~82% less
  warm UI-thread time). Cold rendering is not improved; this is a synthetic
  CPU/model test, not a production-user latency or rendering benchmark.
- Reproduced HTTP credential containing 'socks' being labeled SOCKS5, SOCKS4
  mislabeled SOCKS5 and bare/default SOCKS5 labeled HTTP. Type now comes from
  the validated, credential-free address scheme; malformed entries show INVALID.
  No second URL parse and no credential-dependent protocol guessing.
- Five focused baseline failures now pass; full desktop **246 passed**,
  critical/import Ruff passed. Regression checks parsing once per inventory and
  refresh/workspace invalidation, not hardware-dependent timing thresholds.
- Real Windows QML masked/status/search/reset/minimum-window checks pass without
  warnings. Final current-source package verification still pending.

## Iteration 29 — isolate the reload failure before blaming a route

- Latest private probe/session candidate passed **118 backend tests** and actual
  isolated PostgreSQL **five edit + five delete** races through a real TCP listener.
  Stale probes return discard and audit it; new endpoints remain unchecked,
  deletion no longer raises StaleDataError. Retained assets checked in final image.
- Its first production switch recorded one RemoteDisconnected on the default
  route and one on explicitly bound Ethernet; rolled back to 18082. Both serving
  candidates healthy. This disproves a VPN-only explanation, not all possible
  VPN contributions. Listening-port inspection confirms public TLS uses Caddy.
- Separate temporary Caddy with the exact installed image, verified private CA,
  loopback-only TLS/admin ports and synthetic static responses reproduced the
  same error: plain configuration **239/240** around three reloads, proxy-protocol
  wrapper configuration **240/240**. Earlier plain trials were **240/240**. No
  FastAPI, PostgreSQL, reverse proxy, VPN or real account was involved.
- Thus the wrapper, app and VPN are not necessary for this transport symptom.
  Precise internal shutdown/handshake race remains unproven; do not attribute it
  to a single component beyond the isolated reload reproduction. Caddy documents
  [graceful reloads](https://caddyserver.com/docs/getting-started); measured results
  take precedence over a blanket zero-downtime claim.
- Only the owned temporary Caddy/container anonymous volumes were removed; active
  Caddy/API/PostgreSQL/VPN untouched. Next candidate switch records bounded
  connection-close failures explicitly and requires clean dual-path steady-state
  checks; no automatic retry hides an individual request failure.
- Fresh CI: **38015537159/f4d0e5c**, **38015421458/e5ae29e** and
  **38014907892/35eb4ce** all succeeded. Current-source AI workflows passed on both
  actual engines with fixture LLM (privacy/extraction/replay/artifact/CLI checks);
  this does not validate paid-model quality. Changed source/docs UTF-8 scan:
  **58 files, no BOM, strict decoding passed**. Passive public soak interim
  **127 rounds / 231 checks / zero failures**, final deadline pending.

## Iteration 30 — real API/browser verification and remaining edge cases

- Probe/session candidate now serves production on 18083, immutable image
  `probe-20261010T020700Z` / SHA256
  `da18db27d69b7b731af29ec19d43e2789dc4e0e8b725a1a8c0f6d8754ca9e337`.
  Final switch default **80/80**, Ethernet **79/80** (one connection close),
  independent dual-path steady-state **160/160**. Exact-image isolated Caddy
  reproduction is documented above; no per-request retry or zero-downtime claim.
  Retained 18082 healthy; original API/PostgreSQL/Caddy/VPN starts unchanged.
- Private sources/compiled assets/README/deployment/security notes synced after
  that rollout; no server files committed/pushed. Verified DB/config/source
  backups remain root-private; rollback Caddyfile targets retained 18082.
- Fresh production anonymous browser loads DBonekiG; secure Web Locks, mobile
  auth and both-language proxy guide pass, zero page errors. No real login.
- Current private API in a disposable SQLite fixture: actual UI login/logout for
  viewer/operator/manager/admin/superadmin; expected Check/Add/Remove visibility,
  zero viewer audit requests, actual isolated TCP check and 60+3 tied filtered
  audit rows. **Zero mocked API responses**, zero page errors. This complements
  actual PostgreSQL race proofs rather than replacing them.
- Latest verified package `release-20261010-063407` includes **246 passing tests**,
  both fresh parsed engine runtime reports true and actual packaged authenticated
  proxy/queue/export success on both engines. Subsequent dialog fix is newer and
  requires another current-source package before declaring it packaged.
- Private staged OAuth privacy fix: reproduced tokens remaining in the callback
  URL on auth failure and in the Back history after success. Replace current
  history entry before verification; both browser cases now remove fragments,
  preserve session and normal admin navigation. Synthetic tokens, no Google call.
- Private staged schema fix: six nullable patch fields returned 500; JSON-null
  last_check committed and then made every team proxy list return 500. Real local
  HTTP proof **PATCH 500 / subsequent GET 500**, restored only that synthetic
  fixture. Typed nonnullable fields now reject null before persistence:
  **PATCH 422 / GET 200**. Omission and actual nullable assignments remain valid.
  Full private suite **125 passed**; live read-only JSON-null count is **zero**,
  so no production data repair/migration performed.
- Private staged error UX: short signup password showed '[object Object]'. Web
  helper renders validation field/message, not raw input. Real rejected signup
  now shows the password-length rule and never echoes the input; seven auth
  boundary cases still pass. These three staged changes are not yet deployed.

## Iteration 31 — capture local dialogs from displayed cache, not fresh position

- Reproduced a shift *before* dialog opening: displayed B at index 1, disk now C
  at index 1; opening fetched C, so the earlier after-open guard could accept the
  wrong target. getProxy now uses the displayed inventory and shared workspace
  identity guard for both modes. Missing/stale workspaces return no target.
- Save/delete still validate against current storage under lock; rejected actions
  refresh the view. No persisted identity migration or fallback row guessing.
- New focused regression failed before and passes after; full desktop **247
  passed**, critical/import Ruff passed. Real Windows QML now clicks both Save
  and Delete for shifts before/after opening: C unchanged, view refreshed, zero
  warnings. Bulk positional actions remain a separate follow-up audit.

## Iteration 32 — validate local bulk targets before any side effect

- Reproduced stale selected B/index 1 releasing, deleting, dequarantining or
  starting a check for neighboring C after inventory shifted. Eight cases:
  baseline four failed/four passed. Shared local target validation now rejects
  stale workspace/membership/snapshots before persistence or worker creation.
  Read-check-write remains under the existing storage lock.
- Applied local inventory changes also clear positional selection. Health-only
  refreshes keep it; same-target metadata changes do not force unnecessary resets.
  Membership-length check rejects even identical snapshot copies after deletion.
  No persisted IDs/migration introduced; indistinguishable same-field copies are
  a documented limitation, not a claim of true record identity.
- Local-only quarantine capability hides the unsupported cloud action; direct
  calls report explicit scope rather than pretending a workspace switch. No new
  cloud quarantine feature or server-policy mutation.
- Full desktop **261 passed**, critical/import Ruff passed; real Windows QML
  Save/Delete, masked/status/search/minimum-window checks still pass. Synthetic
  10,000-entry warm search remains **32.3ms median**, cold **186.6ms**; no network.
- Private OAuth/null/error-display follow-up remains staged, not deployed. Its
  full backend suite is **125 passed**. Real current local HTTP now rejects null
  with 422 and still lists proxies with 200; real OAuth failure/Back cases remove
  fragments, and real password validation displays its rule without input echo.
  Next deploy needs immutable-image PostgreSQL validation and saved cutover proof.

## Iteration 33 - preserve unreadable local storage

Reproduced settings/account mutation replacing malformed, wrongly shaped or unreadable JSON with empty data; BOM input also lost existing keys. New regression suite initially had 22 failures and 3 passes. Mutation reads now validate containers and fail before writing; missing new files remain creatable. Existing read-only empty-state behavior is unchanged. UTF-8 BOM input is accepted and writes remain UTF-8 without BOM. All nine account/settings/selector mutation paths covered; full desktop suite **286 passed**. This does not repair existing corrupted files or guarantee cross-process serialization. GUI write-error handling is reviewed separately before final packaging.

## Iteration 34 - visible storage errors and current server boundaries

Settings slots now report persistence failures without uncaught Qt exceptions,
false success, onboarding dismissal or navigation. User automatic-sync/logout
preferences also report failed local writes. AI provider configuration is one
atomic settings update rather than five independently persisted fields.
45 focused storage/UI tests and **306 full desktop tests passed**. Actual Windows
QML with a disposable corrupted settings file: native welcome-button click
showed the error, preserved bytes/onboarding and produced zero QML warnings.

Private server deployed on healthy 18082 from immutable final-034000 image:
OAuth fragments removed before verification/history; six non-nullable proxy null
updates rejected before persistence; readable validation messages omit inputs.
Private suite **125 passed**, final image's isolated PostgreSQL TCP/null/retained
asset checks passed. Actual anonymous production browser verified B0fSbFNz,
mobile authentication, secure Web Locks and RU/EN docs; no customer login/data
mutation. Cutover each path 79/80 (one recorded connection close), independent
steady-state 160/160. Exact-image isolated Caddy reproduction and rollback
remain documented privately; no zero-downtime claim. Root-private backup and
healthy previous 18083 retained; original API/PG/Caddy/VPN starts unchanged.
Server sources remain outside public Git.

## Iteration 35 - explicit import pools and actionable partial failures

Profile-list import used a separate quarantine parser: malformed timestamps
silently released quarantine and naive timestamps raised TypeError. Exhausted
local/cloud pools and cloud read errors silently created profiles without the
requested proxy. Reused the existing quarantine predicate; explicit pool
resolution now fails closed, while intentionally choosing no pool remains
supported. Incomplete cloud sessions cannot import locally. Local selection,
assignment and account save are serialized; a failed account write attempts
assignment rollback (not a crash-safe cross-file transaction). Logs identify
line numbers instead of credential-bearing input lines.

New additive completion signal retains only failed lines in the open dialog;
all-success imports close it. 18 focused regressions, baseline 11/14 failed,
and **324 full desktop tests passed**. Actual Windows QML native import clicks
proved quarantine skip, pool exhaustion blocking, failed-line draft retention,
explicit no-pool success and zero warnings. No real accounts or public backend
sources involved. Package 073450 passed both fresh engine/Python reports at
593b34c (306 tests); a new build is required for this import iteration.

## Iteration 36 - canonical cloud proxy fields

Legacy profile-field cloud saves built unescaped userinfo/unbracketed IPv6 and
dropped usernames with empty passwords. Reused existing `account_proxy` instead
of a new encoder. Six focused creation/reuse regressions failed before, passed
after; **330 full tests passed**. Actual isolated authenticated API verified
three canonical values and three existing-row reuse checks, decoded credentials
and IPv6/empty-password identity; owned synthetic rows cleaned. No production
customer updates. An earlier QA fixture incorrectly treated parse_proxy's tuple
as ProxyDetails; corrected to its documented config/details pair before proof.

## Iteration 37 - archive guarantees and stabilization evidence

Added 24 isolated archive regressions: all sessions/secrets combinations,
checksums, traversal/Windows/ADS/case-collision/symlink paths, existing destination
preservation, size/file limits, live-session change detection, account-write
rollback, restored-profile defaults and new scenario/reference names. No archive
runtime refactor was needed. Full desktop suite **354 passed**. Windows ZIP
reader normalizes backslashes; that fixture is rejected by the manifest/path
boundary before publication, not assumed to fail at one specific internal check.

Real Windows QML background archive slots verified non-blocking full export and
restore, collision rejection, two metadata-only exports and GUI-thread callbacks;
zero QML warnings, temporary synthetic workspace cleaned. Updated Profiles and
Settings Retype guides; **35 pages, zero errors/warnings**. These docs are pushed
on the feature branch, not falsely described as published GitHub Pages.

Stabilized package `dist/release-20261010-074400/CamouFlow/CamouFlow.exe`
contains runtime c62a55f. Clean build, compileall, 330 tests at build time, both
fresh parsed engine/Python reports passed. Actual packaged authenticated HTTP
proxy runs succeeded on both engines; exports verified, four target TLS geo
requests, four fixture pages, two auth challenges, zero unexpected forwards,
certificate/hostname verification enabled. No real accounts or paid LLM.

Current-source AI workflow verification passed on both engines with fixture HTTP
LLM; actual AI QML/replay verifier passed. Fresh CI c62a55f run 38021578604,
8e38cf5 run 38021399230 and 593b34c run 38021048159 completed successfully.
The full current CI QML recipe passed all 13 pages/settings modes and operation,
recorder/heartbeat/single-flight callbacks locally. Private suite rerun:
**125 passed**. Real local API browser rerun: all five roles, actual TCP check,
63 timestamp-tied filtered audit rows, null PATCH 422/subsequent list 200,
OAuth failure/Back token-fragment removal and readable no-input-echo validation
all passed; no mocked API in the five-role integration flow.

## Iteration 38 - avoid per-row disk reads in profile presentation

Measured 10,000 synthetic profiles: render performed 10,000 session reads and
blocked for 4465.9 ms (resolved-capability fixture). Presentation now snapshots
the current session and three capabilities once, while public actionState still
checks the live session. Shared private state calculation retains occupancy and
stale-session guards. Fixture result 57.4 ms / one session read; no network.

Actual Windows QML then exposed remaining empty-reservation path resolution:
1979.6 ms median for 10,000 profiles. A lock-protected empty-set short circuit
preserves path-alias checks when reservations exist. Actual Windows QML after
both changes: 84.1 ms median, search/tag counts correct, zero warnings; no browser
launch or cloud calls. These are local observations, not universal hardware
thresholds. 14 focused state/capability/alias regressions and **368 full tests
passed**. The previous 074400 package predates these two runtime changes;
rebuild and reverify before handoff.

## Iteration 39 - dedicated profile paths and rename rollback

Read-only storage audit found profile identifiers `.`/`..` reaching workspace
roots, sanitized-name aliases sharing browser data, and rename I/O failures
silently reported as success after metadata changed. Initial 25 regressions:
23 failed / 2 passed. No real workspace deletion was run; negative deletion
reproductions used spies and disposable synthetic files.

Added a shared checked-profile path boundary for browser creation, cookie reads,
directory removal/reset, new/renamed accounts and archive restore. Reused the
archive's Windows-name validator instead of duplicating it. Root/engine links,
unsafe/reserved names, active metadata aliases and existing rename destinations
are rejected before side effects. Renames move the dedicated directory before
saving metadata, attempt rollback on save failure, and no longer swallow I/O
errors. Existing ambiguous records remain untouched; no migration/data cleanup.
GUI preflight/constructor/cookie failures use existing asynchronous error and
cloud-lock cleanup paths rather than uncaught Qt callbacks.

35 focused path/alias/rename/link/error regressions and **403 full desktop tests
passed**. Actual two Windows
junctions: six unsafe operations rejected, a nested-junction reset did not follow
its target and the outside synthetic marker remained intact. Real Windows QML
legacy-root start failed before constructor, async cookie failure arrived, a
controlled constructor-race failure used GUI cleanup, no browser launched and
zero warnings. Updated guides explicitly avoid crash-transaction/sandbox claims.
Cloud browser storage is still name-based; cross-team ID-based namespacing needs
a separate compatibility/recovery design, not an automatic ambiguous migration.

## Iteration 40 - safe local cookie replacement and engine-correct preview

Initial cookie regressions: 13 failed / 3 passed. Blank drafts previously cleared
the jar, invalid rows were discarded after clearing, and CloakBrowser's nested
cookie database was not read. Cookie editing now explicitly supports local
profiles only instead of implying cloud/team-scoped storage. Validate the whole
draft before effects; block encrypted preview reuse. Reuse existing operation
ownership/reservations and reject pending browser starts. Snapshot the actual
jar before replacement and attempt rollback on failure, reporting rollback
failure explicitly. An explicit empty array requires GUI confirmation and
captures the original target/draft; cancel does not mutate.

Read only the selected engine's bounded storage. Corrupt/unsupported databases
report errors, not a successful empty preview. Convert Chromium's Windows epoch
and Firefox schema 16/17 millisecond expiry to Unix seconds; older schemas use
seconds, unknown schema versions are rejected. Mozilla's case-15 migration was
checked against the current upstream CookiePersistentStorage.cpp, not a numeric
guess. Actual Camoufox schema 17 and CloakBrowser closed previews matched their
native context expiry within two seconds. Real synthetic browser jars on both
engines passed snapshot/clear/restore under a controlled first-add failure and
successful replacement. Persistent QA cookies were used; session-only cookies
are correctly not promised to survive browser closure.

38 focused regressions passed. Actual Windows QML blank rejection, empty-array
cancel/accept, captured target and cloud-control hiding passed with zero
warnings. That UI check intercepted its worker; real jar execution was verified
separately on both native engines. No real customer cookies or logins were used.
The preview is not a full-fidelity browser-session backup; archives remain the
appropriate storage export. Cloud namespacing and crash-safe transactions remain
separate work, not hidden fallbacks.

Full current desktop suite: **441 passed**.

## Iteration 41 - validate AI history before replacing UI state

Eleven regressions initially failed: malformed task/status/result, secrets,
sources, events and usage counters either partly replaced the current state or
were accepted into properties that require different types. Validate all consumed
transcript fields and normalize event roles before any state assignment. Invalid
history retains the previous task/profile/session/results; valid history keeps
the original completion time and does not rerun a task. Eleven regressions now
pass, as does the actual Windows AI QML/replay/history verifier.

Current native diagnostic audit bypassed ScenarioExecutor entirely. Both engines
observed a deliberately aborted local request; Camoufox forwarded explicit
console calls while CloakBrowser did not (including raw CDP observation).
Neither forwarded the timer-thrown page error despite the timer executing.
These are capture limitations, not proof that a page has no errors. No stealth
settings were disabled or dependencies upgraded to hide the limitation.
Failure-artifact checks separately verified screenshots/HTML/error/events files
and valid trace archives on both engines. Added a user-facing Runs/diagnostics
guide with privacy, retention, viewer prerequisites and engine limitations.

Package 090801 contains cookie/runtime 640b579: clean build, **441 tests**, fresh
parsed engine/Python reports passed on both engines. Packaged authenticated HTTP
proxy queue/export proof passed twice, with four verified target TLS requests,
four pages, two authentication challenges and no unexpected forwards. AI workflow
fixture-provider checks passed both engines; the full current 13-page QML recipe
passed. This package predates iteration 41; rebuild before the final handoff.

Full current desktop suite: **452 passed**. Fresh CI 640b579 run 38026449646,
25d4c0a run 38023791088, d10aa28 run 38022824289 and b46bdf4 run 38022253112
all completed successfully. Iteration 41 needs its own fresh CI after push.

## Iteration 42 - complete profile/scenario null-update boundaries

Nine private HTTP regressions failed before the fix; three omission/nullable
checks passed. Owned actual local API reproduced profile settings and scenario
definition null: PATCH 500 followed by list 500. The two synthetic rows were
removed and lists returned 200; production was never used for this mutation.
Align five profile/four scenario update field types with their non-nullable
storage/public contracts, following the already-fixed proxy pattern. Fields
omitted from PATCH remain untouched; nullable profile pool/proxy references can
still be cleared. Admin/team/pool/run null behavior was inspected and retained,
not broadly changed without a poisoning path. Twelve focused checks passed.

Latest immutable private image passed disposable PostgreSQL: 15 total resource
null cases, omission/nullable references, healthy lists, five edit plus five
delete actual TCP races and retained assets. Test-only httpx stayed in its
disposable QA container. Read-only live JSON-null profile/scenario counts were
zero; no customer repair, deletion or production migration.

Backend-only cutover at **09:26 Samara** to healthy 18084, with validated dump,
prior Caddy/compose/source backup and retained healthy 18082 rollback. JS remains
index-B0fSbFNz.js. Default 80/80, explicitly bound Ethernet 79/80 (one recorded
RemoteDisconnected), independent steady-state 160/160; no hidden retry or
zero-downtime claim. Anonymous live OpenAPI confirms all nine new guards; actual
production browser passed 21 route/width checks, zero errors, no customer login.
Fresh local API browser passed all five roles, real TCP check and 63 tied audit
rows; fixed settings/definition actual HTTP checks return 422/list 200.

## Iteration 43 - repair and exercise real fresh-install migration chains

The stronger disposable-image check used Alembic rather than model create_all
and found PostgreSQL rejecting an integer default on a Boolean historical column.
After that fix, fresh SQLite exposed duplicate pool_shares creation: revision
0001 uses current metadata, while 0007 unconditionally recreated the table.
Use SQLAlchemy's portable [false()](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.false)
for upgrade/downgrade Boolean defaults; make 0007 respect an existing table,
matching neighboring migration patterns. No historical migration rewrite beyond
these compatibility boundaries, new revision or production migration was run.

Real SQLite and exact-image disposable PostgreSQL passed empty installation,
owned downgrade/reupgrade, Boolean default insertion, existing/absent pool-share
creation and synthetic team preservation. These owned fixtures do not establish
a production disaster-recovery drill or recovery of dropped commercial data.
Full private suite **138 passed**. Private sources remain outside Git.

Current desktop package **dist/release-20261010-091311/CamouFlow/CamouFlow.exe**
contains runtime 6a773c1: clean build, compileall, **452 tests**, fresh parsed
engine/Python reports passed. Actual packaged HTTP-authenticated proxy queue and
export passed on both engines with target TLS certificate/hostname validation.
Current-source MCP stdio handshake/read-only tools/startup allowlist/no execution
arguments and real approved queue runs passed on both engines. Actual isolated
n8n import/static-command/browser CLI/JSON export/history/parse-result passed.
Both use existing separate integration runtimes, no desktop dependency changes.
Fresh CI 6a773c1 run **38026742763** completed successfully. Current full 13-page
QML recipe passed; Retype **35 pages, zero errors/warnings**, built not published.

## Iteration 44 - strengthen native cookie and diagnostic integration proof

Actual Windows QML Save clicks now exercised the real asynchronous cookie worker,
not its intercepted UI seam. Both engines acquired/released operation ownership,
rejected an already-owned profile, kept GUI heartbeats processing during the
browser worker and saved a persistent synthetic cookie. Reopening each actual
browser verified the saved value. Zero QML warnings; owned workspace cleaned.
This complements the earlier confirmation/cancel test and controlled native
rollback boundary, without implying crash-safe cookie transactions.

Refined the native event audit to distinguish evaluated scripts from real HTML
scripts. Camoufox captured the HTML page's uncaught timer error; neither engine
forwarded the page.evaluate timer error. CloakBrowser forwarded failed requests
but not explicit console calls or the HTML page error; raw Runtime CDP also
remained empty. Corrected the guide rather than implying all Camoufox errors
are missing. [PinchTab's own CloakBrowser integration documentation](https://pinchtab.com/docs/cloakbrowser/#console-log-capture)
describes related Runtime-event suppression and a different capture path; it
does not establish our installed binary's precise upstream cause or detection
trade-offs. No fallback, page instrumentation, stealth changes or dependency
upgrade were added. Current wrapper 0.3.28 is kept for this verified build.

Fresh native Windows reruns passed dedicated path/junction, profile import,
actual archive-worker callbacks, stale proxy-dialog clicks and minimum-window
Runs filters/screenshots with zero warnings. Live production responsive checks
passed after the resource-guard cutover; isolated API roles/audit pagination,
OAuth failure/history fragment removal and readable validation passed again.
Seven canonical private host source/handoff files were byte-hash verified;
the immutable image stayed unchanged, all prior upstreams remained healthy,
and original API/PostgreSQL/Caddy/VPN start timestamps were preserved.

## Final packaging and native archive validation

Closed real Camoufox/CloakBrowser profiles were exported with sessions and
without metadata secrets, restored under new local names and actually reopened.
Persistent cookie values, HttpOnly/SameSite flags and origin localStorage all
survived; original metadata was unchanged. Archives contained 71 Firefox and
155 Chromium browser files. This is same-Windows-user/machine proof, not a claim
that browser-encrypted sessions transfer to another machine or account.

Prepared local **dist/CamouFlow-autonomous-20261010-091311-windows.zip**,
138,448,015 bytes, SHA256
`3e2d7995c9d99ea291a4c27525306a947180a91800df34cc2b8969866f8c62ad`.
All bundled scenario files are tracked source assets; no untracked scenarios,
workspace settings/profiles or private backend were packaged. ZIP CRC verified,
extracted executable hash matched the original, and fresh runtime/import/hard-
timeout checks passed for both engines from an independent extracted directory.
This is a local delivery artifact, not a published release or main merge.

Machine-readable receipt **outputs/autonomous-audit/final-verification.json**
checks code-source equivalence to packaged runtime 6a773c1, fresh parsed engine
reports, package/ZIP hashes, native cookie/archive proofs, current tests/docs/CI,
isolated integrations, live schemas and dual-path steady-state evidence.
Thirty-five changed Python files passed critical Ruff checks; compileall passed;
72 changed text files passed UTF-8/no-BOM/replacement-character verification.
Owned PowerShell-generated QA logs were normalized from their explicit UTF-16
BOM to ordinary UTF-8 without BOM; actively written soak files were not touched.

## Remaining risks and highest-value continuation

- Cloud browser storage still uses human names, not server/team/profile IDs.
  Next: propagate stable scoped identity through manual browser launch, queue,
  recorder, AI and Python workers; provide explicit backed-up recovery of old
  folders. Never silently assign ambiguous browser data to another team or fall
  back to a similarly named local profile. No migration was implemented here.
- Local identical proxy copies lack persisted UUIDs. Existing opaque snapshot
  guards reduce stale writes, but UUID identity needs a separate compatibility
  migration rather than claiming hashes distinguish identical rows.
- Cookie replacement, profile rename and multi-file import rollback are attempts,
  not crash-safe transactions. Directory guards are not a local-Python sandbox
  or complete filesystem race protection.
- Native browser-event forwarding remains partial; inspect traces/HTML/screenshots
  locally. Do not disable stealth or add a fallback/instrumentation implicitly.
  Paid-provider quality, real Google/customer authentication, different machines
  and a production backup restoration drill were not tested.
- HTTPS-to-proxy health/geo remains explicitly unsupported. The existing secondary
  HTTP geo provider remains; no universal TLS or endpoint-reachability guarantee.
- Progress logs no longer implicitly print values, but explicit logs/stdout,
  errors, historical logs, browser files and artifacts can still contain secrets.
  Profile archives are unencrypted, including session data when metadata secrets
  are excluded. Retention limits metadata, not automatic artifact deletion.
- Caddy reload cutovers recorded a bounded connection close on physical egress.
  Long passive health sampling and successful steady state do not erase it or
  establish zero downtime. Keep retained healthy upstreams and verified backups;
  do not prune them or modify unrelated VPN/Caddy global settings casually.
- Feature-branch docs are built but not published to GitHub Pages. Main stays
  unchanged; the new local ZIP is not an official public release.

## Closeout - 2026-10-10 10:00 Samara / 06:00 UTC

Worked through the requested deadline. The actual timed read-only production
soak exited successfully: **354 rounds / 638 checks / 0 failures**, complete.
Counts were recomputed from every JSONL record and matched the final summary;
live health/OpenAPI and source/package/ZIP/test/CI evidence were revalidated after
06:00 UTC. This sampling does not override the recorded cutover connection close.

Final verified runtime 6a773c1; desktop **452 tests**, private **138 tests**,
runtime CI **38026742763 success**, both native engines and fresh extracted ZIP
runtime checks passed. Current live backend remains immutable resource-guard
image c0222877 on healthy 18084, with healthy rollback upstreams retained.
Production dump inventory was revalidated; original service starts preserved.
Owned localhost QA API/Vite/preview listeners 15173-15177 were stopped, owned
browser sessions closed, and the production soak was allowed to finish naturally.
No customer data cleanup, production migration, VPN restart, main merge, public
release, private-backend commit or private-backend push was performed.

The closing documentation commit brings the feature branch to **45 public
commits since 37207b9**. Runtime code is unchanged by subsequent documentation
commits. Full pre-closeout commit manifest follows; the final HEAD is recorded
in the machine-readable verification receipt and can be verified on origin.

## Public commit manifest before closeout

```text
6b07975 Preserve canceled pending runs in local history
4a2dead Run desktop CI for test changes and smoke Tasks page
471de99 Add saved task search while preserving run input drafts
d49930f Keep queue and history consistent on storage write failures
76c0735 Document timestamped builds and verified release checks
4a4beb5 Record verified blue-green backend rollout and continuation priorities
e797832 Reject invalid engine arguments in workflow verification
20cea3b Make run results visible before scheduling controls
9df2835 Add workspace-scoped search and status filters to run results
5cf9aaa Bound artifact previews and keep run selection workspace-safe
aef395f Unify proxy quarantine policy and stop canceled assignments
6b5e411 Preserve proxy pool edits when asynchronous checks finish
c1e72c2 Serialize cloud token refresh and save session fields atomically
b7cb42c Record verified workspace-isolated console rollout
6de697b Render untrusted QML metadata as plain text without image requests
0254cd2 Hide proxy credentials in inventory and dashboard summaries
4c8e6ca fix(proxies): distinguish unchecked and TCP-only health
62b0db1 fix(proxies): bind cloud actions to displayed identities
cbfcc57 feat(proxies): add cached inventory search and status filters
19990a8 fix(proxies): preserve encoded auth IPv6 and CONNECT framing
c952eba docs: record verified web data failure handling
34ebcc9 docs: record backed-up proxy console rollout and package proof
b71ab9a fix(proxies): require successful geo response and valid exit IP
6c09c40 fix(proxies): isolate geo routing and support IPv6 upstreams
cb51281 docs: record packaged proxy proof and staged web resilience
fadc3c0 fix(scenarios): keep private values out of implicit progress logs
e762bb8 docs: record audit rollout and verified current desktop package
35eb4ce fix(proxies): guard local dialogs and invalidate changed endpoint health
e5ae29e fix(proxies): clear bulk targets before workspace refresh
f4d0e5c perf(proxies): reuse display parsing within the current inventory
c3f8ef9 docs: record isolated reload diagnosis and probe race verification
6928e42 fix(proxies): capture local dialogs from the displayed inventory
856fb1d fix(proxies): validate local bulk targets before mutation or probing
6b09173 fix: preserve invalid local storage during mutations
593b34c fix: report settings persistence failures and save AI config atomically
8e38cf5 fix: require explicit pool assignments and retain failed import drafts
c62a55f fix: canonicalize cloud proxy credentials and IPv6 fields
b46bdf4 test: cover profile archive integrity privacy and rollback
d10aa28 perf: snapshot profile presentation state and skip empty reservations
25d4c0a fix: guard dedicated profile storage and roll back failed renames
640b579 fix: protect local cookie replacement and normalize engine previews
6a773c1 fix: validate AI history before replacing workspace state
fbb8891 docs: record verified resource guards migrations and final integration build
55b4a19 docs: distinguish native browser diagnostics and verify cookie workers
```


## Resumed mission: 13:00 Samara (09:00 UTC), 2026-10-10

User resumed work at 11:07 Samara. Keep previous 10:00 closeout as historical
proof, not the new deadline. Same branch/private-server/security boundaries.
New baseline: clean 59a9073, 452 public tests passed; production upstream 18084
healthy, original PostgreSQL/Caddy/VPN start timestamps unchanged. A separate
read-only production soak runs until 09:00 UTC. Real proxy credentials are only
process environment inputs, never source, documentation or report values.

### Iteration 45: proxy connection ownership and SOCKS stream correctness

- Reproduced unclosed health-check sockets after response timeout and TLS failure.
  The probe now releases its owned socket in a finally block on every outcome.
- Reproduced SOCKS bridge accepting an authentication method the client did not
  offer; reject with 0xff according to RFC 1928 instead of claiming no-auth.
- Reproduced losing the response after a client write-half-close. Replaced
  nonblocking sendall with writable-select/partial-send handling and bounded
  64 KiB per-direction buffers; preserve half-close after draining pending data.
- Nine regression cases include real socketpairs, slow-reader 2 MiB transfers
  in both directions, partial writes and temporary BlockingIOError.
- These code defects are independently reproduced, not claimed as the cause
  of the physical-Ethernet proxy timeouts. Real SOCKS5 works via default/VPN
  routing; HTTP CONNECT does not work on the supplied SOCKS endpoints.
- Primary references: https://www.rfc-editor.org/rfc/rfc1928 and
  https://docs.python.org/3/library/socket.html#socket.socket.send .

### Iteration 46: close the native CloakBrowser SOCKS request-route leak

- Real supplied endpoints: SOCKS5 authentication, verified TLS 1.3 IP lookup and
  256 KiB Cloudflare transfer each passed three identical default-route rounds.
  Exit addresses match each endpoint; geo API reports PL. The physical-Ethernet
  path failed repeated CONNECT/negotiation attempts; TCP alone was reachable.
  HTTP CONNECT also failed on these SOCKS endpoints: do not import them as HTTP.
- Native baseline: both engines navigated HTTPS with the correct proxy IP, but
  CloakBrowser context.request used another exit address on all three endpoints.
  This affects visual http_request and the documented Python context API.
- Root cause verified in pinned CloakBrowser 0.3.28: SOCKS configuration becomes
  a Chromium command-line flag, absent from Playwright's API request context.
  Keep the SDK, fingerprint controls and dependency pins; no runtime monkeypatch.
- Reuse the existing loopback bridge ownership for an HTTP/CONNECT-to-SOCKS
  adapter. Pass the adapter as the SDK's native HTTP proxy so pages and requests
  share the selected upstream, cookies, response-cookie updates and TLS policy.
  Do not pass upstream credentials in Chromium command-line arguments.
- HTTP forwarding rewrites absolute to origin form, preserves request bodies,
  removes proxy credentials and hop-by-hop proxy headers, reconstructs Host,
  closes ordinary origin connections and supports CONNECT/WebSocket upgrades.
  Bound header sizes; malformed targets/ports/headers fail before upstream I/O.
  Upstream failure returns 502, never a direct connection. Stop closes only
  this bridge's owned client/tunnel sockets; active system VPN stays unchanged.
- Corrected source: all three endpoints x both native engines x persistent and
  ephemeral contexts passed HTTPS navigation, repeated matching browser/API IP
  and a real 256 KiB transfer. Twelve native sessions; not synthetic proxy proof.
- Regression tests exercise local real TCP POST/CONNECT, 1 MiB body preservation,
  malformed/oversized input, owned tunnel teardown and launcher credential scope.
- Primary Playwright contract: https://playwright.dev/python/docs/network#http-proxy
  and https://playwright.dev/python/docs/api/class-browsercontext#browser-context-request .
