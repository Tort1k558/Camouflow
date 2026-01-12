# parse_var

Берёт строку из переменной и “разбирает” её по шаблону, записывая части в другие переменные.

## Параметры

- `from_var` *(string)* — имя переменной-источника.
  - Алиасы: `var`, `name`.
- `pattern` / `targets_string` *(string)* — шаблон с плейсхолдерами, например `{{email}};{{password}}`.
- `update_account` *(bool, optional)* — если `true`, сохранит извлечённые поля в данные профиля. По умолчанию: `true`.

## UI (как заполнять)

- **Variable** → `from_var`
- **Targets / pattern** → `pattern`
- **Update account (save to profile)** → `update_account`

## Как работает шаблон

- Шаблон должен содержать плейсхолдеры `{{name}}`.
- Сопоставление строгое: строка должна “целиком” соответствовать шаблону.
- Пробелы в шаблоне считаются гибкими (могут быть любыми/отсутствовать).

## Пример

Допустим, в переменной `raw` лежит:

```
user@example.com;pass123
```

Шаг:

```json
{
  "action": "parse_var",
  "tag": "ParseCreds",
  "from_var": "raw",
  "pattern": "{{email}};{{password}}"
}
```

После шага появятся переменные `{{email}}` и `{{password}}`.
