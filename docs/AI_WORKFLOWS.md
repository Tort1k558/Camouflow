# AI browser workflows and integrations

Create an AI browser task, inspect its outputs, then save and replay a parameterized workflow without further model requests. This guide covers setup, controls, data handling, integrations and verification.

[Русская версия](AI_WORKFLOWS.ru.md)

## First useful result

1. Settings → AI: enable the assistant, set a Chat Completions-compatible base URL and model. Test the currently entered settings, then save. Native provider APIs with different protocols are not supported.
2. Scenarios → AI → **Try isolated demo**. This starts a loopback-only synthetic catalog and creates a separate local profile; it does not send model requests yet.
3. Start the suggested task explicitly. Inspect the extracted table, source URL and request/token counts; export JSON or CSV.
4. In workflow inputs, enter `{"catalog_url":"<the demo URL>"}`. Apply inputs, then **Check read-only replay**. This uses the existing scenario engine, not the model. It checks non-empty outputs and table column names, not business correctness or exact values.
5. Save the draft. Set `catalog_url` in the target profile's variables. Run through Scenarios → Runs. Replace the demo URL with your own page and review selectors before reusing it. The demo URL is temporary and stops working when CamouFlow closes.

Three reviewed starters are included: HTML catalog → JSON; one page → text report; fill one configurable form field without submitting. Sites with auto-save can still react to filling a field.

## Control and limitations

- Starting URL, exact starting-host restriction, explicit file access, per-action confirmations, pause/resume, stop and questions to the operator. Redirecting to another host stops further page observation/actions; this is not a network firewall and cannot block requests already made by a page.
- Pause takes effect between actions. Stop preserves completed steps; an interrupted action may already have affected the page. Do not blindly retry submissions.
- A model-reported `success` is separate from a successful deterministic replay. Interactive drafts require explicit review and desktop Runs; automatic replay checks refuse clicks, typing and submissions.
- Tables require unique non-empty headers, consistent columns and at least one row: maximum 200 rows, 30 columns, 1 MiB. Merged cells are unsupported. Text extraction is bounded to 20,000 characters in AI actions. Viewport snapshots follow scrolling; `find` can locate text further down the page.
- Parameterization replaces exact recorded URL/field values, not arbitrary substrings. Set each required input explicitly; missing inputs stop the scenario. Shared workflow export refuses literal navigation/form values; inspect selectors and metadata before sharing.
- AI history retains the latest 100 local metadata entries and restores saved transcripts only in their original workspace. Transcript/artifact files are not automatically deleted. Deterministic exports are separated by profile under `outputs/ai-results/`.

## Data handling

Page text, labels, URLs, instructions, extracted outputs and operator answers are sent to the configured provider. Editable contents are excluded from DOM snapshots/extraction; detected typed passwords become required profile variables and are redacted from events/transcripts. This does **not** identify every possible secret: pages can render tokens in ordinary text or URLs. Do not use sensitive profiles for demos or enter credentials in operator answers.

A local model endpoint keeps model requests local; the browser can still contact sites. Provider keys remain in existing local settings storage. Artifacts and profile variables may contain sensitive data. CSV output guards formula-leading cells. No claim of full anonymization or sandboxing is made.

## Local CLI

Use the source checkout's Python, not the windowed EXE. Close the desktop first; a shared workspace lock prevents simultaneous access. Existing unfinished jobs must be reviewed before CLI execution. CLI is local-only and accepts read-only extraction workflows; Python, HTTP-request steps, nested scenarios and interactive actions are refused.

```powershell
.venv\Scripts\python.exe main.py --cli list
.venv\Scripts\python.exe main.py --cli history
.venv\Scripts\python.exe main.py --cli run --scenario "Catalog to JSON" --profile "Catalog profile" --confirm --timeout 120
```

JSON is written to UTF-8 stdout; diagnostics go to stderr. A nonzero exit means failure/cancellation. Set `CAMOUFLOW_DATA_DIR` to select an existing local workspace explicitly. Run results use the same queue/history/artifacts as the desktop. The restriction is to browser action types, not a guarantee that GET navigation is side-effect-free.

