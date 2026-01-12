# Step reference

Below are the steps supported by the scenario engine.

## Step groups (as in the UI)

### Navigation & interaction

- `goto` - open a URL
- `wait_for_load_state` - wait for page load state
- `wait_element` - wait for an element
- `sleep` - pause
- `click` - click
- `type` - type text

### Variables

- `set_var` - set a variable
- `parse_var` - parse a variable using a template
- `pop_shared` - pop a value from a shared list/string
- `extract_text` - extract text/attribute into a variable
- `write_file` - write a string to `outputs/`

### Network

- `http_request` - HTTP(S) request (alias `http`)

### Browser tabs

- `new_tab` - new tab
- `switch_tab` - switch tab
- `close_tab` - close tab

### Flow & logging

- `start` - scenario start
- `compare` - compare and branch
- `set_tag` - set profile tag
- `log` - log message
- `run_scenario` - run a nested scenario
- `end` - end scenario

## Common fields (most steps)

- `tag` - unique step label (used for transitions).
- `description` - log text (if set, used instead of action/tag).
- `timeout_ms` - timeout (ms) for actions that support it.
- `next_success_step` / `next_error_step` - tag-based transitions.

## Selector-based step fields

For `click`, `type`, `wait_element`, `extract_text`:

- `selector` - selector.
- `selector_type` - selector type: `css`, `text`, `xpath`, `id`, `name`, `test_id`.
- `selector_index` - `nth()` index when you need a specific match.
- `frame_selector` - iframe CSS selector (if element is inside an iframe).
- `frame_timeout_ms` - iframe lookup timeout (optional).
- `state` - wait state for `wait_element` (default `visible`): `attached`, `detached`, `visible`, `hidden`.

Full details for each step are on its own page.
