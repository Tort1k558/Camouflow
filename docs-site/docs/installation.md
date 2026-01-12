---
order: 90
---
# Установка и запуск

## Требования

- Windows
- Python (рекомендуется использовать `.venv`)

## Запуск приложения

1. Создайте виртуальное окружение и активируйте его.
2. Установите зависимости проекта.
3. Запустите `main.py`.

Пример (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requiremensts
python main.py
```

## Документация (Retype)

Требуется Node.js (LTS) и npm.

Установка Retype:

```powershell
cd docs-site
npm install retypeapp --save-dev
```

Локальный просмотр:

```powershell
cd docs-site
npx retype watch
```

Сборка статического сайта:

```powershell
cd docs-site
npx retype build
```

Конфигурация Retype лежит в `docs-site/retype.yml`. По умолчанию входные файлы в `docs-site/docs/`, сборка идёт в `docs-site/site/`.
