# Glint clean-workspace build audit

Date: **2026-10-12**. Windows x64, application Python 3.12. Audit of the public
[build guide](../native/BUILDING.md), performed separately from the active build.
This is an audit report, not a successful fresh-machine Chromium build.

## Observed stages

| Stage | Result | Evidence / boundary |
| --- | --- | --- |
| New external workspace | Verified | Dedicated `D:\GlintCleanBuildAudit20261012`; no copied Chromium/cache/output |
| `preflight --jobs 4` | Passed | 304.4 GiB free, 12 logical CPUs, expected pinned revisions |
| depot_tools checkout during `bootstrap` | Passed | HEAD `a03dfbf7f2d1cefa2795d81d59ca4f16c8616a8f`; checkout has no tracked modifications |
| Workspace Git configuration | Verified | `depot-tools.allowGlobalGitConfig=false` in workspace config; no global changes requested |
| First CIPD client download | Stalled | Upstream `gclient.bat help` invokes `.cipd_impl.ps1`; no completed client download observed |
| Independent CIPD HTTPS request | Failed | Pinned `windows-amd64` client URL, TLS verification enabled; `ReadTimeout` after 30.83 seconds |
| Bootstrap completion | Not verified | Audit process tree stopped after transport diagnosis; partial workspace retained |
| Chromium sync / hooks / patch application | Not run | Do not present source review or an existing checkout as fresh-download evidence |
| Full compile / runtime / packaging | Not run in this workspace | Existing active incremental build remains separate |

Private transport evidence is retained at
`D:\GlintCleanBuildAudit20261012\cipd-transport-audit.json`; bootstrap logs remain
in the external workspace area. No credentials or actual browser profiles were
used. No OS security changes, global Git changes or active-source edits were made.

## Findings and guide corrections

- The first bootstrap needs network access to the official CIPD endpoint and its
  download redirects. Git clone succeeding does not prove tool-download access.
- Pinned upstream PowerShell download code uses `Invoke-WebRequest` without an
  explicit timeout; a stalled request can leave bootstrap looking idle. Diagnose
  transport separately, not by starting another bootstrap in the same workspace.
- Upstream Git configuration recommendations are warnings. Do not apply suggested
  global mutations: the project deliberately uses workspace-local configuration.
- Four jobs are a maximum, not a RAM guarantee. Recent development builds have
  produced explicit LLVM out-of-memory failures at four jobs. Reduce jobs for
  memory-constrained builds; changing jobs does not require sync/resetting source.
- Manual patch application is ordered and non-transactional; patch 0007 targets
  V8. A partially applied chain must be inspected, not blindly rerun or deleted.
- A clean Windows installation, successful sync/hooks and a complete new-workspace
  compile remain unverified. This audit satisfies the scoped walkthrough/report
  task, not an end-to-end reproducibility claim.

Resume bootstrap in this separate workspace only after resolving the endpoint
transport issue. Do not copy cached binaries to label a clean download successful.
