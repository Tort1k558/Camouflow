# Changelog

All notable changes to CamouFlow are documented here. The version number lives
in `app/version.py`; releases are tagged on GitHub with a ready-to-run Windows
build attached.

## Unreleased

## 0.4.0 - 2026-10-02

- AI tasks: starting URL/host policy, action confirmations, operator questions,
  pause/resume and partial action retention on stop; fixed silent click fallback
  and stale provider/profile readiness.
- Bounded table/text extraction, source URLs, preview and JSON/CSV export;
  editable contents excluded from snapshots, typed-password redaction hardened.
- Parameterized drafts, read-only replay/schema checks, workspace-scoped local
  history/restore and reviewed local starters with an isolated catalog demo.
- Local read-only JSON CLI using the existing run queue, shared desktop/CLI
  workspace lock, optional restricted MCP adapter and inactive n8n example.
- Added workflow walkthroughs and real-browser/UI verification scripts; fixed
  write_file traversal outside the outputs directory.

- Removed ~8,700 lines of dead legacy Qt-Widgets UI (`app/ui/main_window`,
  `app/ui/tabs`, `app/ui/scenario_editor.py`, `app/ui/style.py`,
  `app/ui/icons.py`, unused `run`/`cookies` bridges, `app/stages/stage_ads.py`).
  The QML app is the only interface; nothing user-facing changes.
- Added `app/version.py` as the single source of the version: shown in the
  window title and embedded into the Windows version resource of the EXE
  (`version_info.txt`, wired through `camouflow.spec`).
- Added this changelog.

## 0.3.1 — 2026-09-28

- Improved scenario automation release flow (run queue polish).
- Improved desktop workspace, scenario recording and profile lifecycle.
- Modern flat proxies list; fixed row stretching and the stat strip layout.
- Global toast notifications for app events.
- Account page: compact team console, sidebar account pod, non-blocking cloud
  calls with an async-fail fix.

## 0.3.0 — 2026-09-20

- Built-in AI browser agent (any OpenAI-compatible provider, including local
  Ollama) working on both engines; actions can be saved as a replayable
  scenario.
- Python scripting step for scenarios, executed in a supervised process with
  per-workspace approval.
- Run queue: persistent jobs, parallelism 1–8, one job per profile, interrupt
  handling after restart; results with screenshots and Playwright traces.

## 0.2.0 — 2026-09-19

- Teams v2 on the desktop: conflict center, pool sharing, invites UX.
- Google sign-in in the desktop app; cloud connection to camouflow.site by default.
- First public Windows build linked from the READMEs.

## Earlier

- Initial public repository and documentation (bilingual EN/RU README,
  camouflow.site docs).
