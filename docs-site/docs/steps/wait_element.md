# wait_element

Waits for an element to appear or disappear.

## Parameters

- `selector` *(string)* - selector.
- `selector_type` *(string, optional)* - `css`, `text`, `xpath`, `id`, `name`, `test_id`.
- `selector_index` *(int, optional)* - select a specific `nth()` match.
- `frame_selector` *(string, optional)* - iframe selector.
- `frame_timeout_ms` *(int, optional)* - iframe lookup timeout (ms).
- `state` *(string, optional)* - `attached`, `detached`, `visible`, `hidden` (default `visible`).
- `timeout_ms` *(int, optional)* - wait timeout (ms).

## Example

```json
{
  "action": "wait_element",
  "tag": "WaitLogin",
  "selector": "data-testid=login-form",
  "selector_type": "test_id",
  "state": "visible",
  "timeout_ms": 15000
}
```
