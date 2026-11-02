# Glint R14: connected producer-stage source packet

**Registered for explicit source builds, but unselected and uncompiled.**
The canonical checkout and build receipt remain R13; no installed runtime changes.

| Preparation | Verified scope |
| --- | --- |
| Complete recipe | 144 unchanged R13 patches plus 8 follow-up packets |
| Isolated replay / reversal | **152 / 152**; 471 final sources matched, 332 originals restored |
| Native plan | **163 prepared bodies**: original 85 preserved, 78 added; no execution implied |
| Cookie Mojo bindings | Windows import validation and generation pass; not C++ type checking |
| Runtime / production | **Not admitted** |

## One connected batch

1. BrowserContext producer cohort and topology/lifecycle checks.
2. Existing localStorage backend checkpoint ownership.
3. RestrictedCookieManager accepted-write drain.
4. Versioned CookieJar/document endpoint.
5. Document-producer revision and connection availability without implicit bind.
6. Renderer document aggregate with final posted snapshot validation.
7. Browser dispatch requiring cookie endpoint version 2, sharing bounded wire ownership.
8. Test-only SQL failure injection and Oilpan/controller teardown corrections.

The SQL correction uses a seeded unique index, not unsupported ALTER CHECK or
disabled triggers. It keeps the expected constraint failure, sticky failure and
later-write readback assertions. The GC fixture releases namespaces while their
controller is alive; dangling-pointer checks remain enabled.

This is **not a working whole-profile checkpoint**: global mutation coordination,
worker/HTTP producers, backend/session-cookie persistence, manager completion,
full C++/GN/native/runtime checks and release admission remain open.

The checkpoint runner accepts `--candidate upstream-156-producer-r14` and requires
all 163 bodies, their discovered parameter instances and all six binaries. The
legacy R12 default and R12/R13 85-body contracts remain unchanged. Source transition
still requires the full host gate and an exact rollback backup; do not apply this
recipe blindly over an already patched checkout.

See [preparation.json](preparation.json), [native-case-plan.json](native-case-plan.json)
and [manifest.json](manifest.json). Preparation flags describe the earlier isolated
replay, not later registration or native execution.
