<p align="center">
  <img src="images/logo.svg" width="84" alt="CamouFlow" />
</p>

<h1 align="center">CamouFlow</h1>

<p align="center"><a href="README.md">English</a> · <b>Русский</b></p>

<p align="center">
  <b>Браузерные профили. Визуальная автоматизация. Ваше рабочее пространство.</b><br/>
  Local-first менеджер для Camoufox, CloakBrowser и собственного движка Glint в разработке.
</p>

<p align="center">
  <a href="https://github.com/Tort1k558/Camouflow/releases/latest"><img alt="Релиз приложения" src="https://img.shields.io/github/v/release/Tort1k558/Camouflow?label=desktop&color=202820&labelColor=d1f366" /></a>
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-202820?labelColor=d1f366" />
  <img alt="Glint development preview" src="https://img.shields.io/badge/Glint-development%20preview-202820?labelColor=d1f366" />
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/license-MIT-202820?labelColor=d1f366" /></a>
</p>

<p align="center">
  <a href="https://github.com/Tort1k558/Camouflow/releases/latest">Скачать</a> ·
  <a href="https://camouflow.site/docs">Документация</a> ·
  <a href="docs/GLINT_TEST_MATRIX.md">Результаты Glint</a> ·
  <a href="native/BUILDING.md">Сборка Glint</a> ·
  <a href="CONTRIBUTING.ru.md">Участие в разработке</a>
</p>

## Весь браузерный процесс — в одном месте

| Работа с профилями | Визуальные сценарии |
| :---: | :---: |
| ![Постоянные профили, теги и настройки](images/profiles.png) | ![Визуальный редактор сценариев](images/scenarios.png) |
| Отдельные сессии, настройки движка и назначения прокси. | Действия со связями «успех / ошибка». |

| Возможность | Пример использования |
| --- | --- |
| **Постоянные профили** | Организовать профили по тегам и запустить сценарий для выбранной группы. |
| **Пулы прокси** | Импортировать подключения, проверить здоровье, назначить пул; недоступное назначение не переключается на прямую сеть. |
| **Визуальная автоматизация** | Открыть каталог → извлечь строки → проверить условие → экспортировать результат. |
| **AI → проверка → replay** | Описать задачу, проверить действия и повторять без нового обращения к модели. |
| **Очередь и отладка** | Запланировать запуски; пошагово разобрать ошибку и посмотреть скриншоты/traces. |
| **Backup & restore** | Сохранить архив профиля с контрольными суммами; восстановить с новой идентичностью. |
| **Командная работа — опционально** | Назначать поручения, проверять запуски и запрашивать помощь через приватный сервер. |

## Описать. Проверить. Повторять.

![Извлечение каталога моделью и проверка сценария](images/ai-workflow-demo.png)

**Пример:** извлечь синтетический каталог → проверить таблицу → экспортировать
JSON/CSV → сохранить параметризованный сценарий → проверить read-only replay.

