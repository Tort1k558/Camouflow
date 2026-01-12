# set_var

Sets a scenario variable (and optionally shared).

## Parameters

- `name` / `variable` / `var` *(string)* - variable name.
- `value` *(string)* - value (supports `{{var}}`).
- `scope` *(string, optional)* - scope: `profile` *(default)*, `shared`, `both`.

## Example

```json
{ "action": "set_var", "tag": "SetToken", "name": "token", "value": "{{login_token}}", "scope": "profile" }
```
