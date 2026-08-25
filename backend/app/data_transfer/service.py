from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import MetaData, Table, insert, select, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import Settings

# Importing the model registry ensures every table is present in Base.metadata.
from app.database import base as _model_registry  # noqa: F401
from app.database.session import (
    BooksBase,
    CollectionsBase,
    CoreBase,
    GamesBase,
    MovieBase,
    MusicBase,
    WishesBase,
    books_engine,
    collections_engine,
    core_engine,
    dispose_all_engines,
    games_engine,
    movie_engine,
    music_engine,
    wishes_engine,
)

EXPORT_VERSION = 1
SCHEMA_VERSION = 1
BACKUP_VERSION = 2
MAX_ARCHIVE_ENTRIES = 500_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024**4
MAX_CLIENT_STATE_BYTES = 4 * 1024**2
ENVIRONMENT_ROWS = {
    "core": {"core_settings": {"library_path"}},
    "music": {"music_settings": {"import_path"}},
}
TRANSIENT_TABLES = {"movie": {"movie_uploads"}}
MEDIA_COLUMNS = {
    "music": {
        "music_artwork": ("original_path", "path_512", "path_256", "path_64"),
        "music_tracks": ("file_path",),
    },
    "movie": {"movie_files": ("file_path",)},
    "books": {"books": ("file_path", "cover_path")},
    "collections": {"collection_item_photos": ("file_path", "thumbnail_path")},
}


class DataTransferError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Domain:
    name: str
    engine: Engine
    metadata: MetaData


DOMAINS = (
    Domain("core", core_engine, CoreBase.metadata),
    Domain("music", music_engine, MusicBase.metadata),
    Domain("movie", movie_engine, MovieBase.metadata),
    Domain("books", books_engine, BooksBase.metadata),
    Domain("collections", collections_engine, CollectionsBase.metadata),
    Domain("games", games_engine, GamesBase.metadata),
    Domain("wishes", wishes_engine, WishesBase.metadata),
)
DOMAIN_MAP = {domain.name: domain for domain in DOMAINS}
_operation_lock = threading.RLock()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$mlib_type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$mlib_type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$mlib_type": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {"$mlib_type": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        marker = value.get("$mlib_type")
        raw = value.get("value")
        if marker == "datetime" and isinstance(raw, str):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if marker == "date" and isinstance(raw, str):
            return date.fromisoformat(raw)
        if marker == "decimal" and isinstance(raw, str):
            return Decimal(raw)
        if marker == "bytes" and isinstance(raw, str):
            return base64.b64decode(raw)
        return {key: _decode(item) for key, item in value.items()}
    return value


def _portable_path(value: Any, settings: Settings) -> Any:
    if not isinstance(value, str) or not value:
        return value
    candidate = Path(value)
    if not candidate.is_absolute():
        normalized = PurePosixPath(value.replace("\\", "/"))
        if ".." in normalized.parts:
            raise DataTransferError(f"Недопустимый media-ключ: {value}")
        return normalized.as_posix()
    try:
        return candidate.resolve().relative_to(settings.media_root.resolve()).as_posix()
    except ValueError as exc:
        raise DataTransferError("В базе найден абсолютный путь за пределами media-хранилища") from exc


def _table_payload(connection: Connection, domain: Domain, table: Table, settings: Settings) -> dict[str, Any]:
    environment_keys = ENVIRONMENT_ROWS.get(domain.name, {}).get(table.name, set())
    path_columns = MEDIA_COLUMNS.get(domain.name, {}).get(table.name, ())
    rows: list[dict[str, Any]] = []
    for record in connection.execute(select(table)).mappings():
        row = dict(record)
        if environment_keys and row.get("key") in environment_keys:
            continue
        for column in path_columns:
            row[column] = _portable_path(row.get(column), settings)
        if "source_path" in row:
            row["source_path"] = None
        rows.append({key: _encode(value) for key, value in row.items()})
    return {
        "name": table.name,
        "columns": [column.name for column in table.columns],
        "primary_key": [column.name for column in table.primary_key.columns],
        "rows": rows,
    }


