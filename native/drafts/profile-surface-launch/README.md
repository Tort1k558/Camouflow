# Profile surface launch integration

**Prepared manager schema; browser patch is not compiled or admitted.**

The coherent `next.patch` extends the exact 122-patch R4 prefix with explicit
`--glint-profile-surface-policy=1`. It reuses BrowserContext-owned keys and the
existing document/iframe/popup/worker IPC authorization; no root key is forwarded.
Browser validation rejects unknown versions, diagnostic flag mixtures and missing
key-service, derivation or effective partitioning/AudioMath/WebGL/metadata/WebGPU
features. Existing launches without the version keep their previous behavior.

| Evidence | Result |
| --- | --- |
| Full prefix plus adapter patch | 123 forward/reverse; 270 upstream files restored |
| Actual generated C++ target parsing | Nine implementation units and four native test groups passed syntax checks |
| Standalone contract | 47 C++ checks; 58 Python checks |
| Prepared manager and admission regression | 683 tests passed |

Parsing is not linking or executing the four new native test groups. The patch
must be included in a new measured browser before any `surface-policy-v1` package
is reviewed. The package allowlist is unchanged, and the Qt selector is not
exposed in QML. Unsupported policy requests fail before creating profile storage.

Manager policies distinguish `profile-identity` from `partitioned-privacy` and
select the version/mode atomically. The exact measured Windows Playwright driver
override removes only `ThirdPartyStoragePartitioning` from its disabled-feature
argument; other exclusions and sandboxing remain. Unknown driver bytes fail.
Driver-byte review is separate from browser-package admission.

The explicit policy requires AudioMath; it does not silently migrate legacy Audio.
Large Canvas/WebGPU resource failures and legacy Audio remain unresolved.
See [hash-bound observations](observations.json).
