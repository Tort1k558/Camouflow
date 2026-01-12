# run_scenario

Runs another scenario inside the current one.

## Parameters

- `scenario` / `scenario_name` / `name` / `value` *(string)* - scenario name (supports `{{var}}`).

## Notes

- The nested scenario inherits variables and can modify them.
- Recursion protection is enabled (you cannot call a scenario already in the call stack).

## Example

```json
{ "action": "run_scenario", "tag": "DoSubflow", "value": "SubScenarioName" }
```
