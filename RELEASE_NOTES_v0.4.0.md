# CamouFlow 0.4.0

Describe a browser task, inspect its outputs, then replay a reviewed workflow without another model request.

## New

- Isolated catalog demo and three local starters: catalog to JSON, page to text, form fill without submission.
- Structured table/text extraction, source URLs, preview, JSON/CSV export and workspace-scoped AI history.
- Starting URL/host policy, default action confirmations, operator questions, pause/resume and completed step retention on stop.
- Exact input parameterization, read-only replay/schema checks and workflow export.
- Source-only local JSON CLI, optional restricted stdio MCP and an inactive n8n example.
- Fixed stale provider/profile readiness, false click success, editable-content exposure and output path traversal.

## Try it

Settings -> AI: configure and test a Chat Completions-compatible provider. Scenarios -> AI -> Try isolated demo -> Start. Inspect/export the table, parameterize the demo URL, check replay and save. The provider may charge for the first AI task; deterministic replay does not call the model.

[English guide](https://github.com/Tort1k558/Camouflow/blob/v0.4.0/AI_WORKFLOWS.md) · [Русская инструкция](https://github.com/Tort1k558/Camouflow/blob/v0.4.0/AI_WORKFLOWS.ru.md) · [Recorded real UI demo](https://github.com/Tort1k558/Camouflow/blob/v0.4.0/images/ai-workflow-demo.gif)

## Verified

78 automated tests; real-browser fixture extraction/replay and CLI/MCP checks on Camoufox and CloakBrowser; three successful configured DeepSeek runs on each engine; real-provider UI export/replay/save; isolated Windows n8n 2.41.5 import/execution/JSON parsing; packaged runtime checks on both engines; 35 documentation pages built without warnings.

These are synthetic catalog checks, not a benchmark of every model or website. Live cloud auth/list access was checked read-only; production cloud runs were not exercised.

## Data and upgrade

Page text, labels, URLs, instructions, outputs and operator answers go to the configured provider. Editable contents are excluded; this is not universal secret detection. Automatic replay checks are read-only. An interrupted action may already have changed a page. CLI/MCP require the source Python environment, not the windowed EXE; close the desktop first. MCP request cancellation does not cancel an already-started local run.

Windows package: unzip into a new folder. Back up your existing `settings`, `profiles` and `scenaries` before moving data. No personal profiles, API keys or cloud credentials are included. Browser binaries may be downloaded on first use.

## Кратко по-русски

AI-задача теперь выдаёт проверяемые данные и превращается в параметризованный сценарий. Добавлены таблицы, JSON/CSV, история, подтверждения, пауза, демо и шаблоны. Проверены реальная DeepSeek, оба движка, CLI/MCP и отдельный n8n. Повтор работает без запросов к модели; интерактивные сценарии требуют ручной проверки. Популярность и совместимость со всеми сайтами не гарантируются.
