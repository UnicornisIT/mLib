from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AdminUser, CurrentUser
from app.core.config import Settings, get_settings
from app.database.session import get_books_db
from app.modules.books.library import BooksStorage, audio_duration, iter_file_range, parse_range_header
from app.modules.books.models import Book
from app.modules.books.schemas import BookPage, BookRead, BooksDashboard

router = APIRouter(prefix="/books", tags=["books"])


def serialize_book(book: Book) -> BookRead:
    return BookRead(
        id=book.id,
        media_type=book.media_type,  # type: ignore[arg-type]
        title=book.title,
        author=book.author,
        description=book.description,
        genre=book.genre,
        language=book.language,
        publication_year=book.publication_year,
        publisher=book.publisher,
        isbn=book.isbn,
        narrator=book.narrator,
        page_count=book.page_count,
        duration=book.duration,
        original_filename=book.original_filename,
        file_size=book.file_size,
        format=book.format,
        mime_type=book.mime_type,
        has_cover=bool(book.cover_path),
        added_at=book.added_at,
        updated_at=book.updated_at,
    )


def require_book(db: Session, book_id: str) -> Book:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return book


@router.get("", response_model=BookPage)
def list_books(
    _: CurrentUser,
    db: Annotated[Session, Depends(get_books_db)],
    q: str | None = None,
    media_type: Literal["all", "ebook", "audiobook"] = "all",
    genre: str | None = None,
    sort: Literal["added", "title", "author", "year"] = "added",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> BookPage:
    filters = []
    if media_type != "all":
        filters.append(Book.media_type == media_type)
    if genre:
        filters.append(func.lower(Book.genre) == genre.strip().lower())
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Book.title.like(term),
                Book.author.like(term),
                func.coalesce(Book.narrator, "").like(term),
                func.coalesce(Book.genre, "").like(term),
            )
        )
    ordering = {
        "title": (Book.title.asc(), Book.author.asc()),
        "author": (Book.author.asc(), Book.title.asc()),
        "year": (Book.publication_year.desc(), Book.title.asc()),
    }.get(sort, (Book.added_at.desc(),))
    total = int(db.scalar(select(func.count(Book.id)).where(*filters)) or 0)
    items = db.scalars(select(Book).where(*filters).order_by(*ordering).limit(limit)).all()
    return BookPage(items=[serialize_book(item) for item in items], total=total)


@router.get("/dashboard", response_model=BooksDashboard)
def dashboard(_: CurrentUser, db: Annotated[Session, Depends(get_books_db)]) -> BooksDashboard:
    total = int(db.scalar(select(func.count(Book.id))) or 0)
    ebooks = int(db.scalar(select(func.count(Book.id)).where(Book.media_type == "ebook")) or 0)
    audiobooks = total - ebooks
    authors = int(db.scalar(select(func.count(func.distinct(func.lower(Book.author))))) or 0)
    storage_bytes = int(db.scalar(select(func.coalesce(func.sum(Book.file_size), 0))) or 0)
    return BooksDashboard(
        total=total,
        ebooks=ebooks,
        audiobooks=audiobooks,
        authors=authors,
        storage_bytes=storage_bytes,
    )


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def upload_book(
    user: AdminUser,
    db: Annotated[Session, Depends(get_books_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    author: Annotated[str, Form()],
    media_type: Annotated[Literal["ebook", "audiobook"], Form()],
    cover: Annotated[UploadFile | None, File()] = None,
    description: Annotated[str | None, Form()] = None,
    genre: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    publication_year: Annotated[int | None, Form(ge=0, le=3000)] = None,
    publisher: Annotated[str | None, Form()] = None,
    isbn: Annotated[str | None, Form()] = None,
    narrator: Annotated[str | None, Form()] = None,
    page_count: Annotated[int | None, Form(ge=1)] = None,
) -> BookRead:
    clean_title = title.strip()
    clean_author = author.strip()
    if not clean_title or not clean_author:
        raise HTTPException(status_code=422, detail="Укажите название и автора")
    storage = BooksStorage(settings)
    staged, filename, file_size, file_hash, extension = await storage.stage(file, media_type)
    if db.scalar(select(Book.id).where(Book.file_hash == file_hash)):
        staged.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Этот файл уже есть в библиотеке")

    book = Book(
        media_type=media_type,
        title=clean_title[:500],
        author=clean_author[:500],
        description=(description or "").strip() or None,
        genre=(genre or "").strip()[:255] or None,
        language=(language or "").strip()[:80] or None,
        publication_year=publication_year,
        publisher=(publisher or "").strip()[:255] or None,
        isbn=(isbn or "").strip()[:40] or None,
        narrator=(narrator or "").strip()[:500] or None if media_type == "audiobook" else None,
        page_count=page_count if media_type == "ebook" else None,
        file_path="",
        original_filename=filename,
        file_size=file_size,
        file_hash=file_hash,
        format=extension.lstrip("."),
        mime_type=storage.mime_type(extension),
    )
    db.add(book)
    db.flush()
    media_path: Path | None = None
    cover_path: Path | None = None
    try:
        media_path = storage.commit_file(staged, book.id, extension)
        book.file_path = storage.relative(media_path)
        if media_type == "audiobook":
            book.duration = audio_duration(media_path)
        if cover and cover.filename:
            cover_path = await storage.save_cover(cover, book.id)
            book.cover_path = storage.relative(cover_path)
        db.commit()
    except Exception:
        db.rollback()
        staged.unlink(missing_ok=True)
        if media_path:
            media_path.unlink(missing_ok=True)
        if cover_path:
            cover_path.unlink(missing_ok=True)
        raise
    db.refresh(book)
    return serialize_book(book)


@router.get("/{book_id}", response_model=BookRead)
def book_detail(book_id: str, _: CurrentUser, db: Annotated[Session, Depends(get_books_db)]) -> BookRead:
    return serialize_book(require_book(db, book_id))


@router.get("/{book_id}/cover")
def book_cover(
    book_id: str,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_books_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    book = require_book(db, book_id)
    if not book.cover_path:
        raise HTTPException(status_code=404, detail="Обложка не загружена")
    try:
        path = BooksStorage(settings).managed(book.cover_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь обложки") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл обложки отсутствует")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/{book_id}/content")
def book_content(
    book_id: str,
    _: CurrentUser,
    db: Annotated[Session, Depends(get_books_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    book = require_book(db, book_id)
    try:
        path = BooksStorage(settings).managed(book.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Некорректный путь файла") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл книги отсутствует")
    if book.media_type == "ebook":
        return FileResponse(path, media_type=book.mime_type, filename=book.original_filename)
    file_size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    if range_header:
        try:
            start, end = parse_range_header(range_header, file_size)
        except (ValueError, TypeError):
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
        length = end - start + 1
        headers.update({"Content-Range": f"bytes {start}-{end}/{file_size}", "Content-Length": str(length)})
        return StreamingResponse(
            iter_file_range(path, start, length),
            status_code=206,
            media_type=book.mime_type,
            headers=headers,
        )
    headers["Content-Length"] = str(file_size)
    return StreamingResponse(iter_file_range(path, 0, file_size), media_type=book.mime_type, headers=headers)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: str,
    _: AdminUser,
    db: Annotated[Session, Depends(get_books_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    book = require_book(db, book_id)
    storage = BooksStorage(settings)
    paths = [book.file_path, book.cover_path]
    db.delete(book)
    db.commit()
    for relative_path in paths:
        if not relative_path:
            continue
        try:
            storage.managed(relative_path).unlink(missing_ok=True)
        except ValueError:
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