def _database_payload(settings: Settings) -> tuple[dict[str, Any], dict[str, int]]:
    payload: dict[str, Any] = {"format": "mlib-portable-json", "domains": {}}
    counts: dict[str, int] = {}
    for domain in DOMAINS:
        tables = []
        with domain.engine.connect() as connection:
            for table in domain.metadata.sorted_tables:
                if table.name in TRANSIENT_TABLES.get(domain.name, set()):
                    continue
                table_payload = _table_payload(connection, domain, table, settings)
                tables.append(table_payload)
                counts[f"{domain.name}.{table.name}"] = len(table_payload["rows"])
        payload["domains"][domain.name] = {"tables": tables}
    return payload, counts


def _schema_heads() -> dict[str, str | None]:
    heads: dict[str, str | None] = {}
    for domain in DOMAINS:
        try:
            with domain.engine.connect() as connection:
                heads[domain.name] = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            heads[domain.name] = None
    return heads


def _inventory(root: Path, *, exclude: set[str] | None = None) -> dict[str, dict[str, Any]]:
    omitted = exclude or set()
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in omitted:
            continue
        inventory[relative] = {"sha256": _hash_file(path), "size": path.stat().st_size}
    return inventory


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_client_state(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"version", "theme", "player"}:
        raise DataTransferError("Повреждены пользовательские настройки в резервной копии")
    if value.get("version") != 1 or value.get("theme") not in {"dark", "light", "system"}:
        raise DataTransferError("Версия пользовательских настроек не поддерживается")
    player = value.get("player")
    if player is not None:
        if not isinstance(player, dict):
            raise DataTransferError("Повреждено состояние проигрывателя")
        queue = player.get("queue")
        if queue is not None and (not isinstance(queue, list) or len(queue) > 500):
            raise DataTransferError("Повреждена очередь проигрывателя")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DataTransferError("Пользовательские настройки содержат недопустимые данные") from exc
    if len(encoded) > MAX_CLIENT_STATE_BYTES:
        raise DataTransferError("Пользовательские настройки превышают допустимый размер")
    return json.loads(encoded)


def _zip_tree(root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    try:
        with zipfile.ZipFile(partial, "w", allowZip64=True) as archive:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                relative = path.relative_to(root).as_posix()
                compression = zipfile.ZIP_STORED if relative.startswith("media/") else zipfile.ZIP_DEFLATED
                archive.write(path, relative, compress_type=compression)
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)


def _copy_media(source: Path, destination: Path) -> None:
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.mkdir(parents=True, exist_ok=True)


def create_portable_export(destination: Path, settings: Settings) -> Path:
    destination = destination.expanduser().resolve()
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    with _operation_lock, tempfile.TemporaryDirectory(prefix="mlib-export-", dir=settings.temp_root) as raw:
        root = Path(raw)
        database, counts = _database_payload(settings)
        _write_json(root / "database" / "data.json", database)
        _write_json(root / "metadata" / "entities.json", {"entity_counts": counts})
        _copy_media(settings.media_root, root / "media")
        inventory = _inventory(root)
        manifest = {
            "application": "mLib",
            "archive_type": "export",
            "export_version": EXPORT_VERSION,
            "application_version": settings.app_version,
            "schema_version": SCHEMA_VERSION,
            "database_schema_heads": _schema_heads(),
            "created_at": _utc_now(),
            "source": f"{settings.app_mode}-{os.name}",
            "source_database": "sqlite" if all(d.engine.dialect.name == "sqlite" for d in DOMAINS) else "sql",
            "export_id": str(uuid.uuid4()),
            "entity_counts": counts,
            "media_files": sum(1 for key in inventory if key.startswith("media/")),
            "files": inventory,
        }
        _write_json(root / "manifest.json", manifest)
        _zip_tree(root, destination)
    return destination


