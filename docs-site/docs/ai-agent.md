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
2. Choose any OpenAI-compatible provider and save:
   - **GLM**: base URL `https://api.z.ai/api/paas/v4`, model `glm-4.7`, your API key.
   - **OpenAI**: `https://api.openai.com/v1`, model `gpt-4.1-mini`.
   - **OpenRouter / Groq / DeepSeek**: their OpenAI-compatible URL and model id.
   - **Local Ollama**: `http://localhost:11434/v1`, model like `qwen2.5:7b` — fully offline.
3. Press **Test connection** to verify the key.

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
nothing to run.

Password typing is never written into steps: it becomes a
`recorded_secret_N` profile variable you fill in before replay.

## Safety model

- The model never returns code — only one validated JSON action per turn.
- Navigation is restricted to `http://`, `https://` and `file://`; dangerous
  URL schemes are rejected.
- Step and session limits cap runaway loops; consecutive failures stop the run.
- Everything runs locally: no CamouFlow servers, no telemetry.
