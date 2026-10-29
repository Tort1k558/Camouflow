# Windows profile version guard

**Unapplied Runtime patch.** Managed releases already block binary downgrade;
this adds a per-profile check for an explicitly selected executable as well.

The Windows Runtime checks Chromium's bounded `Last Version` marker against
the selected EXE's fixed PE FileVersion while holding the profile owner lock,
**before loading its private identity or starting Playwright**. Same-version
and forward-version selection remain allowed; older/unknown versions and
browser data with missing version metadata reject without fallback or migration.
Fresh profiles do not need a previous-version marker.

Evidence in [`windows-profile-version-guard.json`](windows-profile-version-guard.json):

- 22 owned marker/real-PE and mocked-launch controls;
- one real owned-profile **148 → 156** upgrade preserved cookies, localStorage,
  IndexedDB, Cache Storage, the service-worker registration and private identity;
- selecting 148 afterwards rejected before identity/driver calls, with all
  owned profile files unchanged. The old browser never opened the upgraded data.
- the isolated patched Runtime also passed the extended **18-check lifecycle**
  CLI, including manager/scenario integration, Recorder, backup/restore,
  cancelled startup/teardown and owner recovery. The exact guard is injected
  into the CLI's owned child processes too; canonical source stays unchanged.

This is **not** general migration/rollback compatibility or executable
authentication. Managed payload checksums remain required; tampered version
markers cannot authenticate a binary. Linux/macOS protection is not implemented.

Do not apply while the current source-bound queues are live. After they become
terminal, verify normalized source hashes, normalize only the target Runtime as
UTF-8 without BOM/LF, run `git -c core.autocrlf=false apply --check`, apply, and
rebind/repeat canonical Runtime/manager verification. No production admission
follows from this draft. Retained test profiles/keys stay private on D:.
