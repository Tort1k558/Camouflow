# parse_var

Takes a string from a variable and parses it using a template, saving parts into other variables.

## Parameters

- `from_var` *(string)* - source variable name.
  - Aliases: `var`, `name`.
- `pattern` / `targets_string` *(string)* - template with placeholders, e.g. `{{email}};{{password}}`.
- `update_account` *(bool, optional)* - if `true`, save extracted fields into profile data. Default: `true`.

## UI mapping

- **Variable**  -> `from_var`
- **Targets / pattern**  -> `pattern`
- **Update account (save to profile)**  -> `update_account`

## How the template works

- The template must contain `{{name}}` placeholders.
- Matching is strict: the entire string must match the template.
- Whitespace in the template is flexible (can be present or omitted).

## Example

Suppose `raw` contains:

```
user@example.com;pass123
```

Step:

```json
{
  "action": "parse_var",
  "tag": "ParseCreds",
  "from_var": "raw",
  "pattern": "{{email}};{{password}}"
}
```

After the step, variables `{{email}}` and `{{password}}` will be available.
