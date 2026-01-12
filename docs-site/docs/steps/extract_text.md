# extract_text

Reads text (or an attribute) from an element and saves it into a variable.

## Parameters

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` - see `steps/index.md`.
- `attribute` *(string, optional)* - attribute name (if not set, uses `textContent`).
- `strip` *(bool, optional)* - trim whitespace (default `true`).
- `to_var` / `var` / `name` *(string, optional)* - target variable name (default `last_value`).

## Example

```json
{
  "action": "extract_text",
  "tag": "ReadTitle",
  "selector": "css=h1",
  "to_var": "title"
}
```
