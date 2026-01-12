# goto

Открывает URL в текущей вкладке.

## Параметры

- `value` / `url` *(string)* — URL (поддерживает `{{var}}`).
- `wait_until` *(string, optional)* — событие ожидания навигации: `load`, `domcontentloaded`, `networkidle`, `commit`.
- `timeout_ms` *(int, optional)* — таймаут навигации (мс).

## Пример

```json
{
  "action": "goto",
  "tag": "Open",
  "value": "https://example.com/u/{{user_id}}",
  "wait_until": "load",
  "timeout_ms": 60000
}
```

