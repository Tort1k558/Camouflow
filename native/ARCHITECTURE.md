# Glint architecture

## Manager integration

`app/core/native/` owns configuration, identity, diagnostics, browser lifecycle
and local binary distribution. The existing browser interface dispatches to this
runtime while preserving Camoufox/CloakBrowser. Engine IDs and profile schemas
remain compatible; the display/product name is Glint.

The runtime launches an explicit installed executable or a selected managed
release. It never substitutes another engine or adopts its profile directory.
Profiles use persistent Chromium contexts with process-owner exclusion and
bounded teardown. Recorder, scenarios and AI use the common browser contract.

## Configuration and privacy

Configuration validates viewport, DPR, locale, timezone, permissions and privacy
requests before startup. Unsupported requests fail rather than silently falling
back. Diagnostics observe actual document/worker browser values; they do not
replace APIs or invent hardware/GPU values.

Persistent identity uses an owned profile-root file containing a versioned
private key. Export excludes the key; restored/cloned profiles obtain a distinct
identity. Cryptographic domain strings and filenames are compatibility contracts,
not branding text, and must not be renamed without migration analysis.

Chromium patches provide hardware ceilings, real installed-font selection,
WebRTC routing, automation/headless policy and Windows storage-path handling.
Newer patches derive per-surface keys from a trusted browser StorageKey and own
the key service per BrowserContext. Off-the-record contexts have independent
ephemeral identities; they must never redirect to the persistent original.

Key loading is asynchronous on a blocking worker; derivation fails until ready.
Readiness callbacks are registered in patch 0016 and passed 43 native cases;
the linked 001–015 browser lacks them. Real-context tests are registered in
patch 0017 with native compilation/execution pending.
Future renderer/worker delivery must be lifetime-bound and use browser-owned
partition state. Canvas/WebGL/WebGPU/audio protection remains incomplete.

## Source reproducibility

`scripts/native_build.py` pins upstream revisions, records sync/hooks dependency
snapshots and checks applied changes by replaying registered patches into a
temporary Git index. Patch 0007 belongs to the separate V8 checkout. Unknown
changes and changed build inputs prevent generation of a successful receipt.

Do not edit an active checkout, GN arguments or registered patch content while
compilation is running. An object build proves only those translation units;
production linking and actual browser execution are separate gates.

## Distribution

`distribution.py` manages checksum-verified local bundles and release selection.
`scripts/package_native_windows.py` checks official staged files against compiled
output, retains licenses/credits and requires matching runtime evidence.
`scripts/native_release.py` provides install, activate, inspect and rollback.

Complete payload integrity includes executable code, DLLs and resources.
Activation checks compatibility/health; compilation alone is not release admission.
There is no signed online update catalog. Development bundles are unsigned.

## Known boundaries

- Graceful close/reopen commits are tested; abrupt crashes may lose pending writes.
- Thread/owner checks do not prove operating-system memory sanitization.
- Unpartitioned shared/service workers need explicit partition policy before
  cross-site privacy protection can be activated.
- Own-fork Linux/macOS runtime, GPU/audio/Canvas protection and production
  security rebasing are not complete.
