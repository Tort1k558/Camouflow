# Protected GPU consistency contract, version 2

**Measured R10 fixture coverage, not full GPU or browser admission.**

[Observations](observations.json) bind the exact validator and independent R10
runtime. The matched baseline, two protected profiles and both restarts passed:
**40 document/iframe/worker contexts, 240 texture observations**.

| Check | Required result |
| --- | --- |
| Unselected baseline | Original texture, buffer and compute results |
| Protected texture reads | Only RGB bit 0 may differ; alpha and padding exact |
| Repeated copy and shader sampling | Exact agreement |
| Three mips / two layers | Complete ordered byte arrays and dimensions |
| Profile identity | Equal same-profile contexts, distinct profiles, stable restarts |
| Existing WebGL gate | PNG, crop/PBO/pack, renderbuffer, errors and metadata still checked |
| Validator robustness | 38 malformed-data injections rejected |

`validate.py` reuses the existing capability and WebGL validators **after**
validating every original WebGPU byte. Only validated texture observations are
normalized for those older capability checks; input observations are untouched.
The raw unselected baseline also passes its original WebGL normalization first.
The initial matched-harness failure is retained in R10's runtime record.

The legacy validator is unchanged. This contract does not establish the exact
native mask oracle, arbitrary textures/formats/workloads, resource-denial
behaviour, device cohorts, external detector results or CAPTCHA acceptance.
R10's source-copy, placeholder-frame and worker-rendering failures remain open.
