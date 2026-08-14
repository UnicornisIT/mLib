"use client";

import { BookOpenText, FileAudio2, FileText, Headphones, ImagePlus, UploadCloud, X } from "lucide-react";
import Image from "next/image";
import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { formatBytes } from "@/lib/format";
import type { Book } from "@/lib/types";

type MediaType = "ebook" | "audiobook";

function uploadBook(data: FormData, onProgress: (value: number) => void): Promise<Book> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/books");
    request.withCredentials = true;
    request.upload.onprogress = (event) => event.lengthComputable && onProgress(Math.round(event.loaded / event.total * 100));
    request.onload = () => {
      let payload: Book | { detail?: string };
      try { payload = JSON.parse(request.responseText) as Book | { detail?: string }; }
      catch { reject(new Error("Сервер вернул некорректный ответ")); return; }
      if (request.status >= 200 && request.status < 300) resolve(payload as Book);
      else reject(new Error("detail" in payload && payload.detail ? payload.detail : "Не удалось загрузить книгу"));
    };
    request.onerror = () => reject(new Error("Соединение прервано во время загрузки"));
    request.send(data);
  });
}

export function BookUploadDialog({ open, onClose, onUploaded }: { open: boolean; onClose: () => void; onUploaded: (book: Book) => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const coverInput = useRef<HTMLInputElement>(null);
  const [mediaType, setMediaType] = useState<MediaType>("ebook");
  const [file, setFile] = useState<File | null>(null);
  const [cover, setCover] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [genre, setGenre] = useState("");
  const [year, setYear] = useState("");
  const [language, setLanguage] = useState("Русский");
  const [narrator, setNarrator] = useState("");
  const [pages, setPages] = useState("");
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const coverPreview = useMemo(() => cover ? URL.createObjectURL(cover) : null, [cover]);

  useEffect(() => () => { if (coverPreview) URL.revokeObjectURL(coverPreview); }, [coverPreview]);
  if (!open) return null;

  const reset = () => {
    setFile(null); setCover(null); setTitle(""); setAuthor(""); setGenre(""); setYear("");
    setNarrator(""); setPages(""); setDescription(""); setProgress(0); setError(""); setUploading(false);
  };
  const close = () => { if (uploading) return; reset(); onClose(); };
  const chooseFile = (next: File | null) => {
    if (!next) return;
    setFile(next);
    if (!title) setTitle(next.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
    const extension = next.name.split(".").pop()?.toLowerCase();
    if (["mp3", "m4b", "m4a", "aac", "ogg", "opus", "flac", "wav"].includes(extension || "")) setMediaType("audiobook");
    setError("");
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title.trim() || !author.trim()) { setError("Выберите файл и укажите название с автором"); return; }
    const data = new FormData();
    data.set("file", file); data.set("media_type", mediaType); data.set("title", title.trim()); data.set("author", author.trim());
    if (cover) data.set("cover", cover);
    if (genre.trim()) data.set("genre", genre.trim());
    if (year) data.set("publication_year", year);
    if (language.trim()) data.set("language", language.trim());
    if (description.trim()) data.set("description", description.trim());
    if (mediaType === "audiobook" && narrator.trim()) data.set("narrator", narrator.trim());
    if (mediaType === "ebook" && pages) data.set("page_count", pages);
    setUploading(true); setError(""); setProgress(0);
    try {
      const book = await uploadBook(data, setProgress);
      onUploaded(book); reset(); onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить книгу");
      setUploading(false);
    }
  };

  const accept = mediaType === "ebook" ? ".epub,.pdf,.fb2,.mobi,.azw3,.djvu,.txt" : ".mp3,.m4b,.m4a,.aac,.ogg,.opus,.flac,.wav";
  return (
    <div className="modal-backdrop book-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <form className="modal book-upload-modal" role="dialog" aria-modal="true" aria-labelledby="book-upload-title" onSubmit={submit}>
        <div className="book-upload-header">
          <div><span>bookLib · ручная загрузка</span><h2 id="book-upload-title">Новая книга</h2></div>
          <button className="book-modal-close static" type="button" onClick={close} aria-label="Закрыть"><X size={20} /></button>
        </div>
        <div className="book-upload-body">
          <div className="book-type-switch" role="group" aria-label="Тип книги">
            <button type="button" className={mediaType === "ebook" ? "active" : ""} onClick={() => { setMediaType("ebook"); setFile(null); }}><BookOpenText size={18} /><span><strong>Электронная</strong><small>EPUB, PDF, FB2 и другие</small></span></button>
            <button type="button" className={mediaType === "audiobook" ? "active" : ""} onClick={() => { setMediaType("audiobook"); setFile(null); }}><Headphones size={18} /><span><strong>Аудиокнига</strong><small>M4B, MP3, FLAC и другие</small></span></button>
          </div>

          <div className="book-upload-grid">
            <div className="book-upload-assets">
              <input ref={fileInput} hidden type="file" accept={accept} onChange={(event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0] || null)} />
              <button
                className={`book-file-drop ${dragging ? "dragging" : ""}`}
                type="button"
                onClick={() => fileInput.current?.click()}
                onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0] || null); }}
              >
                {file ? <><span>{mediaType === "audiobook" ? <FileAudio2 size={25} /> : <FileText size={25} />}</span><strong>{file.name}</strong><small>{formatBytes(file.size)} · нажмите, чтобы заменить</small></> : <><span><UploadCloud size={27} /></span><strong>Перетащите файл сюда</strong><small>или выберите на компьютере</small></>}
              </button>
              <input ref={coverInput} hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={(event: ChangeEvent<HTMLInputElement>) => setCover(event.target.files?.[0] || null)} />
              <button className="book-cover-upload" type="button" onClick={() => coverInput.current?.click()}>
                {coverPreview ? <Image src={coverPreview} alt="Предпросмотр обложки" fill unoptimized sizes="150px" /> : <><ImagePlus size={24} /><strong>Добавить обложку</strong><small>JPG, PNG или WebP</small></>}
                {coverPreview && <span>Заменить обложку</span>}
              </button>
            </div>

            <div className="book-upload-fields">
              <label className="field book-field-wide"><span>Название *</span><input className="input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Например, Дюна" required /></label>
              <label className="field book-field-wide"><span>Автор *</span><input className="input" value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Фрэнк Герберт" required /></label>
              <label className="field"><span>Жанр</span><input className="input" value={genre} onChange={(event) => setGenre(event.target.value)} placeholder="Фантастика" /></label>
              <label className="field"><span>Год</span><input className="input" type="number" min="0" max="3000" value={year} onChange={(event) => setYear(event.target.value)} placeholder="1965" /></label>
              <label className="field"><span>Язык</span><input className="input" value={language} onChange={(event) => setLanguage(event.target.value)} /></label>
              {mediaType === "ebook" ? <label className="field"><span>Страниц</span><input className="input" type="number" min="1" value={pages} onChange={(event) => setPages(event.target.value)} placeholder="704" /></label> : <label className="field"><span>Чтец</span><input className="input" value={narrator} onChange={(event) => setNarrator(event.target.value)} placeholder="Имя диктора" /></label>}
              <label className="field book-field-wide"><span>Описание</span><textarea className="textarea" rows={4} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Коротко о книге — без спойлеров" /></label>
            </div>
          </div>
          {uploading && <div className="book-upload-progress"><span style={{ width: `${progress}%` }} /><strong>{progress < 100 ? `Загружаем · ${progress}%` : "Сохраняем в библиотеку…"}</strong></div>}
          {error && <div className="form-error">{error}</div>}
        </div>
        <div className="book-upload-footer">
          <div className="book-upload-footer-content">
            <div className="book-upload-footer-actions">
              <button className="button book-cancel-button" type="button" onClick={close} disabled={uploading}>Отмена</button>
              <button className="button primary book-primary" type="submit" disabled={uploading || !file}>{uploading ? "Загружаем…" : "Добавить в bookLib"}</button>
            </div>
            <p>Файл и обложка останутся только в вашем хранилище mLib.</p>
          </div>
        </div>
      </form>
    </div>
  );
}
