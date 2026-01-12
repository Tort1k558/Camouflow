# write_file

Writes a line to a file inside `outputs/` (absolute paths are not allowed).

## Parameters

- `filename` / `file` *(string)* - relative file path (e.g. `result.txt` or `folder/result.txt`).
- `value` *(string)* - text to write (supports `{{var}}`).

## Notes

- If the file exists, the line is appended.
- If the file does not end with a newline, one is added before writing.

## Example

```json
{
  "action": "write_file",
  "tag": "Save",
  "filename": "results/{{timestamp}}.txt",
  "value": "{{email}} | {{title}}"
}
```
