# Windows process resource observer

**Read-only draft, not integrated into the manager/watchdog.** No browser limit,
automatic termination, launch policy or production capability changes.

`WindowsProcessReader.read(pid, expected_created_100ns=...)` measures one live
process through an owned query handle: creation identity, kernel/user CPU time,
current/peak working set and private commit. Missing/inaccessible/exited processes
raise errors, never fabricated zero samples. Query handles close on every path;
a cleanup failure does not replace the primary measurement error.

`cpu_interval(previous, current)` rejects PID reuse, counter rollback and
non-increasing sample clocks. `mean_cpu_cores` is CPU-seconds / elapsed seconds,
**not host-normalized percent**. Short intervals are affected by OS counter/clock
granularity; values are not clamped to make them look plausible.

## Verified scope

- **24 controls**, including real owned processes, allocation/CPU changes, invalid
  samples, exited processes, 100 reads without handle growth and cleanup errors.
- One Glint 156 owned-browser observation: seven processes checked against the
  OS parent chain and creation identities, sampled without changing browser policy.
- Runtime core and all 201 frozen queue inputs remained unchanged; owned browser
  resources closed and control processes exited naturally.
- The initial retained control failure sampled the virtualenv launcher instead
  of the workload child. Correcting that harness did not change the reader.

Evidence: [`observations.json`](observations.json); private raw records and test
profiles: `D:\Glint156Candidate\windows-resource-reader-20261029-v3`.

**Summed working sets are not unique physical RAM:** shared pages may be counted
more than once. Private commit is not resident RAM. The observation is neither a
performance benchmark nor complete lifetime accounting for process churn.

The reader does not discover or authorize process ownership. Before manager
integration, bind the profile's root and descendants, handle churn explicitly,
and validate sampling overhead and limit semantics. Do not replace the existing
root-only metric with a working-set sum under the same automatic-kill threshold.
Apply integration only after the current source-bound queues are terminal.

API contracts: [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
and [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).
