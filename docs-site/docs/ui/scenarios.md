# Scenarios

The **Scenarios** page is the scenario library and visual node editor.

## Saved tasks

Use **Tasks** to run a saved scenario through its input form without opening the
node editor. Search matches task names and descriptions, ignoring case. Filtering
does not clear the selected task or its current inputs; clear the search to show
the full library again. A search with no matches is distinct from an empty library.

Queue a task after reviewing its steps, then resume explicitly in **Runs**.
Canceled pending jobs remain in local run history even after the finished queue
is cleared. Running jobs are recorded only after execution and cleanup finish.
History and queue are workspace-scoped; clearing history is a separate action.

## Scenario library

Click the current scenario card to open the library.

Actions:

- **New** creates a scenario.
- **Duplicate** copies the selected scenario.
- **Delete** removes it.
- **Save** saves name, description and steps.

Scenarios are stored in `scenaries/*.json`.

## Action map

The center canvas is the visual scenario map:

- drag nodes to reposition steps
- pan and zoom the canvas
- connect nodes with success/error links
- right-click nodes for edit/duplicate/move/delete
- right-click links to delete them

Transitions are saved as `next_success_step` and `next_error_step`.

## Node properties

The right panel edits the selected step:

- tag
- action
- selector and selector type
- value / URL / text
- variable name
- pattern / targets
- timeout and sleep duration
- success/error target tags
- **Extra JSON** for action-specific fields

`Extra JSON` is merged into the step and is used for advanced fields such as HTTP headers/body, compare operator, tab index, file name, attributes and result variables.

The **Raw step** block shows the final JSON for the selected step.

## Action templates

The left panel groups available actions:

- navigation and interaction
- variables
- network
- browser tabs
- flow and logging

Adding a template creates a default step with safe starter values.

## Shared variables

The **Variables** button opens the shared variables editor. Shared variables can be strings, numbers or lists and are available in all scenarios.

## Run selected scenario

Select a profile in the top bar and press **Run** to execute the current scenario for that profile.
