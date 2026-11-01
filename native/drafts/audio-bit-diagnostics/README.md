# Audio sample-difference diagnostics

**Unselected diagnostic tooling, not an Audio policy change or a browser result.**

## R8 measurement, November 1

[Separate browser record](r8-observations.json): two profiles completed baseline,
Legacy, Math and Math restart, with closed resources and unchanged inputs/core.
Baseline/Math comparisons stayed exact; six Legacy comparison groups changed
samples by up to **one ULP** and still failed the original equality gates.
Both profiles selected reference class 1, so coverage of both classes failed.
There was no retry to obtain a green cohort.

The private runner incorrectly expected a root completion phase and exactly
three modes. Actual multi-profile reports have per-profile completion phases and
`math-restart`. Its failure and original report remain intact; normalization of
the completed measurements does **not** make compatibility or selector coverage
pass. These browser observations are separate from the earlier tool-only checks.

The [separate selected cohort](r8-selected-cohort-observations.json) used the
existing public selector patch before measurement: reference classes **0 and 1**
both completed baseline/Math/restart with exact restart and unchanged linear
graphs. Legacy still failed. The short comparisons had no Math/baseline changes;
the earlier separate long-buffer control changed 12 compressor/slow-attack rows
for class 1 and none for class 0. Neither reference selection nor differing
samples establish actual hardware/device cohorts or direct internal backend
observation. The original random-cohort failure remains preserved.

`difference.js` compares equal-length `Float32Array` views, respecting byte
offsets. It reports changed bit patterns, finite/nonfinite pair counts, signed
zero differences, maximum finite absolute difference and maximum finite ULP
distance. Signed zeros differ in bits but have zero numeric/ULP distance.
NaNs and infinities are counted separately, not assigned a numeric distance.

The helper does not change samples, replace equality assertions or introduce a
passing tolerance. A one-ULP mismatch still fails an original exact-match gate.

## Check the tools without a browser

Use an existing Node executable; this command downloads nothing. Reports stay
outside the checkout on D: and the output directory must not already exist.

```powershell
.venv\Scripts\python.exe -B native/drafts/audio-bit-diagnostics/check.py `
  --node D:\path\to\node.exe `
  --work-dir D:\GlintManagerQA\audio-bit-tools-check
```

Checks cover positive/negative values, normal/subnormal numbers, signed zero,
NaN payloads, infinities, array shape errors, subarray offsets and empty input.
Python checks validate summary counts and preserve failed original verdicts.

## Summarize instrumented measurements

```powershell
.venv\Scripts\python.exe -B native/drafts/audio-bit-diagnostics/summarize.py `
  D:\GlintManagerQA\audio-measurement\report.json `
  --output D:\GlintManagerQA\audio-measurement\differences.json
```

Input follows the Audio compatibility collector's `modes/probes/observed/rows`
layout, optionally nested under `profiles`. Instrumented rows or channel rows
carry a `difference` object from the JS helper. The summary binds input bytes by
SHA-256 and retains original report/probe verdicts separately from metrics.
Rows without a sample reference are explicitly counted; absent metrics are an
error, never assumed to mean zero differences. Original raw reports remain the
authority for individual checks, errors, cleanup and coverage.

The current production fixtures and their pass criteria are **not modified**.
Browser instrumentation, repeated profiles, restarts, privacy and release
admission require separate measurements. These tools alone prove none of them.
