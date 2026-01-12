# Scenario format

A scenario is a JSON file with the following fields:

- `name`: scenario name
- `description`: description (optional)
- `steps`: list of step objects

Files are stored in `scenaries/*.json`.

## Minimal example

```json
{
  "name": "Demo",
  "description": "Example",
  "steps": [
    { "action": "start", "tag": "Start" },
    { "action": "goto", "tag": "Open", "value": "https://example.com" },
    { "action": "end", "tag": "End" }
  ]
}
```

## Common step fields

Most steps can include:

- `action` *(string)* - step type (see the step reference).
- `tag` *(string)* - unique step label used for transitions.
- `description` *(string)* - log text (optional).
- `timeout_ms` *(int)* - timeout (ms) for actions that support it.

### Transitions

Transitions are defined with:

- `next_success_step` - target `tag` for success.
- `next_error_step` - target `tag` for error.

If no transitions are set, the scenario goes to the next step in the list.

Details: `scenarios/flow.md`.
