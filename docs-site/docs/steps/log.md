# log

Пишет сообщение в лог выполнения.

## Параметры

- `value` / `message` / `text` *(string)* — сообщение (поддерживает `{{var}}`).

## Пример

```json
{ "action": "log", "tag": "Info", "value": "Profile={{email}} token={{token}}" }
```

