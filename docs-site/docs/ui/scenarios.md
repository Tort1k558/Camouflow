# Scenarios

The **Scenarios** tab is the scenario library and visual step editor.

## Scenario library

List of scenarios on the left.

- **New** - create a new scenario.
- **Load** - load the selected one.
- **Save** - save the current scenario.
- **Delete** - delete.

Scenarios are stored in `scenaries/*.json`.

## Details

Top right:

- **Name** - scenario name (library key).
- **Description** - description.
- **Variables in scenario** - detected variables (from steps that use `name/to_var/save_as`).

## Action map

The main editor is **Action map**:

- Each block is a scenario step.
- Blocks are connected by arrows (success/error) to define transitions.
- Double-click or the edit button opens the step settings modal.

More about format and transitions: `scenarios/format.md`, `scenarios/flow.md`.

## Step modal

When adding/editing a step, a settings modal opens. Fields depend on the action:

- For selector-based steps (`click`, `type`, `wait_element`, `extract_text`), selector/type/index/iframe fields are shown.
- For `http_request`, method/headers/params/body/result fields are shown.
- For `parse_var`, source variable, pattern, and **Update account** option are shown.
- For `compare`, operator and right value (variable or text) are shown; branching uses `next_success_step` (True) and `next_error_step` (False).
- For `write_file`, file name.
- For `sleep`, duration.
- For `switch_tab`/`close_tab`, tab index.

If the modal does not fit the screen, it becomes scrollable.
