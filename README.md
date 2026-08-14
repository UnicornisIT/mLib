# mLib

> **Статус:** подготовка первого публичного релиза `0.1.0`. Репозиторий ещё не публикуется автоматически.

mLib — локальная self-hosted медиаплатформа для музыки, фильмов и сериалов, книг, физических коллекций, игр и желаний. Наиболее проработанный домен — музыка: загрузка собственных файлов, автоматическое чтение тегов и обложек, каталог, поиск, потоковое воспроизведение, очередь, избранное и плейлисты.

Проект рассчитан на запуск на обычном ПК, в локальной сети и на VPS. Backend остаётся источником истины; frontend не знает физических путей к файлам.

## Что уже работает

- первоначальная настройка и создание администратора;
- вход, выход, Argon2-хеширование паролей и защищённая HttpOnly cookie-сессия;
- загрузка одного или нескольких файлов, Drag & Drop и прогресс по каждому файлу;
- MP3, FLAC, M4A, AAC, OGG, WAV и OPUS;
- импорт разрешённой серверной папки с прогрессом, повторным сканированием и пропуском известных файлов;
- SHA-256 + размер файла для защиты от дублей;
- нормализация ID3, FLAC/Vorbis и MP4-тегов через Mutagen, технические данные через Mutagen/ffprobe;
- извлечение embedded artwork и заранее созданные WebP-версии 512, 256 и 64 px;
- автоматическое разрешение исполнителей и альбомов без дублей регистра/пробелов;
- `Album Artist`, `Various Artists`, номер диска и сортировка multi-disc альбомов;
- пагинированные треки, альбомы, исполнители, жанры, поиск и главная страница;
- HTTP Range Requests (`206 Partial Content`) без загрузки файла целиком в память;
- постоянный плеер, очередь, Next/Previous, Shuffle, Repeat One/All, громкость и mute;
- пользовательские избранное и плейлисты, изменение порядка треков;
- редактирование тегов в БД и безопасное удаление физического файла;
- `movieLib`: каталог фильмов и сериалов, TMDB-поиск, локальные видеофайлы, прогресс просмотра, сезоны и эпизоды;
- `bookLib`: электронные и аудиокниги, обложки, загрузка файлов и чтение/выдача содержимого с авторизацией;
- `collectLib`: универсальные коллекции физических предметов с карточками, несколькими фотографиями и выбором обложки;
- настраиваемые поля коллекций, теги, местоположение предмета, поиск, фильтры и массовые операции;
- `gameLib`: игры, платформы, статусы прохождения, часы, оценки и достижения;
- `wishLib`: общая очередь желаний, приоритеты и отметки об автоматическом выполнении;
- тёмная, светлая и системная темы; адаптивный desktop/tablet/mobile UI;
- SQLite для локального запуска и PostgreSQL без изменения бизнес-логики;
- Alembic, Docker Compose, Nginx-конфигурация и automated tests.

## Архитектура

```text
mLib
├── backend/                      FastAPI, SQLAlchemy, Alembic
│   ├── app/core/                 конфигурация, безопасность
│   ├── app/auth/                 пользователи и сессии
│   ├── app/database/             engine, session, metadata
│   ├── app/settings/             настройки приложения
│   ├── app/storage/              файловое хранилище
│   └── app/modules/              независимые домены
│       ├── music/                музыка, метаданные, artwork и streaming
│       ├── movie/                фильмы, сериалы и прогресс просмотра
│       ├── books/                книги, обложки и файлы
│       ├── collections/          коллекции, поля и фотографии
│       ├── games/                игры и прогресс прохождения
│       └── wishes/               желания и автоматическое сопоставление
├── frontend/                     Next.js, React, TypeScript, Tailwind
│   └── src/
│       ├── app/                  маршруты интерфейса
│       ├── components/           плеер, таблицы, навигация, upload
│       ├── providers/            auth, theme, global player state
│       ├── hooks/                синхронизация библиотеки
│       └── lib/                  API-клиент, типы, форматирование
└── deploy/                       reverse proxy
```

