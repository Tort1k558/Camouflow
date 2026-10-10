# Public CamouFlow Hub

## Development status — 2026-10-11

The private web frontend now implements `/hub` and shareable `/hub/{listing-id}`
pages over the existing scenario marketplace. This increment has been verified
against an owned local database, **not deployed to production**.

- Public search, category filters, popularity/newest sorting and bounded pagination.
- Listing versions, tags, download counts, timestamps and action-type summaries.
- English/Russian pages using the existing green palette; desktop and mobile layouts.
- Empty, missing/unpublished and failed-request states with explicit retry.
- Definition JSON downloads require acknowledging untrusted community content.
  Downloads never execute a scenario or install it silently.

Only explicitly published marketplace rows appear. Private workspace scenarios
are not automatically uploaded or listed. The new catalog endpoints expose neither
team/user/source identifiers nor scenario definitions; the existing marketplace
API contract is unchanged. Definitions are available through the existing explicit
download operation. Server implementation and tests remain outside the public repo.

## Installing and publishing

Open **Scenario market** in the desktop app, search for the listing's title and
choose **Install**. Review all actions and use an isolated profile before running.
Installation saves a copy; it does not start a browser task. The website's JSON
download is an inspectable definition, not a newly supported desktop import format.

Team managers publish from the existing desktop marketplace. Remove credentials,
cookies, personal data and other secrets from the definition and description
before publishing. Team managers and server administrators can unpublish a listing;
existing desktop copies are not recalled.

Publication is **not** a security review or proof of browser compatibility. The
current Hub explicitly states this and identifies executable Python actions.

## Verification scope

The private backend suite passed **221 tests**, including catalog isolation,
metadata privacy, unpublishing, literal search wildcards, pagination and request
validation. The frontend production build passed TypeScript and Vite checks.

A real browser exercised catalog/detail pages at 1440, 1024, 768 and 375 pixels,
both languages, search/category filtering, second-page navigation, consent-gated
download with persisted accounting, empty/not-found states and recovery from a
controlled HTTP failure. No application JavaScript errors or horizontal overflow
were observed. Downloaded JSON was inspected; these were owned fixtures, not
customer content or production tests.

## Remaining Hub deliverables

This foundation does not finish the agreed Hub scope. Still required:

- Evidence-backed reviewed scenarios, tied to the exact definition/version hash.
- Safe screenshots and explicit compatibility evidence, not inferred badges.
- Reviewed one-click desktop import, without running arbitrary community code.
- Indexable catalog/detail metadata and discoverability through Google/GitHub.
- Safe private-server deployment, production browser checks and desktop import proof.

The overall autonomous development mission remains active.
