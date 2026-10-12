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
| `drafts/` | Status notes for candidates promoted to the registered chain |
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

The linked 001-026 Windows browser passed all eight runtime gates (160 checks).
The latest 001-027 browser adds a verified shared-worker rejection notification;
all 40 owned startup/restart/shared-client/rejection checks passed. Its ordinary
runtime regression suite also passed all eight gates / 160 checks. Readiness patch 0016
passed 43 native key/service cases. Context-test patch 0017
passed all twenty native cases. Patches 0018-0020 register document/worker policy
endpoints and the worker consumer; all 34 native cases passed, followed by a
combined 54-case BrowserContext/IPC run. Worker startup/handoff patches 0021-0026
are linked behind a developer-only switch; four Blink seed ownership unit cases
passed on retry after test-only patch 0028 corrected a fixture lifetime abort.
The browser core, receipt and GN arguments were verified unchanged.
Patch 0029 registers the document partition validator and its nine exact cases;
the public `--target document-partition` native-unit gate passed. It does not
activate document delivery or Canvas protection; the verified browser is still
001-027.
The unprotected Canvas baseline passed on 001-027 before
and after restart. Canvas protection remains a candidate; branding
still needs application and verification. No signed own-engine release or guaranteed
anti-bot/CAPTCHA acceptance is advertised.

Development diaries and machine-specific evidence stay outside public source.
Durable contracts live in architecture docs; released changes belong in the
[changelog](../CHANGELOG.md).
