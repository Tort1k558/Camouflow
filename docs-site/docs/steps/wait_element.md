# wait_element

Ждёт появления/исчезновения элемента.

## Параметры

- `selector` *(string)* — селектор.
- `selector_type` *(string, optional)* — `css`, `text`, `xpath`, `id`, `name`, `test_id`.
- `selector_index` *(int, optional)* — выбрать `nth()` совпадение.
- `frame_selector` *(string, optional)* — iframe selector.
- `frame_timeout_ms` *(int, optional)* — таймаут поиска iframe (мс).
- `state` *(string, optional)* — `attached`, `detached`, `visible`, `hidden` (по умолчанию `visible`).
- `timeout_ms` *(int, optional)* — таймаут ожидания (мс).

## Пример

```json
{
  "action": "wait_element",
  "tag": "WaitLogin",
  "selector": "data-testid=login-form",
  "selector_type": "test_id",
  "state": "visible",
  "timeout_ms": 15000
}
```

