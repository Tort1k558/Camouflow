# Windows profile version guard

**Integrated into `app/core/native/`.** Managed releases already block binary
downgrade; the per-profile guard also covers explicitly selected executables.
The full canonical Python regression passed **3862 tests, one skipped**.
Canonical installed lifecycle (18 checks), worker startup (60) and both combined
surface modes (12 phases / 24 nested Canvas cases each) subsequently passed.
The [scoped record](../upstream-156/canonical-app66-observations.json) also retains
the failed Audio-v1 fidelity gate; this is not general migration admission.

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

The patch and original isolated observations remain as provenance; do not apply
the patch again. Source integration does not grant policy or production
admission. Retained test profiles/keys stay private on D:.
