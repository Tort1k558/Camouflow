# set_tag

Sets the tag (stage) for the current profile.

## Parameters

- `value` / `tag` / `stage` *(string)* - new tag value (supports `{{var}}`).

## Example

```json
{ "action": "set_tag", "tag": "MarkDone", "value": "done" }
```

## Note

Historical alias: `set_stage` (normalized to `set_tag` in the editor).
