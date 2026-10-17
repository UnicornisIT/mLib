# Выпуск релиза mLib

Инструкция описывает выпуск Windows Desktop-версии mLib (`vX.Y.Z[-alpha]`). Она сверена с
`.github/workflows/windows-desktop.yml`, `.github/workflows/ci.yml` и `scripts/check_release.py`.
Если вы меняете workflow, обновите этот файл в том же pull request.

## 1. Главное правило

**Опубликованный тег не переиздаётся.** Тег, однажды отправленный в `origin`, не удаляют, не переносят
на другой коммит и не пушат повторно. Любое исправление — даже если сборка упала и Release не появился —
выходит следующей версией (`0.0.4-alpha` → `0.0.5-alpha`).

Почему так строго: у одной версии не должно существовать двух разных сборок. electron-updater сравнивает
только номера версий, поэтому пользователь со «старой» сборкой той же версии никогда не получит
исправленную, а опубликованные SHA-256 перестанут совпадать с уже скачанными файлами.

Как это обеспечено:

- workflow падает, если Release для тега уже существует, и проверяет это ещё раз непосредственно перед
  публикацией; `--clobber` и редактирование существующих Releases из workflow убраны;
- в настройках репозитория должен быть включён ruleset для тегов `v*`, запрещающий удаление и
  перемещение (`Settings → Rules → Rulesets → New tag ruleset`: target `v*`, включить *Restrict deletions*
  и *Block force pushes*, *Restrict updates*). Workflow не может обнаружить удалённый Release, поэтому
  без ruleset правило держится только на дисциплине.

Чтобы не «сжигать» номера версий, всегда делайте пробную сборку (раздел 4, шаг 6) до тега.

## 2. Как устроен релиз

Релиз — это git-тег `v<версия>`, отправленный в `origin`. Workflow **Windows Desktop** выполняет jobs
последовательно:

| Job | Runner | Что делает | Права токена |
| --- | --- | --- | --- |
| `verify` | ubuntu | `scripts/check_release.py --tag`: все источники версии совпадают с тегом, есть release notes; Release для тега ещё не существует | `contents: read` |
| `ci` | ubuntu | полный `ci.yml`: ruff, pytest, typecheck, lint, Next.js build, Playwright E2E, Docker build | `contents: read` |
| `installer` | windows | `scripts/build-windows.ps1` (повторно гоняет тесты, собирает backend, frontend и NSIS), загружает artifact | `contents: read` |
| `publish` | ubuntu | скачивает artifact, проверяет имя установщика против тега, ещё раз проверяет отсутствие Release, выполняет `gh release create --verify-tag` | `contents: write` |

Release содержит четыре файла (плюс два архива исходников, которые GitHub добавляет сам):

- `mLib-Setup-<версия>-x64.exe`;
- `mLib-Setup-<версия>-x64.exe.sha256`;
- `mLib-Setup-<версия>-x64.exe.blockmap`;
- `latest.yml` — метаданные electron-updater с SHA-512.

Тег с суффиксом (`-alpha`) публикуется как **pre-release**. Текст Release берётся из
`.github/release-notes/<тег>.md`; без этого файла `verify` падает.

Ручной запуск (`Actions → Windows Desktop → Run workflow`) проходит `verify`, `ci` и `installer`,
создаёт artifact на 14 дней и **ничего не публикует**: job `publish` выполняется только для события
`push` тега. Секреты подписи в ручной запуск не передаются, поэтому пробная сборка неподписанная.

Во всех jobs `actions/checkout` работает с `persist-credentials: false`, а сторонние Actions закреплены
по SHA коммита. При обновлении Action меняйте SHA и комментарий с версией вместе.

Установленное приложение проверяет Releases через 15 секунд после запуска и затем каждые 6 часов.
Alpha-сборка видит новые prerelease, стабильная — только стабильные выпуски. Скачивание и установка
начинаются только после действий пользователя.

Отдельного релизного процесса для Docker/server-версии нет: образы в реестр не публикуются,
server-пользователи обновляются через `git pull` и `docker compose up -d --build`.

## 3. Версионирование

Semantic Versioning, сейчас схема `0.0.N-alpha`. Версия хранится в **пяти** файлах:

| Файл | Поле |
| --- | --- |
| `backend/app/core/config.py` | `app_version` |
| `frontend/package.json` | `version` |
| `desktop/package.json` | `version` |
| `desktop/frontend-runtime/package.json` | `version` |
| `desktop/package-lock.json` | `version` и `packages[""].version` |

Дополнительно для каждой версии нужны:

- `.github/release-notes/v<версия>.md` — текст GitHub Release (обязателен);
- запись в `frontend/src/lib/releaseNotes.ts` — окно «Что нового» после обновления (если записи нет,
  окно просто не показывается);
- раздел в `CHANGELOG.md`.

Проверка согласованности (её же выполняют CI и `verify`):

```bash
python scripts/check_release.py
python scripts/check_release.py --tag v0.0.4-alpha
```

`appId` в NSIS не меняется, поэтому новая версия ставится поверх старой, а данные в `%LOCALAPPDATA%\mLib`
сохраняются.

