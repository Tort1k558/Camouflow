# Security policy

## Reporting a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/Tort1k558/Camouflow/security/advisories/new).
Private reporting is enabled for this repository. **Do not open a public issue
or pull request containing an exploit or sensitive data.**

Include:

- affected version/commit, OS and browser engine;
- a minimal reproduction using disposable profiles and synthetic data;
- expected boundary, actual impact and relevant sanitized output;
- whether exploitation requires local access or an authenticated account.

Never attach API keys, proxy passwords, session cookies, profile archives,
customer data or production credentials. Do not test against other users or
production infrastructure without specific authorization. A public upstream
browser vulnerability should also be reported through that upstream's process.

## Support scope

Security fixes target the latest stable CamouFlow release and current `main`.
Older releases are not guaranteed backports. Update to the latest stable version
before reporting unless the latest release itself prevents reproduction.

Glint is an experimental development engine, not a security-hardened production
release. Its pinned Chromium baseline requires security review/rebasing before
production admission. A patched fingerprint surface is not a security boundary
or a guarantee against tracking. Camoufox/CloakBrowser updates and upstream
vulnerabilities must be considered independently of desktop app updates.

The optional hosted backend is privately maintained and is not part of the
public source tree. Reports affecting the CamouFlow-operated service can use
the same private reporting channel; do not disclose its credentials or sources.

## Handling reports

Maintainers will investigate privately and coordinate fixes and disclosure with
the reporter. This project has no guaranteed response SLA or paid bounty.
Please allow investigation and an available fix before public disclosure.
