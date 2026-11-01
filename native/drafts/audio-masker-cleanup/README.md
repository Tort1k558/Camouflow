# Audio masker sensitive-buffer cleanup

**Unselected three-file R7 patch. Not a browser build or a legacy Audio fix.**

The existing masker retained its copied seed/derived cache after destruction and
left temporary HMAC digests uncleared. This packet uses the same `OPENSSL_cleanse`
primitive as the profile-key owner, preserves copy/move behavior, and wipes the
digest on success and failure. It changes no sample algorithm or key domain.

## Reproduce

Requires the existing pinned R7 checkout, local MSVC/SDK, Clang/ASan and compiled
BoringSSL objects. Downloads nothing; compiles only isolated helper executables.
Reports and source copies remain in a fresh external D: directory.

```powershell
.venv\Scripts\python.exe -B native/drafts/audio-masker-cleanup/check.py `
  --workspace D:\Glint156Candidate `
  --work-dir D:\GlintManagerQA\audio-masker-check-new
```

The checker applies/reverses the patch only in disposable copies, compares 12,327
before/after outputs with an independent Python HMAC reference, and checks owned
storage erasure and copy/move lifetime. Normal and ASan runs use real BoringSSL;
its existing assembly library and libc++ abort handler are linked, not stubbed.
ASan covers the helper/driver, not rebuilt/instrumented crypto dependencies.

A separate instrumented-crypto fixture injects null HMAC results and short
digests, checks both failure cleanups and rejects poisoned cache reuse. That
fixture is not cryptographic correctness evidence. Proposed GTest syntax is
checked; no Chromium GN GTest target or browser is executed by this tool.

The context-owned seed/transport lifetimes are **not changed**. Clearing those
snapshots prematurely could turn a pending protected completion into raw output;
their full teardown protocol needs a separate fail-closed change and tests.
Register/build the complete next candidate and repeat runtime gates before
claiming integrated cleanup. Legacy fidelity/analyser/worklet mismatch, device
cohort plausibility, privacy and production admission remain open.