## 4. Чек-лист перед тегом

1. Изменения слиты в `main`, CI на `main` зелёный, рабочее дерево чистое (`git status`).
2. Версия обновлена во всех пяти файлах, добавлены release notes, запись «Что нового» и раздел
   `CHANGELOG.md`; `python scripts/check_release.py --tag v<версия>` проходит.
3. Упоминания имени установщика в `README.md`, `docs/WINDOWS_DESKTOP_BUILD.md` и
   `docs/WINDOWS_DESKTOP_USER.md` обновлены.
4. Если есть новые Alembic-миграции, они проверены на копии реальной библиотеки. Перед миграцией desktop
   создаёт `backups/auto-before-migration-*.zip` — **только базы данных, без медиа** — и при ошибке
   откатывает базы из этой копии. Хранятся последние 7 таких копий.
5. Локальные проверки:

   ```bash
   cd backend
   python -m pytest
   ruff check app tests desktop_backend.py

   cd ../frontend
   pnpm typecheck
   pnpm lint
   pnpm build
   pnpm test:e2e
   ```

6. Пробная сборка: `Actions → Windows Desktop → Run workflow` на `main` и скачать artifact, либо локально
   на Windows 11 x64 (Python 3.12, Node.js 22+ с Corepack):

   ```powershell
   .\scripts\build-windows.ps1              # с тестами
   .\scripts\build-windows.ps1 -SkipTests   # повторная сборка без тестов
   $env:MLIB_PYTHON = "C:\Python312\python.exe"   # если Python несколько
   ```

   Результат: `dist\mLib-Setup-<версия>-x64.exe`.
7. Ручная проверка установщика на чистой Windows 11 x64 VM без Python, Node, Git и IDE:
   1. установить EXE;
   2. создать пользователя и несколько записей с media, включая загрузку трека, книги и видео;
   3. перезапустить приложение, проверить сохранность данных;
   4. выполнить Export, Backup, Import и Restore (через интерфейс, а не только тестами);
   5. установить новую версию поверх старой; при наличии миграций убедиться, что показывается окно
      запуска и приложение стартует;
   6. проверить автообновление с Release большей версии (предложение → скачивание → перезапуск);
   7. удалить приложение, убедиться, что `%LOCALAPPDATA%\mLib` остался; установить повторно;
   8. проверить русский Unicode и масштабирование Windows 100/125/150/200%;
   9. убедиться, что после закрытия не остаётся процессов `mLib.exe` и `mlib-backend.exe`.

## 5. Выпуск

```bash
git switch main
git pull --ff-only
python scripts/check_release.py --tag v0.0.4-alpha
git tag -a v0.0.4-alpha -m "mLib 0.0.4-alpha"
git push origin v0.0.4-alpha
```

Дальше:

1. `Actions → Windows Desktop`: дождитесь зелёного прогона всех четырёх jobs.
2. `Releases`: появился pre-release с четырьмя файлами и текстом из `.github/release-notes/`.
3. Скачайте EXE и сверьте SHA-256 с опубликованной суммой.
4. На машине со старой версией убедитесь, что приложение предлагает обновление.

## 6. Подпись установщика

Подписывается только сборка из тега: секреты `CSC_LINK` и `CSC_KEY_PASSWORD`
(`Settings → Secrets and variables → Actions`) передаются в job `installer` лишь при `push` тега.
Без них EXE публикуется **неподписанным**, и Windows SmartScreen показывает предупреждение о неизвестном
издателе. Сертификат не хранить в репозитории, самоподписанный не использовать.

Ограничение текущей конфигурации: в `desktop/package.json` стоит `signAndEditExecutable: false`, поэтому
даже при наличии сертификата `mLib.exe` внутри установщика, вероятно, остаётся неподписанным.
После настройки сертификата проверьте `signtool verify /pa` для установщика и для установленных
`mLib.exe` и `mlib-backend.exe`.

Публикация использует встроенный `GITHUB_TOKEN`, отдельный токен не нужен. Репозиторий и Releases должны
быть публичными: токен приватного репозитория в приложение встраивать нельзя.

## 7. Если что-то пошло не так

| Ситуация | Действие |
| --- | --- |
| `verify` упал до сборки (версия, release notes, Release уже есть) | Тег уже опубликован. Исправьте причину в `main` и выпустите следующую версию |
| `ci`, `installer` или `publish` упали, Release не создан | То же: следующая версия. Тег не удалять и не переносить |
| Release создан, но сломан | Не удаляйте и не меняйте его. Выпустите следующую версию с исправлением; в описании сломанного Release можно вручную добавить предупреждение |

## 8. Прочие правила

- Первый installer с updater каждый пользователь ставит вручную; последующие обновления приходят сами.
- Не добавляйте в коммиты `.env`, базы, media, токены, логи и generated output.
- В сообщениях коммитов и описаниях PR не добавляйте строки `Co-Authored-By` и упоминания Claude.
  Это относится и к коммиту с обновлением версии, и к любым правкам при подготовке релиза.