## Optional MCP

The adapter uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) in a separate environment; the desktop has no new dependency.

```powershell
.venv\Scripts\python.exe -m venv .local\mcp-env
.local\mcp-env\Scripts\python.exe -m pip install -r integrations\requirements.txt
.local\mcp-env\Scripts\python.exe integrations\mcp_server.py --python "C:\path\camouflow\.venv\Scripts\python.exe" --data-dir "C:\path\workspace"
```

Configure your MCP client's stdio command/arguments from that invocation. By default only `list_workflows` and `run_history` are exposed. To expose `run_approved_workflow`, add `--allow-scenario "Catalog to JSON" --allow-profile "Catalog profile"`. The pair and workflow hash are frozen at startup; changing the workflow requires restarting the adapter and approving it again. Execution takes no model-controlled arguments and has a 120-second CLI budget. Canceling the MCP request does not cancel an already-started local run; inspect history before retrying. No HTTP server or arbitrary browser/code execution is exposed.

## n8n example

Import `integrations/n8n-local-catalog.json`, review the static command, replace its installation paths/profile name and supply the profile variables. It is an **inactive example**, not a hosted connector. The example was verified in an isolated Windows n8n 2.41.5 runtime, including the CLI run and parsed result. Never interpolate webhook/user/model text into the command.

Use only a trusted self-hosted Windows n8n instance on the same host/user as CamouFlow. [Execute Command](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/) is unavailable on n8n Cloud and disabled by default from n8n 2.0; enable it only after reviewing your instance's access controls. A Linux container cannot directly run the host's Windows Python. The workflow parses CLI JSON; n8n import/execution requires testing in your own deployment.

## Verification

Run these commands from the repository root. Verification scripts live in `scripts/`; temporary reports are not committed.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_ai_workflows.py camoufox
.venv\Scripts\python.exe scripts\verify_ai_workflows.py cloakbrowser
.venv\Scripts\python.exe scripts\verify_ai_ui.py
.venv\Scripts\python.exe scripts\verify_release.py --runtime
```

Workflow smoke uses actual browsers and a local fixture Chat Completions endpoint: extraction, editable privacy, scrolling, parameterized replay with changed input, JSON artifact and CLI queue execution. UI smoke includes profile selection, settings changes, demo, export, real replay, history and saving. It does not validate the reasoning quality of paid/cloud/local models or compatibility with every provider/site. Release smoke checks the packaged browser/Python runtime.

To also test MCP stdio and allowlisted execution against that isolated fixture, set `CAMOUFLOW_MCP_PYTHON` to the absolute path of `.local/mcp-env/Scripts/python.exe` before running either workflow smoke. The adapter's test dependency remains separate from the desktop environment.

### Opt-in real provider checks

The release demo was checked three times on each engine with the configured `deepseek-flash` model, plus a full UI start/export/replay/save flow. Only synthetic catalog data was sent; keys remain in memory and are not copied into the test workspace. Each session is bounded to eight actions and 180 seconds. These checks use your configured provider and may incur API charges:

```powershell
.venv\Scripts\python.exe scripts\verify_ai_provider.py --settings-file settings/settings.json --engine camoufox --repeats 3 --report .local/provider-camoufox.json
.venv\Scripts\python.exe scripts\verify_ai_provider.py --settings-file settings/settings.json --engine cloakbrowser --repeats 3 --report .local/provider-cloakbrowser.json
.venv\Scripts\python.exe scripts\verify_ai_provider_ui.py --settings-file settings/settings.json --report .local/provider-ui.json
```

For an isolated n8n check, install n8n separately, then run `integrations/verify_n8n.py --n8n <path-to-bin/n8n> --report .local/n8n-smoke.json` using the project's Python. It imports an inactive workflow into a temporary n8n database and executes only the synthetic catalog job. It does not change a running n8n deployment.
