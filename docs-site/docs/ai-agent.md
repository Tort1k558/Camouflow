---
title: AI assistant
---

# AI browser tasks

The built-in AI assistant drives a profile's browser for you: describe a task in
plain language, watch every step live, and save the agent's actions as a normal
replayable scenario. It works with **both engines** — Camoufox and CloakBrowser —
because it uses the same browser control layer as scenarios and recording.

## Setup

1. Open **Settings → AI Assistant**.
2. Set a Chat Completions-compatible base URL, model and API key. Native provider protocols are not supported. Local Ollama can use `http://localhost:11434/v1`; browser traffic is still online even when model requests are local.
3. Press **Test connection** to test the currently entered settings, then save.

The v0.4.0 demo was verified with the configured DeepSeek model on both engines. This is not a guarantee of compatibility with every model or website.

The API key is stored locally in your settings file, the same way server tokens
are. While a task runs, the structure of visited pages (element texts; never
input values) is sent to the provider — use a local Ollama endpoint if that
matters to you.

## Running a task

**Scenarios → AI task**: pick a profile, describe the task, set the step limit
(5–100, default 25) and press **Start AI task**.

- The profile browser opens visibly and the agent works one action at a time:
  navigate, click, fill fields, pick options, scroll, wait.
- The live log shows each thought, action and result; **Stop** cancels anytime.
- When finished, the agent's answer appears in **Result**; a full transcript is
  saved under `outputs/ai-runs/<timestamp>/transcript.json`.
- Cloud profiles are locked for the session, exactly like recording.

## Saving as a scenario

Press **Save & edit** to turn the session into a scenario. The agent's actions
become ordinary visual steps (`goto`, `type`, `click`, `select_option`, …) with
the same unique selectors the recorder produces — review them in the editor like
any recording. From then on the workflow replays deterministically and costs
no additional model requests to run. Browser compute and network costs still apply.

Password typing is never written into steps: it becomes a
`recorded_secret_N` profile variable you fill in before replay.

## Isolated demo and structured outputs

Choose **Try isolated demo** in Scenarios -> AI. It creates a separate local profile and a loopback-only synthetic catalog. Start explicitly: the configured provider may charge for requests.

The assistant can extract HTML tables and text, show sources, preview the first 30 rows and export JSON or CSV. Tables require unique non-empty headers and consistent columns: at most 200 data rows, 30 columns and 1 MiB, with no merged cells.

## Parameterize and verify

Inputs map variable names to exact recorded navigation/form values, for example `{"catalog_url":"<demo URL>"}`. Apply inputs, check read-only replay, then save. Set required inputs in the destination profile variables before using Runs. The demo URL expires when the app closes.

Read-only replay uses the existing scenario engine without a model request. It checks non-empty outputs and table column names, not business correctness. Interactive drafts require explicit desktop review; automatic replay refuses clicks, typing and submissions. A model's success message is separate from verified replay.

Reviewed local starters cover a catalog table, one-page text report and filling one field without submitting. Websites with auto-save can still react to filling a field.

## Control and data handling

- Starting URL, exact host restriction and explicit file access. Host restriction is not a firewall: page requests or redirects may already have happened before the next check.
- Browser changes require confirmation by default. The agent can ask the operator for clarification. Pause applies between actions; stop retains completed steps. An interrupted action may already have changed the page.
- Page text, labels, URLs, task instructions, extracted data and operator answers go to the selected provider. Editable contents are excluded from snapshots/extraction; typed passwords become profile variables and are redacted from logs. Tokens rendered as ordinary text or URLs may still be exposed. Do not enter credentials in operator answers.
- Local AI history restores transcripts only in their original workspace; the latest 100 metadata entries are retained. Artifact files are not automatically deleted.
- Shared workflow export requires parameterized navigation/field values; inspect selectors and metadata before sharing.

## Local integrations

The source-only JSON CLI reuses the desktop queue/history. Close the desktop first; a workspace lock prevents simultaneous access. CLI runs only local read-only extraction workflows. Optional stdio MCP exposes list/history by default; execution requires a startup-approved scenario/profile and unchanged workflow hash. Canceling an MCP request does not cancel an already-started local run.

[CLI, MCP setup and inactive n8n example](https://github.com/Tort1k558/Camouflow/blob/main/docs/AI_WORKFLOWS.md#local-cli)

[Russian walkthrough](https://github.com/Tort1k558/Camouflow/blob/main/docs/AI_WORKFLOWS.ru.md)
