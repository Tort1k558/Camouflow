# Canvas colour and copy contracts

**Measured incompatibility, not a fix or admitted privacy policy.**

The [R8 observation](observations.json) compares ordinary and experimental
profile-identity Canvas policies on an owned loopback fixture. Both execute the
same opaque 8×8 CSS-colour pattern in HTML canvas, OffscreenCanvas, same-origin
iframe, classic worker and module worker. No external site code or allowlist is
used by this probe; private profile keys never enter its result.

| Contract | Baseline, all five contexts | Experimental, all five contexts |
| --- | --- | --- |
| Readback equals the known multicolour CSS fill | Exact | **101 changed channels / 256** |
| Copy each returned pixel through CSS fill and read again | Exact | Exact |
| Later disjoint writes leave earlier pixel values stable | Exact | Exact |
| Uniform opaque fill | Exact | Exact |

The changed count belongs to this one profile/pattern, not every profile.
Source/core/driver and all runtime-asset guards passed; owned resources and the
fixture thread closed. A single changed channel fails the colour contract;
repeat/copy consistency does not turn colour substitution into native fidelity.

The separate [external observation](../upstream-156-audio-r8/public-sites-observations.json)
reported 14% RGBA noise in CreepJS's experimental profile. Its percentage is not
the same metric as this probe's channel count. CreepJS's
[public implementation](https://github.com/abrahamjuliot/creepjs/blob/master/src/canvas/index.ts)
checks known pixel colours and copied image data; passing selected automation
checks does not establish natural Canvas rendering.

Next: separate versioned rendering identity from readback masking, preserving
the existing policy/keys and historical failure. Investigate real native
rendering cohorts and verify their effect before claiming a replacement. No
domain-specific exception, smaller tolerance or invisible-browser claim is allowed.

`validate.py` rejects malformed counts, contradictory verdicts and missing or
reordered contexts. Worker failures remain incomplete, never zero differences.
The probe covers these five contexts and opaque RGBA8 CSS colours only; it is
not a full Canvas/float16/P3/export/security regression suite.
