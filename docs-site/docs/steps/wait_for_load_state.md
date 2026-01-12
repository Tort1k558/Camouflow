# wait_for_load_state

Waits for the page to reach a given load state.

## Parameters

- `state` *(string, optional)* - `load`, `domcontentloaded`, `networkidle`, `commit` (default `load`).
- `timeout_ms` *(int, optional)* - wait timeout (ms).

## Example

```json
{ "action": "wait_for_load_state", "tag": "Loaded", "state": "networkidle", "timeout_ms": 60000 }
```
