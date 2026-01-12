# sleep

Pause.

## Parameters

- `seconds` *(float, optional)* - pause duration.
- `timeout_ms` *(int, optional)* - if `seconds` is not set, uses `timeout_ms/1000`.

## Example

```json
{ "action": "sleep", "tag": "Delay", "seconds": 1.5 }
```
