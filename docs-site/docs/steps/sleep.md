# sleep

Пауза.

## Параметры

- `seconds` *(float, optional)* — длительность паузы.
- `timeout_ms` *(int, optional)* — если `seconds` не задан, используется `timeout_ms/1000`.

## Пример

```json
{ "action": "sleep", "tag": "Delay", "seconds": 1.5 }
```

