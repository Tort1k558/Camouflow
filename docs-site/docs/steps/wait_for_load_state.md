# wait_for_load_state

Ждёт, пока страница достигнет нужного состояния загрузки.

## Параметры

- `state` *(string, optional)* — `load`, `domcontentloaded`, `networkidle`, `commit` (по умолчанию `load`).
- `timeout_ms` *(int, optional)* — таймаут ожидания (мс).

## Пример

```json
{ "action": "wait_for_load_state", "tag": "Loaded", "state": "networkidle", "timeout_ms": 60000 }
```

