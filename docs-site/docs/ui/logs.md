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
