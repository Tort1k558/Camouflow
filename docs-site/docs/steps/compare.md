# compare

Compares a value (usually a variable) with another value (variable or text) and branches.

In the UI this step is named **Compare / if**.

## Branching

- "True" branch: `next_success_step` (can be read as *YES*).
- "False" branch: `next_error_step` (used as the *NO* branch; it is not an error, the field is reused).

If the False branch is not set but True is set, the step stops the scenario when the condition is false to avoid falling into the True branch.

## Parameters

- `left_var` *(string)* - left variable name (the value to compare).
  - Aliases: `var`, `name`, `from_var`.
- `value` *(string, optional)* - right value (text), supports `{{var}}`.
- `right_var` *(string, optional)* - right variable name (if set, used instead of `value`).
- `op` *(string, optional)* - operator (default `equals`):
  - `equals`, `not_equals`
  - `contains`, `not_contains`
  - `startswith`, `endswith`
  - `regex`
  - `is_empty`, `not_empty`
  - `gt`, `gte`, `lt`, `lte` *(numeric comparison; both values must parse as float)*
- `case_sensitive` *(bool, optional)* - case sensitivity (default `false`).
- `result_var` *(string, optional)* - store result (`true`/`false`) in this variable.

## UI mapping

- **Variable**  -> `left_var`
- **Value**  -> `value` (if not using `right_var`)
- **Right variable**  -> `right_var`
- **Compare operator**  -> `op`
- **Result variable**  -> `result_var`
- **Case sensitive**  -> `case_sensitive`

## Examples

### Compare a variable to text

```json
{
  "action": "compare",
  "tag": "IsDone",
  "left_var": "stage",
  "value": "done",
  "op": "equals",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```

### Compare two variables

```json
{
  "action": "compare",
  "tag": "SameCountry",
  "left_var": "country_a",
  "right_var": "country_b",
  "op": "equals",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```

### Check that a string is not empty

```json
{
  "action": "compare",
  "tag": "HasToken",
  "left_var": "token",
  "op": "not_empty",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```
