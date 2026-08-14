import { AudioLines, BookOpenText, Headphones, MoreHorizontal } from "lucide-react";
import Image from "next/image";
import { bookCoverUrl } from "@/lib/api";
import type { Book } from "@/lib/types";

function formatDuration(seconds: number | null) {
  if (!seconds) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
}

export function BookCard({ book, onOpen }: { book: Book; onOpen: () => void }) {
  const isAudio = book.media_type === "audiobook";
  const detail = isAudio
    ? formatDuration(book.duration) || (book.narrator ? `Читает ${book.narrator}` : "Аудиокнига")
    : book.page_count ? `${book.page_count} стр.` : book.format.toUpperCase();

  return (
    <article className="book-card">
      <button className="book-cover-button" type="button" onClick={onOpen} aria-label={`Открыть «${book.title}»`}>
        <span className={`book-cover ${book.has_cover ? "has-image" : `placeholder-${book.id.charCodeAt(0) % 4}`}`}>
          {book.has_cover ? (
            <Image src={bookCoverUrl(book.id)} alt={`Обложка «${book.title}»`} fill unoptimized sizes="(max-width: 640px) 44vw, 210px" />
          ) : (
            <span className="book-cover-placeholder"><small>{book.author}</small><strong>{book.title}</strong><i>{book.publication_year || "mLib"}</i></span>
          )}
          <span className="book-format-badge">{book.format.toUpperCase()}</span>
          <span className="book-card-action">{isAudio ? <AudioLines size={19} /> : <BookOpenText size={19} />}</span>
        </span>
      </button>
      <div className="book-card-copy">
        <button type="button" onClick={onOpen}>
          <strong>{book.title}</strong>
          <span>{book.author}</span>
        </button>
        <button className="book-more" type="button" onClick={onOpen} aria-label="Подробнее"><MoreHorizontal size={18} /></button>
      </div>
      <div className="book-card-meta">
        <span>{isAudio ? <Headphones size={12} /> : <BookOpenText size={12} />}{detail}</span>
        {book.genre && <span>{book.genre}</span>}
      </div>
    </article>
  );
}
