# Owned runtime evidence retention

**Integrated into the canonical verifier.** Full Python regression:
**3862 passed, one skipped**. The canonical installed lifecycle's 18 checks,
60 worker cases and both combined surface modes subsequently passed; see the
[scoped record](../upstream-156/canonical-app66-observations.json). The original
shutdown timeout remains unexplained.

The first expanded 156 run hit a browser-close timeout. `TemporaryDirectory`
then tried to remove a still-locked SQLite file and replaced the useful failure
with `NotADirectoryError`. This patch follows the existing GPU verifier's
explicit owned-directory/cleanup pattern:

- retain the owned profile on failure;
- preserve the primary exception, including when log cleanup also fails;
- delete only successful runs, after a canonical owned-path check;
- report cleanup failures separately instead of turning them into a pass.

Five Windows held-file controls passed on an isolated copy. The patched copy
also passed all 18 baseline browser checks on 156.0.8078.36. The execution copy's
repository root was set to the same value as the canonical script; no timeout,
fallback or forced-process termination was added. **The browser timeout itself
is not fixed by this patch.** Scope and hashes are in
[`owned-runtime-evidence-retention.json`](owned-runtime-evidence-retention.json).

The archived patch and isolated-copy evidence remain as provenance; do not
apply the patch again or treat that earlier result as current admission.
No timeout was increased and no forced process termination was introduced.

Retained profiles can contain private keys and browser data. Keep them local;
never add them to Git or public reports. Full local evidence stays under
`D:\Glint156Candidate\runtime-evidence-retention-20261029-v1`.
