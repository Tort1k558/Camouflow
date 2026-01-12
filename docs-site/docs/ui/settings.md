# Settings

Вкладка **Settings** задаёт глобальные настройки Camoufox, которые применяются ко всем профилям (если не переопределены на уровне профиля).

## Appearance

Выбор темы оформления приложения.

Добавлены темы **CamouFlow Orange** (Light/Dark) с оранжевыми акцентами под бренд/лого.

По умолчанию используется **CamouFlow Orange (Light)**, а прежние Light/Dark остаются как “Classic” варианты.

## Camoufox defaults

Настройки разбиты по вкладкам внутри Settings. Общая идея:

- **Auto** — использовать автоматические/рекомендуемые значения.
- **Set** — вручную задать значение.

Типовые параметры (может меняться в зависимости от версии):

- **Headless** — запуск с окном / headless.
- **Humanize** — “человеческие” задержки ввода/движения.
- **Locale / Timezone** — локаль и часовой пояс.
- **OS / Fonts** — имитация ОС и список шрифтов.
- **Window** — метрики окна/экрана (включая `screen.*`, `innerWidth/innerHeight` и др.).
- **Navigator** — переопределение `navigator.*` (например `userAgent`, `platform`, `languages` и т.п.).
- **Privacy / Network** — блокировки WebRTC / images / WebGL, cache, COOP и т.п.

Ниже — смысл ключевых параметров (ориентируйтесь по названиям в UI; часть полей может быть доступна только в Settings/профильных overrides).

### Общие

- **headless** — режим запуска браузера (с окном или без).
- **persistent_context** — использовать persistent context (профиль сохраняется на диск в `profiles/`).
- **enable_cache** — включить/выключить кэш.

### Локаль и среда

- **locale** — локаль интерфейса/языков (например `en-US`, `ru-RU`).
- **timezone** — часовой пояс (например `Europe/Moscow`).
- **os** — имитация ОС (Auto или выбор Windows/MacOS/Linux).
- **fonts** — список шрифтов (по одному на строку).

### Window / Screen overrides

Вкладка **Window** позволяет вручную задавать значения метрик окна/экрана, которые используются в JS-окружении страницы.
Примеры параметров:

- `screen.width`, `screen.height`, `screen.availWidth`, `screen.availHeight`
- `browser.innerWidth`, `browser.innerHeight`, `browser.outerWidth`, `browser.outerHeight`
- `browser.devicePixelRatio`

Если оставить Auto — используются значения по умолчанию.

### Navigator overrides

Вкладка **Navigator** позволяет переопределять свойства `navigator.*`.
Обычно это строки/списки/числа/булевы значения (в UI есть переключатель Auto/Set или выпадающий Auto/True/False).

### Privacy / Network

- **block_webrtc** — блокировать WebRTC.
- **block_images** — блокировать загрузку изображений.
- **block_webgl** — блокировать WebGL.
- **disable_coop** — настройка COOP (Cross-Origin-Opener-Policy) для совместимости/изоляции.
- **webgl_vendor / webgl_renderer** — ручная подмена Vendor/Renderer (если доступно в UI).

## Кнопки

- **Save** — сохранить настройки.
- **Reset to recommended** — сбросить на рекомендуемые значения.
