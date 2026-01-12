# new_tab

Открывает новую вкладку (страницу) и делает её активной.

## Параметры

- `value` / `url` *(string, optional)* — URL для открытия.
- `wait_until` *(string, optional)* — `load`, `domcontentloaded`, `networkidle`, `commit`.
- `timeout_ms` *(int, optional)* — таймаут навигации (мс).

## Пример

```json
{ "action": "new_tab", "tag": "OpenTab", "value": "https://example.com" }
```