Core не содержит понятий `Track`, `Artist` или `Album`. Музыка, фильмы, книги, коллекции, игры и желания реализованы соседними доменами в `app/modules` и `src/app`, используя общие auth/settings/storage.

Тяжёлые операции — hashing, Mutagen, ffprobe, обработка изображений и импорт — выполняются вне основного async event loop FastAPI. Текущий реестр задач импорта изолирован так, чтобы позднее заменить его durable worker без изменения REST-контракта.

## Схема данных

```mermaid
erDiagram
    USER ||--o{ FAVORITE : marks
    USER ||--o{ PLAYLIST : owns
    ARTIST ||--o{ TRACK : performs
    ARTIST ||--o{ ALBUM : album_artist
    ALBUM ||--o{ TRACK : contains
    ARTWORK ||--o{ TRACK : illustrates
    ARTWORK ||--o{ ALBUM : illustrates
    PLAYLIST ||--o{ PLAYLIST_TRACK : orders
    TRACK ||--o{ PLAYLIST_TRACK : included
    TRACK ||--o{ FAVORITE : favorited

    TRACK {
      uuid id PK
      string title
      uuid artist_id FK
      uuid album_id FK
      string file_hash UK
      string file_path
      float duration
      int disc_number
      int track_number
      int play_count
    }
    ALBUM {
      uuid id PK
      string normalized_title
      string normalized_album_artist
      uuid artwork_id FK
    }
    ARTIST {
      uuid id PK
      string name
      string normalized_name UK
    }
    PLAYLIST_TRACK {
      uuid id PK
      uuid playlist_id FK
      uuid track_id FK
      int position
    }
```

Физические файлы лежат независимо от отображаемых тегов:

```text
media/music/
├── originals/<uuid-prefix>/<track-uuid>.<ext>
├── artwork/<uuid-prefix>/<artwork-uuid>-{original,512,256,64}.webp
└── staging/
```

## REST API

Полная интерактивная документация доступна на `http://localhost:8000/docs` при локальном запуске backend.

| Область | Endpoints |
|---|---|
| Auth | `GET /api/auth/status`, `POST /setup`, `POST /login`, `POST /logout`, `GET /me` |
| Tracks | `GET /api/music/tracks`, `GET/PATCH/DELETE /tracks/{id}` |
| Playback | `GET /tracks/{id}/stream`, `POST /tracks/{id}/played` |
| Favorites | `POST/DELETE /tracks/{id}/favorite` |
| Artwork | `GET /api/music/artwork/{id}/{size}` |
| Upload/import | `POST /api/music/upload`, `POST /imports`, `GET /imports/{job_id}` |
| Books | `GET/POST /api/books`, `GET /books/dashboard`, `GET /books/{id}/cover`, `GET/DELETE /books/{id}`, `GET /books/{id}/content` |
| Collections | `GET/POST/PATCH/DELETE /api/collections`, `/collections/items`, `/collections/{id}/fields`, `/collections/items/bulk`, `/collections/items/{id}/photos` |
| Movies/TV | `/api/movie/dashboard`, `/titles`, `/catalog`, `/uploads`, `/files/{id}/stream`, tracking и episodes |
| Games | `GET/POST /api/games`, `GET /games/dashboard`, `GET/PATCH/DELETE /games/{id}` |
| Wishes | `GET/POST /api/wishes`, `GET /wishes/dashboard`, `GET/PATCH/DELETE /wishes/{id}` |
| Catalog | `GET /albums`, `/albums/{id}`, `/artists`, `/artists/{id}`, `/genres`, `/dashboard` |
| Search | `GET /api/music/search?q=...` |
| Playlists | `GET/POST /playlists`, `GET/PATCH/DELETE /playlists/{id}` |
| Playlist tracks | `POST /playlists/{id}/tracks`, `DELETE /tracks/{item_id}`, `PUT /tracks/reorder` |
| Settings | `GET/PATCH /api/settings` |
| System | `GET /health` |

