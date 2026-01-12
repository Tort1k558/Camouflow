# pop_shared

Takes the first item from a shared variable (list or multi-line string), saves the remainder back, and maps values to variables using a template.

## Parameters

- `value` *(string)* - shared variable key (supports `{{var}}`).
- `pattern` / `targets_string` *(string)* - template with placeholders, e.g. `{{email}}|{{password}}`.
  - The template must match the string entirely.
  - Separators/whitespace in the template allow flexible spacing.

## What it does

- Removes the first element from the list/string.
- Updates the shared variable and saves it in settings.
- Writes extracted values into scenario variables.
- Attempts to update the profile in the database (so fields persist).

## Example

```json
{
  "action": "pop_shared",
  "tag": "TakeCreds",
  "value": "accounts_pool",
  "pattern": "{{email}};{{password}}"
}
```
