import zipfile
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.data_transfer.service import (
    DataTransferError,
    create_backup,
    create_portable_export,
    import_portable_export,
    restore_backup_with_client_state,
)
from app.database.session import BooksSessionLocal, GamesSessionLocal, WishesSessionLocal
from app.modules.books.models import Book
from app.modules.games.models import Game
from app.modules.wishes.models import Wish


def desktop_settings(tmp_path: Path):
    return get_settings().model_copy(
        update={
            "app_mode": "desktop",
            "data_root": tmp_path / "data",
            "media_root": tmp_path / "media",
            "backups_root": tmp_path / "backups",
            "temp_root": tmp_path / "temp",
        }
    )


def test_portable_export_import_preserves_unicode_ids_relationships_and_media(
    authenticated_client,
    tmp_path: Path,
) -> None:
    settings = desktop_settings(tmp_path)
    relative = Path("books/originals/ab/book-id.txt")
    media_file = settings.media_root / relative
    media_file.parent.mkdir(parents=True)
    media_file.write_text("Русский текст книги", encoding="utf-8")

    with BooksSessionLocal() as db:
        db.add(
            Book(
                id="book-id",
                media_type="ebook",
                title="Мастер и Маргарита",
                author="Михаил Булгаков",
                file_path=relative.as_posix(),
                original_filename="Мастер и Маргарита.txt",
                file_size=media_file.stat().st_size,
                file_hash="a" * 64,
                format="txt",
                mime_type="text/plain",
            )
        )
        db.commit()
    with GamesSessionLocal() as db:
        db.add(Game(id="game-id", title="Космические рейнджеры", platform="PC"))
        db.commit()

    archive = create_portable_export(tmp_path / "library.zip", settings)
    assert archive.is_file()

    with BooksSessionLocal() as db:
        db.execute(Book.__table__.delete())
        db.commit()
    with GamesSessionLocal() as db:
        db.execute(Game.__table__.delete())
        db.commit()
    media_file.unlink()

    _, safety = import_portable_export(archive, settings)
    assert safety.is_file()
    with BooksSessionLocal() as db:
        restored = db.get(Book, "book-id")
        assert restored is not None
        assert restored.title == "Мастер и Маргарита"
        assert restored.file_path == relative.as_posix()
    with GamesSessionLocal() as db:
        assert db.get(Game, "game-id").title == "Космические рейнджеры"
    assert media_file.read_text(encoding="utf-8") == "Русский текст книги"


def test_broken_import_does_not_change_current_library(authenticated_client, tmp_path: Path) -> None:
    settings = desktop_settings(tmp_path)
    settings.media_root.mkdir(parents=True)
    with GamesSessionLocal() as db:
        db.add(Game(id="safe-game", title="Сохранить меня", platform="PC"))
        db.commit()
    archive = create_portable_export(tmp_path / "valid.zip", settings)
    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(broken, "w") as output:
        for member in source.infolist():
            content = b"tampered" if member.filename == "metadata/entities.json" else source.read(member)
            output.writestr(member, content)

    with pytest.raises(DataTransferError, match="размер файла|контрольная сумма"):
        import_portable_export(broken, settings)

    with GamesSessionLocal() as db:
        assert db.get(Game, "safe-game").title == "Сохранить меня"


def test_exact_backup_restore_and_large_library(authenticated_client, tmp_path: Path) -> None:
    settings = desktop_settings(tmp_path)
    settings.media_root.mkdir(parents=True)
    media_file = settings.media_root / "collections" / "item" / "photo.jpg"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"full-resolution-photo")
    client_state = {
        "version": 1,
        "theme": "dark",
        "player": {"queue": [{"id": "track-1", "title": "Песня"}], "index": 0, "volume": 0.35},
    }
    wishes = [
        Wish(
            id=f"wish-{index:04d}",
            owner_id="owner",
            category="buy",
            target_type="item",
            title=f"Предмет {index}",
            normalized_title=f"предмет {index}",
        )
        for index in range(1_000)
    ]
    with WishesSessionLocal() as db:
        db.add_all(wishes)
        db.commit()

    backup = create_backup(tmp_path / "large-backup.zip", settings, client_state=client_state)
    with zipfile.ZipFile(backup) as archive:
        names = set(archive.namelist())
        domains = ("core", "music", "movie", "books", "collections", "games", "wishes")
        assert {f"database/{name}.db" for name in domains} <= names
        assert "media/collections/item/photo.jpg" in names
        assert "settings/client.json" in names
    with WishesSessionLocal() as db:
        db.execute(Wish.__table__.delete())
        db.commit()
    media_file.unlink()
    _, safety, restored_state = restore_backup_with_client_state(backup, settings)

    with WishesSessionLocal() as db:
        assert db.scalar(select(func.count(Wish.id))) == 1_000
        assert db.get(Wish, "wish-0999").title == "Предмет 999"
    assert safety is not None and safety.is_file()
    assert media_file.read_bytes() == b"full-resolution-photo"
    assert restored_state == client_state


def test_backup_rejects_invalid_client_state(authenticated_client, tmp_path: Path) -> None:
    settings = desktop_settings(tmp_path)
    settings.media_root.mkdir(parents=True)
    with pytest.raises(DataTransferError, match="очередь проигрывателя"):
        create_backup(
            tmp_path / "invalid-client-state.zip",
            settings,
            client_state={"version": 1, "theme": "system", "player": {"queue": [{}] * 501}},
        )
