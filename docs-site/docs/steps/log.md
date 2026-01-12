# log

Writes a message to the execution log.

## Parameters

- `value` / `message` / `text` *(string)* - message (supports `{{var}}`).

## Example

```json
{ "action": "log", "tag": "Info", "value": "Profile={{email}} token={{token}}" }
```
