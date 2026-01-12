# Справочник шагов

Ниже перечислены шаги, которые поддерживает движок сценариев.

## Группы шагов (как в UI)

### Navigation & interaction

- `goto` — открыть URL
- `wait_for_load_state` — ждать состояние загрузки
- `wait_element` — ждать элемент
- `sleep` — пауза
- `click` — клик
- `type` — ввод текста

### Variables

- `set_var` — установить переменную
- `parse_var` — распарсить переменную по шаблону
- `pop_shared` — взять значение из shared списка/строки
- `extract_text` — извлечь текст/атрибут в переменную
- `write_file` — записать строку в `outputs/`

### Network

- `http_request` — HTTP(S) запрос (алиас `http`)

### Browser tabs

- `new_tab` — новая вкладка
- `switch_tab` — переключить вкладку
- `close_tab` — закрыть вкладку

### Flow & logging

- `start` — старт сценария
- `compare` — сравнение и ветвление
- `set_tag` — установить тег профиля
- `log` — сообщение в лог
- `run_scenario` — запустить вложенный сценарий
- `end` — завершить сценарий

## Общие поля (для большинства шагов)

- `tag` — уникальная метка шага (нужна для переходов).
- `description` — текст для лога (если указан, используется вместо action/tag).
- `timeout_ms` — таймаут (мс) для действий, которые его поддерживают.
- `next_success_step` / `next_error_step` — переходы по тегам.
- `on_error` / `on_error_target` — поведение при ошибках (см. `scenarios/flow.md`).

## Поля для шагов с селектором

Для шагов `click`, `type`, `wait_element`, `extract_text`:

- `selector` — селектор.
- `selector_type` — тип селектора: `css`, `text`, `xpath`, `id`, `name`, `test_id`.
- `selector_index` — индекс `nth()` если нужно выбрать элемент из списка совпадений.
- `frame_selector` — CSS-селектор iframe (если элемент внутри iframe).
- `frame_timeout_ms` — таймаут на поиск iframe (если нужен).
- `state` — состояние ожидания для `wait_element` (по умолчанию `visible`): `attached`, `detached`, `visible`, `hidden`.

Полное описание каждого шага — на его странице.
