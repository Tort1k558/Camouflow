# Logs

The **Logs** tab shows the application activity log:

- UI messages (import/run/errors)
- scenario execution progress by profile

Logs are also written to `logs/` (including `logs/proxy.log` for proxy diagnostics).

Implicit progress messages for variable assignment, extraction and shared-pool
consumption include names, not stored values. HTTP progress includes method and
status, not the URL (which can contain credentials or tokens).

An explicit `log` step and Python stdout still print what your script requests.
Errors and other diagnostic sources may contain sensitive data. Review logs
before sharing; this is not a blanket redaction guarantee. Existing logs are
not rewritten, and scenario values/exports are unchanged.

## Run diagnostics

The scenario **Runs** panel separates scheduling from retained results. Search
by scenario/profile and filter by status; filtering never starts a run. Selecting
a result shows metadata, failure details and Python output. Large text previews
show the last 32 KiB; **Open artifacts** opens the complete local directory.
Finished-history retention is bounded to 500 metadata records; artifact files
are not automatically deleted with the queue.

**Screenshot** opens a captured page image. **Trace viewer** launches the local
Playwright viewer for `trace.zip`; it requires the viewer's Chromium installation.
Unavailable captures produce an explicit message. A failed browser action can
save `error.json`, `page.html`, `page.png`, `browser-events.json` and a trace,
but a browser startup failure cannot capture a page that never opened.

Browser-event capture is engine-dependent. Native synthetic checks observed
Camoufox console messages and request failures on both engines, but CloakBrowser
did not forward explicit `console.log/warn/error` calls, and neither engine
forwarded a timer error scheduled through `page.evaluate`. A separate HTML-script
test did capture Camoufox's uncaught page error, but not CloakBrowser's. This
distinguishes page-script errors from evaluated-script errors. An empty events list is not proof
that the page had no errors. HTML, screenshots and traces may contain signed-in
pages or sensitive data: review locally and do not upload them to untrusted
services.
