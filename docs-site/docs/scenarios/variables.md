# Variables and templates

Scenarios support `{{var}}` placeholders in string fields.

## Variable sources

Variables are collected from:

- profile fields (imported values such as `email`, `password`, and any others from the import template)
- `extra_fields` (if present)
- shared variables
- values set by steps (e.g. `set_var`, `extract_text`, `http_request`)
  - also `parse_var` (extracted values)

## `{{var}}` substitution

Any string can include placeholders:

- `"Authorization: Bearer {{token}}"`
- `"https://example.com/u/{{user_id}}/settings"`

If a variable is missing, an empty string is inserted.

## Built-in variables

Some variables are provided automatically:

- `{{cookies}}` - JSON string with cookies, refreshed before a step if it uses the cookies template.
- `{{timestamp}}` - local timestamp `YYYY-MM-DD-HH-MM-SS`, refreshed before a step if it uses the timestamp template.

## Shared variables

Shared variables are a common store available to all profiles during a run.

Types:

- `string` - a single string
- `list` - list of strings (edited as one value per line in the UI)

Usage:

- Use `{{key}}` in steps like a normal variable.
- Use `pop_shared` to take values from the shared list and map them to variables.
