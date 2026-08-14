# Release readiness: mLib 0.1.0

Дата проверки: 2026-08-14.

## Итог

**NOT READY FOR PUBLIC RELEASE** до выполнения двух обязательных проверок:

1. выполнить чистый Docker Compose-прогон с перезапуском, пересборкой и проверкой сохранности данных на машине с Docker;
2. восстановить/инициализировать Git-репозиторий, проверить историю на секреты и выполнить добавленный GitHub Actions workflow.

Лицензия MIT добавлена. Код, локальная production-сборка, зависимости, миграции SQLite и основной пользовательский браузерный сценарий прошли проверку.

## A. Найдено и исправлено

- Исправлен upload трека с album metadata: служебные признаки filename/fallback больше не передаются модели альбома и сохраняются в модели трека.
- В backend Docker image добавлены отсутствовавшие миграции Collections, Games и Wishes.
- Production-режим отклоняет короткий или шаблонный `SECRET_KEY`.
- Уязвимые Python- и frontend-зависимости обновлены; lock-файл воспроизводим.
- Удалены native `alert`, `confirm` и `prompt`; добавлены единые доступные диалоги и toast-уведомления.
- Исправлена связь label/input в редакторе трека, добавлены 404/error pages и один корректный `main` landmark на страницу.
- Исправлены мобильные переполнения общей service-grid оболочки и hero-графики bookLib.
- E2E переведён на production-сборку с чистыми временными БД и гарантированной остановкой собственных процессов.
- README синхронизирован с семью доменами БД, Docker, PostgreSQL, обновлением и резервным копированием.
- Добавлены CI, issue/PR templates, changelog, contribution и security policy.

## B. Тесты и аудиты

| Проверка | Статус | Результат |
|---|---|---|
| Backend pytest | PASS | 73/73 |
| Ruff | PASS | backend, tests и E2E helpers |
| TypeScript | PASS | `tsc --noEmit` |
| ESLint | PASS | без ошибок |
| Next.js production build | PASS | 24 маршрута |
| Browser E2E | PASS | 3 целевых теста, 3 исключённые зеркальные комбинации |
| Python dependency audit | PASS | известных уязвимостей нет |
| Frontend dependency audit | PASS | известных уязвимостей нет |
| Dependency consistency | PASS | `pip check`, frozen pnpm install |
| YAML | PASS | Compose, workflow и issue templates |
| Candidate-file secret scan | PASS | credential-shaped значений и приватных абсолютных путей не найдено |
| Docker build/up/restart | NOT TESTED | Docker CLI отсутствует |
| PostgreSQL runtime | NOT TESTED | Docker/PostgreSQL недоступны |
| Git tracked/history scan | NOT TESTED | каталог `.git` отсутствует |
| GitHub Actions run | NOT TESTED | репозиторий не подключён к GitHub |

## C. Browser E2E

Проверены:

- первый запуск и создание администратора;
- загрузка WAV с ID3-тегами и embedded artwork;
- отображение title/artist/album artwork;
- запуск, пауза и seek;
- добавление в избранное;
- создание плейлиста и добавление трека;
- редактирование метаданных, поиск и refresh;
- выход, неверный пароль, повторный вход;
- сохранность изменённого трека и плейлиста между сессиями;
- отсутствие неожиданных console/page errors;
- ключевые маршруты `/`, `/music`, `/movie`, `/books`, `/collections`, `/games`, `/wishes` на desktop/tablet/mobile;
- главная страница на 1920×1080, 1440×900, 1280×720, 1024×768, 768×1024, 414×896, 390×844, 375×812 и 360×800.

CRUD остальных доменов покрыт backend integration tests. Полные CRUD-пути каждого домена через UI не автоматизированы и рекомендуются как ручной acceptance-прогон перед первым публичным тегом.

## D. Безопасность и публичный состав

- `.env`, базы, media, uploads/import, логи, кэши, Playwright output, `.next`, `node_modules` и virtualenv исключены из Git.
- Проект распространяется по лицензии MIT; полный текст находится в `LICENSE`.
- Docker contexts исключают локальные данные, тесты и generated output.
- Production-секрет обязан быть случайным и не короче 32 символов.
- Пароли хешируются Argon2; смена пароля проверяет текущий пароль, применяет policy, ограничивает неудачные попытки и отзывает старые сессии.
- Cookie, CORS, upload limit и TMDB token управляются окружением.
- Локальные `.env`/БД/media не удалялись и не изменялись тестами.
- Полный аудит Git-истории невозможен без `.git`.

## E. Запуск

Основной путь описан в `README.md`:

```bash
cp .env.example .env
# заменить SECRET_KEY уникальным случайным значением
docker compose up -d --build
```

Приложение должно открываться на `http://localhost:3000`; backend имеет healthcheck `/health`. Для PostgreSQL используется overlay `docker-compose.postgres.yml` и семь отдельных доменных БД.

## F. Что нельзя утверждать

- Нельзя утверждать, что clean Docker install, restart, rebuild, volume persistence и PostgreSQL прошли: Docker отсутствует в среде проверки.
- Нельзя утверждать, что `.gitignore` защищает уже отслеживаемые файлы или что история не содержит секретов: Git metadata отсутствует.
- Нельзя утверждать, что CI зелёный на GitHub: workflow проверен статически и локальными эквивалентами, но не запускался на runner.

## G. Перед публикацией

1. На чистой машине выполнить SQLite и PostgreSQL Docker Compose сценарии: setup → CRUD/media → restart → rebuild → update → проверка данных.
2. Инициализировать или вернуть Git metadata; проверить `git status`, tracked ignored files и всю историю gitleaks/trufflehog-подобным инструментом.
3. Добавить реальный clone URL в README после создания remote.
4. Запустить GitHub Actions, исправить runner-specific проблемы, включить branch protection и Private Vulnerability Reporting.
5. Провести ручной UI CRUD acceptance для Movies, Books, Collections, Games и Wishes.
6. Только после этого создать тег `v0.1.0` и GitHub Release на основе `CHANGELOG.md`.
