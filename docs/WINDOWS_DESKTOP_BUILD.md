# Сборка mLib для Windows

## Архитектура

Desktop-версия переиспользует существующие части mLib:

```text
mLib.exe (Electron, без консоли)
├── Next.js standalone frontend (встроенный Node runtime Electron)
├── mlib-backend.exe (FastAPI sidecar, PyInstaller, без консоли)
└── %LOCALAPPDATA%\mLib
    ├── data\       SQLite
    ├── media\      пользовательские файлы
    ├── backups\    backup перед import/restore/migration
    ├── logs\       rotating logs
    ├── config\     secret и состояние окна
    └── temp\       временные файлы операций
```

Electron выбирает два свободных порта на `127.0.0.1`, запускает backend, ждёт `/health`, запускает Next.js и только после этого показывает окно. Порты не публикуются в LAN. При закрытии Electron запрашивает корректное завершение backend и принудительно завершает его только по таймауту.

Приложение использует `requestSingleInstanceLock`: повторный запуск активирует существующее окно. Размер, положение и maximized-состояние сохраняются в `config/window-state.json`.

## Почему Electron

Текущий frontend — Next.js 16 с динамическими маршрутами и production-режимом `standalone`. Electron позволяет использовать этот frontend и его Node runtime без переписывания интерфейса. Он также предоставляет зрелые BrowserWindow, IPC, single-instance API и NSIS installer.

- Tauri не устранил бы sidecar-процессы: Next.js SSR всё равно требует Node, FastAPI — Python. Дополнительно появились бы Rust toolchain и зависимость от WebView2.
- PyInstaller и Nuitka подходят для backend, но сами по себе не дают встроенное web-окно и installer lifecycle. PyInstaller выбран только для FastAPI sidecar.
- Чистый WebView2 wrapper потребовал бы самостоятельной реализации lifecycle, runtime bootstrapper, single-instance, IPC и installer.
- Переписывание backend на Node ради Electron нарушило бы требование минимального вмешательства и ухудшило бы совместимость будущего Linux/PostgreSQL-режима.

Цена этого решения — больший installer, так как Chromium входит в поставку. Для текущего SSR-стека это осознанный компромисс в пользу надёжности.

## База данных и migrations

Существующая архитектура разделяет данные на семь доменных баз:

```text
data\core.db
data\music.db
data\movie.db
data\books.db
data\collections.db
data\games.db
data\wishes.db
```

Это разделение сохранено, потому что оно уже поддерживает `SQLite → PostgreSQL` одной моделью SQLAlchemy и семью наборами Alembic migrations. В desktop включены:

- `PRAGMA foreign_keys=ON`;
- `PRAGMA journal_mode=WAL`;
- `PRAGMA synchronous=NORMAL`;
- `PRAGMA busy_timeout=10000`;
- транзакции SQLAlchemy.

На первом запуске sidecar автоматически применяет все migrations. При обнаружении новой migration существующей библиотеки сначала создаётся `backups/auto-before-migration-*.zip`. Хранятся последние семь автоматических копий. При ошибке migration исходные данные восстанавливаются из backup.

Для server-режима остаются переменные `CORE_DATABASE_URL`, `MUSIC_DATABASE_URL` и остальные URL. Они могут указывать на PostgreSQL; бизнес-модели, API и migrations общие.

## Media storage

Файлы находятся в `%LOCALAPPDATA%\mLib\media`. Таблицы хранят ключи вида `music/originals/ab/<uuid>.flac` или `collections/photos/...`, а не абсолютные Windows-пути. Поля `source_path` не переносятся, потому что это сведения о внешней исходной папке, а не часть библиотеки.

## Export и Import

Portable export имеет вид:

```text
manifest.json
database/data.json
metadata/entities.json
media/**
```

`database/data.json` содержит все таблицы, первичные ключи, ID, foreign keys, даты, JSON-поля и связи семи доменов. `manifest.json` содержит версии приложения/формата/schema, revisions migrations, количество сущностей и SHA-256/размер каждого файла. Operational-таблица незавершённых загрузок и машинно-зависимые пути не экспортируются.

Import выполняет следующие проверки: безопасные ZIP-пути, тип архива, `export_version`, `schema_version`, полный перечень файлов, размер, SHA-256, известные домены/таблицы/колонки, наличие media и foreign keys. До изменения данных создаётся точный safety backup. Таблицы загружаются в транзакциях; при любой ошибке восстанавливается safety backup.

Формат не является дампом SQLite и не зависит от SQL dialect. Поэтому тот же service layer можно вызвать при будущем импорте в PostgreSQL.

## Backup и Restore

Backup предназначен для этой desktop-установки и содержит согласованные snapshots семи SQLite-баз, media, локальное пользовательское состояние интерфейса и manifest с SHA-256. Restore проверяет архив, создаёт safety backup текущего состояния и только затем заменяет базы и media; параметры интерфейса применяются после успешного восстановления. Backup отличается от portable Export и не используется для переноса в PostgreSQL.

## Сборка installer

Требования только к build-машине:

- Windows 11 x64;
- Python 3.12;
- Node.js 22+ с Corepack;
- интернет для первой установки зависимостей.

Из корня репозитория:

```powershell
.\scripts\build-windows.ps1
```

