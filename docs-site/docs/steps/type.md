# type

Печатает текст в поле (символ за символом).

## Параметры

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` — см. `steps/index.md`.
- `value` / `text` *(string)* — вводимый текст (поддерживает `{{var}}`).
- `clear` *(bool, optional)* — очистить поле перед вводом (по умолчанию `true`).

## Пример

```json
{
  "action": "type",
  "tag": "TypeEmail",
  "selector": "input[name=email]",
  "value": "{{email}}",
  "clear": true
}
```

