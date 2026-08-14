FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic_core ./alembic_core
COPY alembic_music ./alembic_music
COPY alembic_movie ./alembic_movie
COPY alembic_books ./alembic_books
COPY alembic_collections ./alembic_collections
COPY alembic_games ./alembic_games
COPY alembic_wishes ./alembic_wishes
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/mlib-entrypoint
RUN chmod +x /usr/local/bin/mlib-entrypoint

EXPOSE 8000
ENTRYPOINT ["mlib-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
