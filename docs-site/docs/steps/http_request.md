# http_request

Performs an HTTP(S) request via `context.request.fetch` (Playwright). Context cookies are automatically included and updated.

Alias: `http`.

## Parameters (main)

- `value` / `url` *(string)* - URL (supports `{{var}}`).
- `method` *(string, optional)* - HTTP method (default `GET`).
  - Alias: `http_method`.
- `headers` *(object, optional)* - headers `{ "Header": "value" }`.
- `params` *(object|string, optional)* - query params (object or string `a=1&b=2`).
  - Aliases: `query`, `query_params`.
- `data` *(any|string|bytes, optional)* - request body.
  - Aliases: `json`, `body`.
- `form` *(object, optional)* - `application/x-www-form-urlencoded`.
- `multipart` *(object, optional)* - `multipart/form-data` (simple fields).
- `timeout_ms` *(int, optional)* - timeout (ms).
- `max_redirects` *(int, optional)*, `max_retries` *(int, optional)*.
- `fail_on_status_code` *(bool, optional)* - error on non-2xx at the Playwright level.
- `ignore_https_errors` *(bool, optional)*.

## Parameters (results)

- `save_as` *(string, optional)* - result variable prefix (default `http`):
  - `{save_as}_status`, `{save_as}_ok`, `{save_as}_headers`, `{save_as}_body`, `{save_as}_json`, `{save_as}_url`
  - Aliases: `result_prefix`, `prefix`, `var_prefix`.
- `response_var` *(string, optional)* - store the whole response in one variable (JSON string).
  - Alias: `to_var`.
- `extract_json` *(object, optional)* - mapping `{ "var": "path" }` to extract values from JSON response.
  - `path` supports `$.a.b[0].c` (simplified JSONPath, `$` is the root).
  - Alias: `json_extract`.
- `require_success` *(bool, optional)* - if `true`, stop the scenario when status is non-2xx.

## Example: POST JSON + extract token

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

## UI editor (no JSON)

In the UI, fields map to:

- **HTTP method**  -> `method`
- **HTTP headers** (lines `Header: value`)  -> `headers`
- **Query params** (lines `key=value`)  -> `params`
- **Body** + **Parse body as JSON**  -> `data` (string or JSON)
- **Save as**  -> `save_as`
- **Response var**  -> `response_var`
- **Extract JSON** (lines `var=$.path`)  -> `extract_json`
- checkboxes/numbers  -> `require_success`, `fail_on_status_code`, `ignore_https_errors`, `max_redirects`, `max_retries`
