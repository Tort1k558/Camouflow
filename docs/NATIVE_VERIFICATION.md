# Glint verification

## Evidence levels

1. Python/source tests prove manager behavior under their fixtures.
2. Standalone C++ tests prove the tested policy primitives.
3. Chromium native units prove the linked native test target, not browser startup.
4. Production object compilation proves those translation units, not chrome.exe.
5. A linked own-fork binary needs actual runtime tests and measured code hashes.
6. Packaged/relocated payloads need independent integrity, lifecycle and rollback checks.

Never treat one level as proof of a broader level. Prepared/unapplied patches,
upstream SDK controls and old reports are not proof of a new own-engine release.

## Public gates

| Tool | Scope |
| --- | --- |
| `scripts/verify_release.py --build --runtime` | Desktop package and packaged legacy-engine checks |
| `scripts/verify_native_cpp.py` | Standalone native policy primitives |
| `scripts/verify_native_privacy_units.py` | 33 exact required key/loading/owner cases |
| `scripts/verify_native_suite.py` | Runtime, hardware, WebRTC, automation, fonts, identity, CDP and combined gates |
| `scripts/verify_native_storage_paths.py` | Windows path-depth/storage probes |
| `scripts/verify_native_canvas.py` | Canvas verification tooling, not an implemented protection claim |

Run commands as documented in the [build guide](../native/BUILDING.md). Use fresh
report paths outside source/application repositories. Keep raw outputs and
measured executable/core-DLL hashes; a count without exact names and successful
completion is insufficient. Failed or skipped cases are not a passing gate.

## Required release checks

- Profile separation and persistence for cookies, localStorage, IndexedDB,
  Cache Storage and service workers across reopen/restart.
- Cross-process owner exclusion, controller death, browser crash and bounded
  cancellation/teardown with no surviving owned browser processes.
- Authenticated proxies and permissions with explicit no-direct-route controls.
- Document/iframe/worker consistency and combined policies, including unsupported
  input rejection with the expected native diagnostic.
- Navigation, forms, extraction, screenshots, Recorder and replay.
- Packaged/relocated resources, full payload integrity, real credits and rollback.
- UI compatibility results invalidated when configuration changes.

Crash persistence covers a gracefully committed checkpoint, not every pending
write. Shared/service worker partitioning, actual Chrome incognito bootstrap and
future renderer key delivery require their own lifecycle evidence.

## Current boundary

The 001-010 Windows development baseline has completed runtime gates and
packaged-payload checks. Key/codec/owner native units are separate evidence.
The newer production context integration is not yet a newly linked verified
browser. Prepared drafts add ten service-readiness and twenty real-context cases;
neither draft has been compiled/run or registered for release admission.

Current development is Windows-only. Linux/macOS own-fork runtime verification,
Canvas/GPU/audio protection and security rebasing remain required. External
anti-bot scores may be observations, never guaranteed release capabilities.
