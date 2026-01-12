# compare

Сравнивает значение (обычно из переменной) с другим значением (переменная или текст) и делает ветвление.

В UI этот шаг называется **Compare / if**.

## Ветвление

- “True” ветка: `next_success_step` (можно воспринимать как *YES*).
- “False” ветка: `next_error_step` (используется как *NO* ветка, хотя это не ошибка: просто переиспользуется поле перехода “на ошибке”).

Если “False” ветка не задана, а “True” задана — шаг остановит сценарий при ложном условии, чтобы не уйти по ошибке в true-ветку.

## Параметры

- `left_var` *(string)* — имя переменной слева (то, что сравниваем).
  - Алиасы: `var`, `name`, `from_var`.
- `value` *(string, optional)* — правое значение (текст), поддерживает `{{var}}`.
- `right_var` *(string, optional)* — имя переменной справа (если задано, используется вместо `value`).
- `op` *(string, optional)* — оператор (по умолчанию `equals`):
  - `equals`, `not_equals`
  - `contains`, `not_contains`
  - `startswith`, `endswith`
  - `regex`
  - `is_empty`, `not_empty`
  - `gt`, `gte`, `lt`, `lte` *(числовое сравнение; оба значения должны парситься как float)*
- `case_sensitive` *(bool, optional)* — чувствительность к регистру (по умолчанию `false`).
- `result_var` *(string, optional)* — куда записать результат (`true`/`false`).

## UI (как заполнять)

- **Variable** → `left_var`
- **Value** → `value` (если не используете `right_var`)
- **Right variable** → `right_var`
- **Compare operator** → `op`
- **Result variable** → `result_var`
- **Case sensitive** → `case_sensitive`

## Примеры

### Сравнить переменную с текстом

```json
{
  "action": "compare",
  "tag": "IsDone",
  "left_var": "stage",
  "value": "done",
  "op": "equals",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```

### Сравнить две переменные

```json
{
  "action": "compare",
  "tag": "SameCountry",
  "left_var": "country_a",
  "right_var": "country_b",
  "op": "equals",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```

### Проверить, что строка содержит подстроку

```json
{
  "action": "compare",
  "tag": "HasToken",
  "left_var": "token",
  "op": "not_empty",
  "next_success_step": "YES",
  "next_error_step": "NO"
}
```
