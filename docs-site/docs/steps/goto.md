# goto

Opens a URL in the current tab.

## Parameters

- `value` / `url` *(string)* - URL (supports `{{var}}`).
- `wait_until` *(string, optional)* - navigation wait event: `load`, `domcontentloaded`, `networkidle`, `commit`.
- `timeout_ms` *(int, optional)* - navigation timeout (ms).

## Example

```json
{
  "action": "goto",
  "tag": "Open",
  "value": "https://example.com/u/{{user_id}}",
  "wait_until": "load",
  "timeout_ms": 60000
}
```
