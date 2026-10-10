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
| P2 | Run results/search/filter usability | Implemented | Collapsible scheduling, search/status filters, retained-history matching and minimum-window proof |
| P2 | Queue/storage failure and concurrency audit | Implemented initial safeguards | Reproduced disk-write failure leaving running job with no worker; rollback, pause and visible errors added |
| P2 | Useful server functionality | Team run history deployed | Correct terminal statuses/token lifecycle plus read-only team search/filter/pagination; isolated auth/RBAC/browser proof |
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
