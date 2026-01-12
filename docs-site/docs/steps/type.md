# type

Types text into a field (character by character).

## Parameters

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` - see `steps/index.md`.
- `value` / `text` *(string)* - input text (supports `{{var}}`).
- `clear` *(bool, optional)* - clear the field before typing (default `true`).

## Example

```json
{
  "action": "type",
  "tag": "TypeEmail",
  "selector": "input[name=email]",
  "value": "{{email}}",
  "clear": true
}
```
