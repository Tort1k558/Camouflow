# Transitions and errors

## Default flow

If a step has no explicit transitions, the scenario executes steps in order.

## Tag-based transitions

Branching is defined by step tags:

- `tag` - unique step label (auto-generated in the editor, e.g. `Step1`, `Step2`).
- `next_success_step` - jump on success.
- `next_error_step` - jump on error.

## Error behavior

If a step fails:

- when `next_error_step` is set, the scenario jumps to that tag.
- otherwise the scenario stops with an error.

## Scenario end

- The `end` step closes the browser and ends the scenario.
- Nested scenarios (`run_scenario`) have recursion protection.

## Conditions (compare)

The `compare` step is used for conditional branching:

- `next_success_step` - **True** branch (*YES*)
- `next_error_step` - **False** branch (*NO*)
