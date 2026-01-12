# extract_text

Считывает текст (или атрибут) из элемента и сохраняет в переменную.

## Параметры

- `selector`, `selector_type`, `selector_index`, `frame_selector`, `timeout_ms` — см. `steps/index.md`.
- `attribute` *(string, optional)* — имя атрибута (если не задано — берётся `textContent`).
- `strip` *(bool, optional)* — обрезать пробелы (по умолчанию `true`).
- `to_var` / `var` / `name` *(string, optional)* — имя переменной (по умолчанию `last_value`).

## Пример

```json
{
  "action": "extract_text",
  "tag": "ReadTitle",
  "selector": "css=h1",
  "to_var": "title"
}
```

