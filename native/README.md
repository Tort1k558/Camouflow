# Glint

CamouFlow's independent Chromium-based development engine. It is not a
Camoufox/CloakBrowser rename or a JavaScript fingerprint wrapper.

- [Build on Windows](BUILDING.md)
- [Architecture](ARCHITECTURE.md)
- [Status and limitations](../docs/NATIVE_ENGINE.md)
- [Verification requirements](../docs/NATIVE_VERIFICATION.md)
- [External test sites and per-build results](../docs/GLINT_TEST_MATRIX.md)
- [Development plan and continuation prompt (Russian)](../docs/GLINT_ROADMAP.ru.md)

## Source layout

| Directory/file | Purpose |
| --- | --- |
| `patches/` | Registered, ordered Chromium/V8 patch chain |
| `core/` | Shared C++ policy primitives |
| `windows/` | Windows font-policy source |
| `tests/` | Native policy fixtures and tests |
| `branding/` | Prepared Glint product/logo patch, not applied |
| `drafts/` | Unapplied context/readiness candidates, not passing runtime proof |
| `build/`, `toolchain/` | Build/toolchain support source |
| `build-lock.json` | Pinned upstream revisions and build limits |
| `args.gn` | Development Chromium build configuration |

Chromium, tool downloads, cache and binaries belong in an external workspace
on D:, not this Git repository. The historical `D:\CamouFlowNative` and
`out/CamouFlowNative` names remain technical paths, not product branding.
Private backend source is excluded from public Git.

## Release boundary

Current own-fork work is Windows-only. Linux/macOS support is deferred, not
released. The manager's Mobile Web mode is desktop Chromium viewport/touch
emulation, not Android/iOS. Only verified capabilities may be enabled.

The 001-010 Windows development baseline has runtime evidence; later privacy
key/context changes and branding/readiness candidates need further native
compilation and runtime verification. No signed own-engine release or guaranteed
anti-bot/CAPTCHA acceptance is advertised.

Development diaries and machine-specific evidence stay outside public source.
Durable contracts live in architecture docs; released changes belong in the
[changelog](../CHANGELOG.md).