[Запись UI-демо](images/ai-workflow-demo.gif) · [Быстрый старт AI](docs/AI_WORKFLOWS.ru.md) ·
[CLI / MCP / n8n](docs/AI_WORKFLOWS.md#local-cli)

> Успех от модели не равен проверенному replay. Содержимое страниц передаётся
> выбранному AI-провайдеру; исключение редактируемых полей не скрывает все секреты.

## Выберите движок

| Движок | Основа | Статус |
| --- | --- | --- |
| **Camoufox** | Сторонний Firefox-based движок | Интегрированы настраиваемые антидетект-профили |
| **CloakBrowser** | Сторонний Chromium-based движок | Интегрированы настраиваемые антидетект-профили |
| **Glint** | **Наш публичный форк Chromium/Blink** | **Windows preview в разработке**, нативные C++/Mojo-политики |

Настройки зависят от движка. Glint — не переименование чужого браузера;
неподдерживаемые настройки не заменяются молча. Релиз приложения не обязательно
содержит последнюю экспериментальную сборку Glint.

### Glint: что реализовано

| Область | Что есть | Что осталось |
| --- | --- | --- |
| Идентичность и контексты | Приватные ключи профилей; derivation по partition/surface на стороне браузера | Полный генератор согласованных паспортов устройств |
| Hardware и шрифты | Нативные ограничения CPU/памяти и выбор установленных Windows-шрифтов | Кроссплатформенная эмуляция устройств |
| WebRTC и автоматизация | Нативная маршрутизация и политики отдельных automation/headless/CDP-сигналов | Внешние проверки утечек; **полной невидимости CDP нет** |
| Доставка в workers/document | Worker opt-in transport; четыре Blink handoff-теста прошли; document-черновики | Document runtime/recovery и production admission |
| Canvas / GPU / Audio | Canvas-кандидаты; штатное поведение GPU/audio | **Защита не завершена и не включена** |
| TLS / HTTP | Штатный Chromium/BoringSSL | Измерения на одинаковом маршруте; подмены ClientHello нет |
| Mobile и платформы | Viewport/touch Web Emulation; проверенный Windows runtime в разработке | Не настоящий Android/iOS; проверки Linux/macOS отложены |

[Публичные патчи](native/patches) · [Архитектура](native/ARCHITECTURE.md) ·
[Возможности](docs/NATIVE_ENGINE.md) · [План](docs/GLINT_ROADMAP.ru.md)

### Glint: результаты, не обещания

**Windows · Chromium 148.0.7778.96 · патчи 001–027** — закреплённая
экспериментальная база, не production-релиз и не заявление об актуальности обновлений безопасности.

| Проверка | Зафиксированный результат |
| --- | --- |
| Существующие runtime-политики | **160 проверок прошли в 8 локальных gates** |
| Запуск / перезапуск / отклонение workers | **40 проверок прошли**, диагностический opt-in |
| Blink seed ownership / thread handoff | **4 cases прошли**, с test-only исправлением fixture 0028 |
| Canvas API без защиты | **4 фазы прошли** — не доказательство защиты |
| Внешние fingerprint/bot-сервисы | **Не запускались для 001–027** |
| reCAPTCHA / Turnstile с реальными ключами / hCaptcha | **Не подтверждены для 001–027** |

[Полная матрица и история сборок](docs/GLINT_TEST_MATRIX.md): CreepJS, Pixelscan,
BrowserScan, Sannysoft, BrowserLeaks, Fingerprint Playground, TLS/HTTP и другие.
Результаты прошлых сборок не переносятся. Баллы CAPTCHA и доступ к сайтам не гарантируются.

## Начать работу

**[Скачать Windows-приложение](https://github.com/Tort1k558/Camouflow/releases/latest)** →
распаковать → запустить `CamouFlow.exe`. Движки загружаются при первом запуске.
Локальный режим не требует входа на сервер.

<details>
<summary>Запуск из исходников · Windows, Python 3.12</summary>

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Сборка приложения: `build.bat`.
Результат: `dist\<build-id>\CamouFlow\CamouFlow.exe`.
Для Glint есть отдельная [инструкция сборки Chromium](native/BUILDING.md).

</details>

## Подробнее

[Справочник приложения](docs/DESKTOP_REFERENCE.ru.md) ·
[Облачные задачи](docs-site/docs/hosted-tasks.md) ·
[Командный центр](docs-site/docs/team-center.md) ·
[Python-сценарии](docs-site/docs/python-scripting.md) ·
[API](https://camouflow.site/api) · [Изменения](CHANGELOG.md)

<details>
<summary>Управление прокси и обзор рабочего пространства</summary>

| Пулы прокси | Обзор |
| :---: | :---: |
| ![Пулы прокси и проверки здоровья](images/proxies.png) | ![Обзор рабочего пространства](images/dashboard.png) |

</details>

**Local-first, не sandbox:** профили и данные хранятся локально; облачные функции
и выбранные AI-провайдеры имеют отдельные потоки данных. Архивы, traces и файлы
сессий храните приватно. Опциональный сервер не входит в этот репозиторий.

[Участие в разработке](CONTRIBUTING.ru.md) · [Сообщить о баге](https://github.com/Tort1k558/Camouflow/issues/new/choose) ·
[Правила сообщества](CODE_OF_CONDUCT.md) · [Безопасность](SECURITY.md) · [Лицензия MIT](LICENSE)