def _database_file(domain: Domain) -> Path:
    if domain.engine.dialect.name != "sqlite" or not domain.engine.url.database:
        raise DataTransferError("Точная резервная копия доступна только для локальной SQLite-версии")
    return Path(domain.engine.url.database).resolve()


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        raise DataTransferError(f"Не найдена база данных {source.name}")
    with closing(sqlite3.connect(source)) as incoming, closing(sqlite3.connect(destination)) as outgoing:
        incoming.execute("PRAGMA busy_timeout=10000")
        incoming.backup(outgoing)
        outgoing.commit()


def _default_backup_path(settings: Settings, prefix: str = "mLib-backup") -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return settings.backups_root / f"{prefix}-{timestamp}.zip"


def create_backup(
    destination: Path | None,
    settings: Settings,
    *,
    reason: str = "manual",
    client_state: dict[str, Any] | None = None,
) -> Path:
    destination = (destination or _default_backup_path(settings)).expanduser().resolve()
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    settings.backups_root.mkdir(parents=True, exist_ok=True)
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    with _operation_lock, tempfile.TemporaryDirectory(prefix="mlib-backup-", dir=settings.temp_root) as raw:
        root = Path(raw)
        normalized_client_state = _normalize_client_state(client_state)
        for domain in DOMAINS:
            _sqlite_snapshot(_database_file(domain), root / "database" / f"{domain.name}.db")
        _copy_media(settings.media_root, root / "media")
        if normalized_client_state is not None:
            _write_json(root / "settings" / "client.json", normalized_client_state)
        inventory = _inventory(root)
        manifest = {
            "application": "mLib",
            "archive_type": "backup",
            "backup_version": BACKUP_VERSION,
            "application_version": settings.app_version,
            "schema_version": SCHEMA_VERSION,
            "database_schema_heads": _schema_heads(),
            "created_at": _utc_now(),
            "reason": reason,
            "client_state": normalized_client_state is not None,
            "files": inventory,
        }
        _write_json(root / "manifest.json", manifest)
        _zip_tree(root, destination)
    return destination


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_ENTRIES:
        raise DataTransferError("Архив содержит слишком много файлов")
    total = sum(member.file_size for member in members)
    if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise DataTransferError("Архив превышает допустимый размер")
    seen: set[str] = set()
    for member in members:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise DataTransferError("Архив содержит небезопасный путь")
        normalized = path.as_posix()
        if normalized in seen:
            raise DataTransferError("Архив содержит повторяющиеся пути")
        seen.add(normalized)
    return members


def _extract_and_verify(source: Path, destination: Path, expected_type: str) -> dict[str, Any]:
    if not source.is_file():
        raise DataTransferError("Выбранный архив не найден")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            members = _safe_members(archive)
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise DataTransferError("manifest.json отсутствует или повреждён") from exc
            if manifest.get("application") != "mLib" or manifest.get("archive_type") != expected_type:
                raise DataTransferError("Выбран архив другого типа или приложения")
            if expected_type == "backup":
                backup_version = manifest.get("backup_version")
                if not isinstance(backup_version, int) or backup_version not in {1, BACKUP_VERSION}:
                    raise DataTransferError("Версия резервной копии не поддерживается")
                schema_version = manifest.get("schema_version")
                if not isinstance(schema_version, int) or schema_version > SCHEMA_VERSION:
                    raise DataTransferError("Резервная копия создана более новой несовместимой версией mLib")
            archive.extractall(destination, members=members)
    except zipfile.BadZipFile as exc:
        raise DataTransferError("Файл не является корректным ZIP-архивом") from exc
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise DataTransferError("В manifest отсутствует перечень файлов")
    actual_names = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_names != set(files):
        raise DataTransferError("Состав архива не совпадает с manifest")
    for relative, expected in files.items():
        path = destination / PurePosixPath(relative)
        if not isinstance(expected, dict) or expected.get("size") != path.stat().st_size:
            raise DataTransferError(f"Нарушен размер файла {relative}")
        if expected.get("sha256") != _hash_file(path):
            raise DataTransferError(f"Нарушена контрольная сумма файла {relative}")
    return manifest


