# new_tab

Opens a new tab (page) and activates it.

## Parameters

- `value` / `url` *(string, optional)* - URL to open.
- `wait_until` *(string, optional)* - `load`, `domcontentloaded`, `networkidle`, `commit`.
- `timeout_ms` *(int, optional)* - navigation timeout (ms).

## Example

```json
{ "action": "new_tab", "tag": "OpenTab", "value": "https://example.com" }
```