Списки имеют пагинацию и ограниченный `page_size`; поля частого поиска и сортировки индексированы.

## Самый простой запуск через Docker

Нужны Docker Engine и Docker Compose v2.

1. Скопируйте `.env.example` в `.env`.
2. Замените `SECRET_KEY` уникальным случайным значением длиной не менее 32 символов. Пример генерации: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. При необходимости задайте `MUSIC_IMPORT_PATH` — папку хоста с уже существующей музыкой.
4. Запустите:

```bash
docker compose up -d --build
```

Откройте `http://localhost:3000`. На первом экране создайте администратора. В Docker разрешённая папка импорта — `/imports`.

SQLite и медиаданные находятся в persistent volume `mlib_data`; пересборка контейнеров их не удаляет.

Проверить состояние контейнеров можно командой `docker compose ps`; backend считается готовым после успешной проверки `/health`.

## Обновление и резервное копирование

Перед обновлением остановите запись новых данных и сохраните persistent volume. Для SQLite достаточно архивировать содержимое `mlib_data` (базы в `/data/db` и медиаданные в `/data/media`). Для PostgreSQL дополнительно сделайте `pg_dump` всех баз `mlib_*`. После резервного копирования получите новую версию проекта и выполните:

```bash
docker compose pull
docker compose up -d --build
```

Миграции выполняются автоматически при старте backend. Никогда не используйте `docker compose down -v` при обычном обновлении: ключ `-v` удаляет пользовательские данные.

## Локальный запуск для разработки

Требования: Python 3.12+, Node.js 22+, pnpm 11+, FFmpeg/ffprobe.

Backend:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
cd backend
alembic -n core upgrade head
alembic -n music upgrade head
alembic -n movie upgrade head
alembic -n books upgrade head
alembic -n collections upgrade head
alembic -n games upgrade head
alembic -n wishes upgrade head
uvicorn app.main:app --reload
```

## Независимые базы сервисов

mLib использует семь независимых подключений:

- `CORE_DATABASE_URL` — пользователи, единый вход и общие параметры размещения;
- `MUSIC_DATABASE_URL` — musicLib, плейлисты и музыкальные настройки;
- `MOVIE_DATABASE_URL` — movieLib, видео, прогресс просмотра и настройки TMDB.
- `BOOKS_DATABASE_URL` — bookLib, электронные и аудиокниги с ручными метаданными и обложками.
- `COLLECTIONS_DATABASE_URL` — collectLib, коллекции, предметы, фотографии, теги, местоположения и настраиваемые поля.
- `GAMES_DATABASE_URL` — gameLib, игры, платформы, статусы прохождения, часы, оценки и достижения.
- `WISHES_DATABASE_URL` — wishLib, общая очередь желаний и отметки об автоматическом выполнении.

При переходе со старой монолитной `mlib.db` выполните из папки `backend`:

```bash
python -m scripts.split_database
```

Команда создаёт датированную резервную копию исходной базы, переносит данные с сохранением UUID и проверяет количество строк во всех доменных таблицах. Исходная `DATABASE_URL` после разделения используется только как адрес старой базы для инструмента переноса.

Frontend в другом терминале:

```bash
cd frontend
cp .env.example .env.local
corepack enable
pnpm install
pnpm dev
```

Откройте `http://localhost:3000`. Backend и OpenAPI будут на `http://localhost:8000` и `/docs`.

## PostgreSQL

Для Docker-варианта задайте сильный `POSTGRES_PASSWORD` в `.env`, затем:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Alembic автоматически применит те же миграции к PostgreSQL. Для внешнего PostgreSQL задайте отдельный URL для каждого домена (`CORE_DATABASE_URL`, `MUSIC_DATABASE_URL`, `MOVIE_DATABASE_URL`, `BOOKS_DATABASE_URL`, `COLLECTIONS_DATABASE_URL`, `GAMES_DATABASE_URL`, `WISHES_DATABASE_URL`), например:

