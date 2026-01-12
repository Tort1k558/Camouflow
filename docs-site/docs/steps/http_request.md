# http_request

Выполняет HTTP(S) запрос через `context.request.fetch` (Playwright). Cookies контекста учитываются и обновляются автоматически.

Алиас: `http`.

## Параметры (основные)

- `value` / `url` *(string)* — URL (поддерживает `{{var}}`).
- `method` *(string, optional)* — HTTP метод (по умолчанию `GET`).
- `headers` *(object, optional)* — заголовки `{ "Header": "value" }`.
- `params` *(object|string, optional)* — query параметры (объект или строка `a=1&b=2`).
- `data` *(any|string|bytes, optional)* — тело запроса.
  - Синонимы: `json`, `body`.
- `form` *(object, optional)* — `application/x-www-form-urlencoded`.
- `multipart` *(object, optional)* — `multipart/form-data` (простые поля).
- `timeout_ms` *(int, optional)* — таймаут (мс).
- `max_redirects` *(int, optional)*, `max_retries` *(int, optional)*.
- `fail_on_status_code` *(bool, optional)* — ошибка при non-2xx на уровне Playwright.
- `ignore_https_errors` *(bool, optional)*.

## Параметры (результаты)

- `save_as` *(string, optional)* — префикс переменных результата (по умолчанию `http`):
  - `{save_as}_status`, `{save_as}_ok`, `{save_as}_headers`, `{save_as}_body`, `{save_as}_json`, `{save_as}_url`
- `response_var` *(string, optional)* — записать весь ответ в одну переменную (JSON-строка).
- `extract_json` *(object, optional)* — маппинг `{ "var": "path" }` для извлечения значений из JSON-ответа.
  - `path` поддерживает `$.a.b[0].c` (упрощённый JSONPath, `$` — корень).
- `require_success` *(bool, optional)* — если `true`, шаг остановит сценарий при статусе не 2xx.

## Пример: POST JSON + извлечение токена

```json
{
  "action": "http_request",
  "tag": "LoginApi",
  "value": "https://example.com/api/login",
  "method": "POST",
  "headers": { "Content-Type": "application/json" },
  "data": { "email": "{{email}}", "password": "{{password}}" },
  "save_as": "login",
  "extract_json": { "token": "$.token", "user_id": "$.user.id" },
  "require_success": true
}
```

## Редактор в UI (без JSON)

В интерфейсе параметры задаются полями:

- **HTTP method** → `method`
- **HTTP headers** (строки `Header: value`) → `headers`
- **Query params** (строки `key=value`) → `params`
- **Body** + **Parse body as JSON** → `data` (строка или JSON)
- **Save as** → `save_as`
- **Response var** → `response_var`
- **Extract JSON** (строки `var=$.path`) → `extract_json`
- чекбоксы/числа → `require_success`, `fail_on_status_code`, `ignore_https_errors`, `max_redirects`, `max_retries`
