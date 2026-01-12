# write_file

Пишет строку в файл внутри `outputs/` (абсолютные пути запрещены).

## Параметры

- `filename` / `file` *(string)* — относительный путь файла (например `result.txt` или `folder/result.txt`).
- `value` *(string)* — текст для записи (поддерживает `{{var}}`).

## Примечания

- Если файл существует — добавляет строку в конец (append).
- Если в конце файла нет переноса строки — добавит перенос перед записью.

## Пример

```json
{
  "action": "write_file",
  "tag": "Save",
  "filename": "results/{{timestamp}}.txt",
  "value": "{{email}} | {{title}}"
}
```