def _replace_media(incoming: Path, settings: Settings) -> None:
    target = settings.media_root.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    rollback = target.with_name(f".{target.name}.rollback-{uuid.uuid4().hex}")
    if target.exists():
        os.replace(target, rollback)
    try:
        if incoming.exists():
            shutil.copytree(incoming, target)
        else:
            target.mkdir(parents=True)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        if rollback.exists():
            os.replace(rollback, target)
        raise
    shutil.rmtree(rollback, ignore_errors=True)


def _restore_backup_extracted(root: Path, settings: Settings) -> None:
    dispose_all_engines()
    staged: list[tuple[Path, Path]] = []
    for domain in DOMAINS:
        incoming = root / "database" / f"{domain.name}.db"
        if not incoming.is_file():
            raise DataTransferError(f"В backup отсутствует {domain.name}.db")
        target = _database_file(domain)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.restoring")
        shutil.copy2(incoming, temporary)
        staged.append((temporary, target))
    for temporary, target in staged:
        os.replace(temporary, target)
        target.with_name(f"{target.name}-wal").unlink(missing_ok=True)
        target.with_name(f"{target.name}-shm").unlink(missing_ok=True)
    _replace_media(root / "media", settings)


def _read_client_state(root: Path) -> dict[str, Any] | None:
    path = root / "settings" / "client.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataTransferError("Повреждены пользовательские настройки в резервной копии") from exc
    return _normalize_client_state(value)


def _restore_backup(
    source: Path,
    settings: Settings,
    *,
    make_safety_backup: bool,
) -> tuple[Path, Path | None, dict[str, Any] | None]:
    source = source.expanduser().resolve()
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    with _operation_lock, tempfile.TemporaryDirectory(prefix="mlib-restore-", dir=settings.temp_root) as raw:
        root = Path(raw)
        _extract_and_verify(source, root, "backup")
        client_state = _read_client_state(root)
        safety = create_backup(None, settings, reason="before-restore") if make_safety_backup else None
        try:
            _restore_backup_extracted(root, settings)
        except Exception:
            if safety:
                restore_backup(safety, settings, make_safety_backup=False)
            raise
    return source, safety, client_state


def restore_backup(source: Path, settings: Settings, *, make_safety_backup: bool = True) -> tuple[Path, Path | None]:
    restored, safety, _ = _restore_backup(source, settings, make_safety_backup=make_safety_backup)
    return restored, safety


def restore_backup_with_client_state(
    source: Path,
    settings: Settings,
    *,
    make_safety_backup: bool = True,
) -> tuple[Path, Path | None, dict[str, Any] | None]:
    return _restore_backup(source, settings, make_safety_backup=make_safety_backup)


def _validate_export_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("export_version") != EXPORT_VERSION:
        raise DataTransferError("Версия формата экспорта не поддерживается")
    schema_version = manifest.get("schema_version")
    if not isinstance(schema_version, int) or schema_version > SCHEMA_VERSION:
        raise DataTransferError("Экспорт создан более новой несовместимой версией mLib")


def _load_database_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataTransferError("database/data.json отсутствует или повреждён") from exc
    if payload.get("format") != "mlib-portable-json" or not isinstance(payload.get("domains"), dict):
        raise DataTransferError("Неизвестный формат database/data.json")
    return payload


