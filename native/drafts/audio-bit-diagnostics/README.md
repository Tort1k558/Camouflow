# Audio sample-difference diagnostics

**Unselected diagnostic tooling, not an Audio policy change or a browser result.**

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
