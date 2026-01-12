# click

Clicks an element.

## Parameters

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` - see `steps/index.md`.
- `button` *(string, optional)* - mouse button: `left`, `right`, `middle`.
- `click_delay_ms` *(int, optional)* - click delay (ms).

## Example

```json
{
  "action": "click",
  "tag": "Submit",
  "selector": "button[type=submit]",
  "selector_type": "css",
  "timeout_ms": 10000
}
```