def _validated_rows(domain: Domain, domain_payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(domain_payload, dict) or not isinstance(domain_payload.get("tables"), list):
        raise DataTransferError(f"Повреждён раздел данных {domain.name}")
    table_map = {table.name: table for table in domain.metadata.sorted_tables}
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for raw_table in domain_payload["tables"]:
        if not isinstance(raw_table, dict) or not isinstance(raw_table.get("name"), str):
            raise DataTransferError(f"Повреждено описание таблицы {domain.name}")
        name = raw_table["name"]
        if name in seen or name not in table_map or name in TRANSIENT_TABLES.get(domain.name, set()):
            raise DataTransferError(f"Неизвестная или повторная таблица {domain.name}.{name}")
        seen.add(name)
        table = table_map[name]
        columns = raw_table.get("columns")
        rows = raw_table.get("rows")
        expected_columns = [column.name for column in table.columns]
        if columns != expected_columns or not isinstance(rows, list):
            raise DataTransferError(f"Несовместимая структура таблицы {domain.name}.{name}")
        decoded: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(expected_columns):
                raise DataTransferError(f"Повреждена запись {domain.name}.{name}")
            decoded.append({key: _decode(value) for key, value in row.items()})
        rows_by_table[name] = decoded
    required = set(table_map) - TRANSIENT_TABLES.get(domain.name, set())
    if seen != required:
        missing = ", ".join(sorted(required - seen))
        raise DataTransferError(f"В экспорте отсутствуют таблицы: {missing}")
    return rows_by_table


def _validate_media_references(rows: dict[str, dict[str, list[dict[str, Any]]]], media_root: Path) -> None:
    for domain_name, tables in MEDIA_COLUMNS.items():
        for table_name, columns in tables.items():
            for row in rows.get(domain_name, {}).get(table_name, []):
                for column in columns:
                    value = row.get(column)
                    if not value:
                        continue
                    path = PurePosixPath(str(value).replace("\\", "/"))
                    if path.is_absolute() or ".." in path.parts or not (media_root / path).is_file():
                        raise DataTransferError(f"В экспорте отсутствует media-файл {value}")


def _import_rows(rows: dict[str, dict[str, list[dict[str, Any]]]], settings: Settings) -> None:
    connections: list[tuple[Domain, Connection, Any]] = []
    try:
        for domain in DOMAINS:
            connection = domain.engine.connect()
            connections.append((domain, connection, connection.begin()))
        for domain, connection, _transaction in connections:
            tables = list(domain.metadata.sorted_tables)
            for table in reversed(tables):
                connection.execute(table.delete())
            table_map = {table.name: table for table in tables}
            for table in tables:
                table_rows = rows[domain.name].get(table.name, [])
                if table_rows:
                    connection.execute(insert(table), table_rows)
            if domain.name == "core":
                connection.execute(
                    insert(table_map["core_settings"]),
                    {"key": "library_path", "value": str(settings.media_root)},
                )
            if domain.engine.dialect.name == "sqlite":
                violations = connection.execute(text("PRAGMA foreign_key_check")).fetchmany(1)
                if violations:
                    raise DataTransferError(f"Нарушены связи в разделе {domain.name}")
        for _domain, _connection, transaction in connections:
            transaction.commit()
    except Exception:
        for _domain, _connection, transaction in connections:
            if transaction.is_active:
                transaction.rollback()
        raise
    finally:
        for _domain, connection, _transaction in connections:
            connection.close()


def import_portable_export(source: Path, settings: Settings) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    settings.temp_root.mkdir(parents=True, exist_ok=True)
    with _operation_lock, tempfile.TemporaryDirectory(prefix="mlib-import-", dir=settings.temp_root) as raw:
        root = Path(raw)
        manifest = _extract_and_verify(source, root, "export")
        _validate_export_manifest(manifest)
        payload = _load_database_payload(root / "database" / "data.json")
        domains_payload = payload["domains"]
        if set(domains_payload) != set(DOMAIN_MAP):
            raise DataTransferError("Экспорт содержит неполный набор разделов базы данных")
        rows = {
            domain.name: _validated_rows(domain, domains_payload[domain.name])
            for domain in DOMAINS
        }
        _validate_media_references(rows, root / "media")
        safety = create_backup(None, settings, reason="before-import")
        try:
            _import_rows(rows, settings)
            _replace_media(root / "media", settings)
        except Exception:
            restore_backup(safety, settings, make_safety_backup=False)
            raise
    return source, safety


def prune_automatic_backups(settings: Settings, keep: int = 7) -> None:
    candidates = sorted(
        settings.backups_root.glob("auto-before-migration-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in candidates[keep:]:
        old.unlink(missing_ok=True)


def automatic_migration_backup(settings: Settings) -> Path:
    destination = _default_backup_path(settings, "auto-before-migration")
    backup = create_backup(destination, settings, reason="before-migration")
    prune_automatic_backups(settings)
    return backup
