"use client";

import { BookOpenText, Download, FileText, Headphones, Trash2, X } from "lucide-react";
import Image from "next/image";
import { api, bookContentUrl, bookCoverUrl } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { Book } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

function durationLabel(seconds: number | null) {
  if (!seconds) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return `${hours ? `${hours} ч ` : ""}${minutes} мин`;
}

export function BookDetailsDialog({ book, onClose, onDeleted }: { book: Book; onClose: () => void; onDeleted: () => void }) {
  const feedback = useFeedback();
  const isAudio = book.media_type === "audiobook";
  const remove = async () => {
    if (!await feedback.confirm({ title: "Удалить книгу?", message: `«${book.title}» и её файл будут удалены без возможности восстановления.`, confirmLabel: "Удалить книгу", destructive: true })) return;
    await api(`/books/${book.id}`, { method: "DELETE" });
    onDeleted();
  };

  return (
    <div className="modal-backdrop book-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal book-detail-modal" role="dialog" aria-modal="true" aria-labelledby="book-detail-title">
        <button className="book-modal-close" type="button" onClick={onClose} aria-label="Закрыть"><X size={20} /></button>
        <div className={`book-detail-cover ${book.has_cover ? "has-image" : `placeholder-${book.id.charCodeAt(0) % 4}`}`}>
          {book.has_cover ? <Image src={bookCoverUrl(book.id)} alt="" fill unoptimized sizes="320px" /> : <span><small>{book.author}</small><strong>{book.title}</strong></span>}
        </div>
        <div className="book-detail-copy">
          <div className="book-detail-kicker">{isAudio ? <Headphones size={15} /> : <BookOpenText size={15} />}{isAudio ? "Аудиокнига" : "Электронная книга"}</div>
          <h2 id="book-detail-title">{book.title}</h2>
          <p className="book-detail-author">{book.author}</p>
          <div className="book-detail-tags">
            {book.publication_year && <span>{book.publication_year}</span>}
            {book.genre && <span>{book.genre}</span>}
            {book.language && <span>{book.language}</span>}
            {book.page_count && <span>{book.page_count} стр.</span>}
            {durationLabel(book.duration) && <span>{durationLabel(book.duration)}</span>}
          </div>
          {book.narrator && <p className="book-detail-narrator">Читает <strong>{book.narrator}</strong></p>}
          <p className="book-detail-description">{book.description || "Описание пока не добавлено."}</p>
          {isAudio && <audio className="book-audio" src={bookContentUrl(book.id)} controls preload="metadata" />}
          <div className="book-detail-file"><FileText size={16} /><span><strong>{book.original_filename}</strong><small>{book.format.toUpperCase()} · {formatBytes(book.file_size)}</small></span></div>
          <div className="book-detail-actions">
            <a className="button primary book-primary" href={bookContentUrl(book.id)} download={book.original_filename}><Download size={16} />Скачать</a>
            <button className="button danger-subtle" type="button" onClick={() => void remove()}><Trash2 size={16} />Удалить</button>
          </div>
        </div>
      </div>
    </div>
  );
}
