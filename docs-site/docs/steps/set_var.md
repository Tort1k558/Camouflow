# set_var

Устанавливает переменную сценария (и опционально shared).

## Параметры

- `name` / `variable` / `var` *(string)* — имя переменной.
- `value` *(string)* — значение (поддерживает `{{var}}`).
- `scope` *(string, optional)* — область: `profile` *(по умолчанию)*, `shared`, `both`.

## Пример

```json
{ "action": "set_var", "tag": "SetToken", "name": "token", "value": "{{login_token}}", "scope": "profile" }
```

