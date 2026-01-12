# click

Кликает по элементу.

## Параметры

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` — см. `steps/index.md`.
- `button` *(string, optional)* — кнопка мыши: `left`, `right`, `middle`.
- `click_delay_ms` *(int, optional)* — задержка клика (мс).

## Пример

```json
{
  "action": "click",
  "tag": "Submit",
  "selector": "button[type=submit]",
  "selector_type": "css",
  "timeout_ms": 10000
}
```

