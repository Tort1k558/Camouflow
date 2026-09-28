---
title: Python scripting
---

# Python steps

Add **Scripting > Python script** in the scenario editor, select the block and
choose **Edit Python script**. Python and visual blocks share the same browser
session. A Python block uses API version 1 and defines one asynchronous entrypoint:

```python
async def main(ctx):
    await ctx.page.goto(ctx.inputs["url"])
    ctx.log.info("Page opened")
    return {"title": await ctx.page.title(), "url": ctx.page.url}
```

Set **Inputs** to a JSON object, for example `{"url": "{{report_url}}"}`.
Variables are substituted in input values, never in Python source. Missing input
variables are errors. **Result variable** receives the return value after successful
execution: strings remain strings; other JSON values are serialized to JSON.
Use the existing variable parsing block to extract structured results.

## Context API

| Member | Purpose |
| --- | --- |
| `ctx.page` | Current asynchronous Playwright page |
| `ctx.context` | This profile's browser context |
| `ctx.use_page(page)` | Select an open page of this context for subsequent steps |
| `ctx.inputs` | Resolved input mapping |
| `ctx.variables` | Snapshot of scenario variables; modifying it does not save variables |
| `ctx.log` | Profile-scoped Python logger |
| `ctx.artifacts_dir` | `pathlib.Path` for this run's artifacts |
| `ctx.check_cancelled()` | Raise cancellation when stop has been requested |
| `await ctx.sleep(seconds)` | Asynchronous cancellable wait |

For authenticated HTTP calls use Playwright's `ctx.context.request`. The script
working directory is the run's artifacts directory. `print()` and logging are
captured, bounded, and visible in run details and the debugger. Do not print
passwords, tokens or sensitive page contents: outputs are not automatically redacted.

## Runtime and stop behavior

Scenarios containing Python, including nested scenarios, execute in a dedicated
process. The application retains ownership of queue state and cloud lock renewal.
Windows Job Objects terminate the worker and its child processes on forced stop
or application exit. This is process supervision, **not a security sandbox**.

The default block timeout is 60 seconds; configurable range is 100 ms to one hour.
After cancellation the worker has up to three seconds to stop cooperatively.
A blocked worker is terminated together with its browser. A hard timeout fails the
entire run; it cannot continue through the block's error link because the browser
session has ended. Ordinary Python exceptions use existing error links.

There is no automatic retry. Submitted forms, network requests and files already
written are not rolled back. Do not resume a failed task without checking its
effects. The application releases profile reservations only after confirmed worker
cleanup; a cleanup failure leaves the profile marked **Cleanup required**.

The result limit is 1 MiB, source limit 256 KiB, and output is capped. The queue
stores an execution snapshot; editing a scenario cannot mutate an active job.
Shared-variable and profile-tag operations are routed through the parent process.

## Trust and sharing

Imported and local Python scenarios require explicit local approval before being
queued. The review includes Python in nested scenarios. Changes to the reviewed
scenario bundle require approval again. Approval is stored on this computer and
is not installed with marketplace templates or shared with teammates.

Python runs with the user's OS permissions, including files, processes and network.
Only approve code you trust. The API server stores definitions; it never executes
uploaded Python. Older clients without Python support cannot execute these blocks.

## Editor and debugging

The editor includes syntax highlighting, line numbers, indentation, undo/redo and
syntax checking. **Check syntax** does not run code and does not verify websites,
imports or side effects. **Save script** saves the scenario asynchronously.

Configure the run under **Scenarios > Runs**, enable the existing debugger and
select a profile. Debugging is at block boundaries: one Python block executes as
one step. The debugger shows source, inputs, output and the return value; exceptions
include source line numbers. Python line breakpoints are not supported.
**Run to selected** executes intervening blocks and pauses before a later selected
block if the execution path reaches it. **Next step** then executes that block.
It does not rewind already executed actions.

## More examples

Write CSV into this run's artifacts:

```python
async def main(ctx):
    import csv
    path = ctx.artifacts_dir / "page.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["title", "url"])
        writer.writerow([await ctx.page.title(), ctx.page.url])
    return str(path)
```

Read a JSON endpoint with the profile's browser session:

```python
async def main(ctx):
    response = await ctx.context.request.get(ctx.inputs["endpoint"])
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status}")
    return await response.json()
```

## Distribution

No system Python installation is needed for the packaged Windows application.
The supported initial module set includes `asyncio`, `csv`, `datetime`, `json`,
`math`, `pathlib`, and `re`, plus the provided Playwright objects. Arbitrary pip
installation and custom interpreters are not supported. An unavailable module
raises an import error; it is not downloaded automatically.

For an opt-in packaged runtime diagnostic (fixed test code, disposable profiles):

```text
CamouFlow.exe --check-python-runtime camoufox C:\Temp\python-runtime.json
CamouFlow.exe --check-python-runtime cloakbrowser C:\Temp\python-runtime-cloak.json
```

The selected browser engine must already be installed. Diagnostics do not use
existing profiles or authenticate to the cloud. Reports name the temporary data
directory retained for inspection; remove it after reviewing results.