Команда выполняет typecheck/lint/tests, собирает Next.js standalone, создаёт `mlib-backend.exe` через PyInstaller и выпускает NSIS installer через electron-builder. Для повторной локальной сборки без тестов:

```powershell
.\scripts\build-windows.ps1 -SkipTests
```

Если нужно явно выбрать Python:

```powershell
$env:MLIB_PYTHON = "C:\Python312\python.exe"
.\scripts\build-windows.ps1
```

Результат:

```text
dist\mLib-Setup-0.0.2-alpha-x64.exe
```

Установщик ставит GUI-приложение в стандартный Program Files, создаёт ярлыки меню «Пуск» и рабочего стола и регистрирует uninstall. `deleteAppDataOnUninstall=false`, поэтому `%LOCALAPPDATA%\mLib` не удаляется. Повторная установка находит старую библиотеку и применяет только недостающие migrations.

Локальная build-команда создаёт неподписанный installer. Для публичного релиза настройте Authenticode-сертификат через штатные переменные electron-builder (`CSC_LINK`/`CSC_KEY_PASSWORD`) в защищённых GitHub Secrets. Подпись настроена только на SHA-256 без устаревшего SHA-1 и получает RFC 3161 timestamp SHA-256 от DigiCert. Не добавляйте самописную подпись и не храните сертификат в репозитории. Без Authenticode Windows SmartScreen может показать предупреждение неизвестного издателя, хотя SHA-256 файла остаётся проверяемым.

`ffprobe` не является runtime-требованием desktop-версии: Mutagen обрабатывает музыку, а известные видеоформаты имеют безопасный fallback. Если в будущем понадобится расширенная диагностика кодеков, положите лицензированный `ffprobe.exe` в `desktop/build/tools` перед packaging; пользователь всё равно не должен устанавливать его отдельно.

Portable-вариант вторичен и собирается после подготовки основных bundle:

```powershell
cd desktop
npm run dist:portable
```

## Версии и новый выпуск

Перед выпуском синхронно измените:

- `backend/app/core/config.py` — `app_version`;
- `frontend/package.json` — `version`;
- `desktop/package.json` — `version`.

После этого запустите полную сборку. NSIS использует стабильный `appId`, поэтому новая версия обновляет приложение, не затрагивая `%LOCALAPPDATA%\mLib`.

Desktop использует официальный `electron-updater`. Сборка из GitHub получает адрес репозитория из `github.repository`; electron-builder встраивает `app-update.yml` и создаёт `latest.yml` с SHA-512. Приложение проверяет подходящие Releases через 15 секунд после запуска и затем каждые 6 часов. Предварительная сборка получает последующие prerelease-версии, а стабильная — только стабильные выпуски. Скачивание начинается только после нажатия пользователем, установка — после отдельного подтверждения перезапуска. Локальная сборка без `MLIB_GITHUB_REPOSITORY` безопасно отключает updater.

Workflow `.github/workflows/windows-desktop.yml` собирает тот же installer на Windows runner. Ручной запуск через `Actions → Windows Desktop → Run workflow` создаёт временный artifact для проверки, но не публикует релиз.

Чтобы автоматически создать публичный GitHub Release и прикрепить к нему EXE, SHA-256, blockmap и `latest.yml`, отправьте тег, совпадающий с версией в `desktop/package.json`:

```powershell
git tag v0.0.2-alpha
git push origin v0.0.2-alpha
```

После успешной сборки файлы появятся в разделе `Releases` репозитория. Тег с суффиксом, например `-alpha`, автоматически публикуется как prerelease. Повторный запуск workflow для того же тега заменяет вложения актуальной сборкой. Для следующего выпуска сначала синхронно обновите версии во всех трёх файлах, перечисленных выше, а затем используйте новый тег.

Репозиторий и Release должны быть публичными: в установленное приложение нельзя встраивать GitHub-токен от приватного репозитория. Updater отслеживает не произвольные коммиты, а готовые Releases. Это гарантирует, что пользователю предлагается версия с новым semver, собранным installer и проверяемыми хешами. Первый installer с updater нужно один раз скачать из Releases и установить вручную; все последующие выпуски он обнаружит сам.

Workflow использует встроенный `GITHUB_TOKEN`; отдельный персональный токен не нужен. Для подписанной сборки добавьте в `Settings → Secrets and variables → Actions` секреты `CSC_LINK` и `CSC_KEY_PASSWORD`. Без них EXE всё равно будет собран и опубликован, но останется неподписанным.

## Проверка на чистом ПК

Перед релизом обязательна отдельная Windows 11 x64 VM без Python, Node, Git и IDE:

1. установить `mLib-Setup-<version>-x64.exe`;
2. создать пользователя и несколько записей/media;
3. перезапустить приложение и проверить сохранность;
4. выполнить Export, Backup, Import и Restore;
5. установить следующую версию поверх текущей;
6. опубликовать тестовый Release с большей версией, проверить предложение в интерфейсе, скачивание и перезапуск;
7. удалить приложение, убедиться, что `%LOCALAPPDATA%\mLib` остался;
8. установить повторно и проверить библиотеку;
9. проверить русский Unicode и Windows scaling 100/125/150/200%;
10. проверить отсутствие оставшихся процессов после закрытия.