```text
CORE_DATABASE_URL=postgresql+psycopg://mlib:password@database:5432/mlib_core
```

## Production и VPS

1. Укажите production-домен в `CORS_ORIGINS`.
2. Включите `COOKIE_SECURE=true` и обслуживайте приложение только через HTTPS.
3. Используйте длинные отдельные значения `SECRET_KEY` и `POSTGRES_PASSWORD`.
4. Не публикуйте порт backend наружу; доступ к `/api` должен идти через reverse proxy.
5. Ограничьте права на volume медиатеки и регулярно резервируйте БД и `/data/media`.
6. Запустите PostgreSQL и профиль Nginx:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml --profile proxy up -d --build
```

`deploy/nginx.conf` передаёт Range-заголовки, отключает buffering для streaming и принимает загрузки до 1 ГБ. TLS обычно завершается на внешнем Nginx, Caddy, Traefik или у облачного балансировщика; при прямой публикации добавьте сертификаты в этот конфиг.

## Проверки

```bash
cd backend
python -m pytest
ruff check app tests

cd ../frontend
pnpm typecheck
pnpm lint
pnpm build
pnpm test:e2e:install
pnpm test:e2e
```

Тесты покрывают metadata normalization, duplicate detection, Range Requests, порядок плейлиста, CRUD и authentication.

E2E использует только временные базы и медиахранилище в `frontend/.e2e`; рабочие базы и пользовательские файлы не изменяются.

## Безопасность

- пользовательские имена файлов не участвуют в конечном пути;
- расширения проверяются по whitelist, а Mutagen подтверждает, что содержимое является аудио;
- upload ограничен по размеру и никогда не исполняется;
- все media/artwork endpoints требуют авторизацию;
- пути импорта ограничены настроенным корнем, а управляемые пути проверяются после `resolve()`;
- пароли хешируются Argon2, секреты не логируются;
- CORS, secure cookie и лимиты загрузки настраиваются окружением;
- streaming читает файл небольшими блоками.

## Следующие этапы и ограничения MVP

- MusicBrainz и Cover Art Archive представлены контрактом `MetadataProvider`, но сетевые провайдеры пока не подключены; встроенные теги не перезаписываются.
- Server-side transcoding ещё не реализован: воспроизведение формата зависит от поддержки браузера. FFmpeg уже входит в Docker-образ и используется для технического анализа.
- Задачи импорта хранят состояние в памяти процесса. После перезапуска сам каталог остаётся в БД, но история активной задачи теряется; следующий шаг — durable worker.
- Нет ReplayGain, lyrics, waveform, gapless/crossfade, offline PWA, Chromecast/AirPlay/DLNA и scrobbling.
- Модель готова к нескольким пользователям (избранное и плейлисты принадлежат пользователю), но UI управления пользователями пока отсутствует.
- Реализованы независимые домены Music, Movies/TV, Books, Collections, Games и Wishes; их данные и медиахранилища не смешиваются.
- Для следующего этапа collectLib оставлены учёт выданных предметов, расширенная статистика и импорт CSV.

Ключевые решения: UUID-пути защищают хранилище от переименований; SQLite/PostgreSQL разделены конфигурацией, а не бизнес-логикой; «Все треки» — индексированный запрос, а не дублирующий системный плейлист; artwork готовится при импорте, а не при каждом HTTP-запросе; внешние метаданные могут только заполнить отсутствующие поля.

## Участие в разработке

Порядок локального запуска, тестов и подготовки pull request описан в [CONTRIBUTING.md](CONTRIBUTING.md). Уязвимости следует сообщать приватно по инструкции из [SECURITY.md](SECURITY.md), не публикуя секреты или персональные данные в issue.

## Лицензия

Проект распространяется по лицензии [MIT](LICENSE). Разрешены использование, копирование, изменение и распространение при сохранении уведомления об авторских правах и текста лицензии.
