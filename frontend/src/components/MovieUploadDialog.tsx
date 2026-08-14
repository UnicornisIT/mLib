"use client";

import { FileVideo2, UploadCloud, X } from "lucide-react";
import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { MovieUpload } from "@/lib/types";

type FileState = {
  file: File;
  progress: number;
  status: "ready" | "uploading" | "processing" | "done" | "error";
  detail?: string;
};

async function uploadInChunks(file: File, titleId: string | undefined, onProgress: (progress: number, processing?: boolean) => void): Promise<MovieUpload> {
  let upload = await api<MovieUpload>("/movie/uploads", {
    method: "POST",
    body: { filename: file.name, size: file.size, title_id: titleId },
  });
  while (upload.offset < file.size) {
    const end = Math.min(upload.offset + upload.chunk_size, file.size);
    const response = await fetch(`/api/movie/uploads/${upload.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/offset+octet-stream",
        "Upload-Offset": String(upload.offset),
      },
      body: file.slice(upload.offset, end),
    });
    const payload = await response.json() as MovieUpload | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && payload.detail ? payload.detail : "Не удалось продолжить загрузку");
    upload = payload as MovieUpload;
    onProgress(Math.round((upload.offset / file.size) * 100), upload.status === "processing");
    if (upload.status === "error") throw new Error(upload.error || "Файл не удалось обработать");
  }
  return upload;
}

export function MovieUploadDialog({
  open,
  onClose,
  titleId,
  titleName,
}: {
  open: boolean;
  onClose: () => void;
  titleId?: string;
  titleName?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<FileState[]>([]);
  const [dragging, setDragging] = useState(false);
  if (!open) return null;

  const addFiles = (files: FileList | File[]) => {
    const next = Array.from(files).filter((file) => file.size > 0).map((file) => ({
      file,
      progress: 0,
      status: "ready" as const,
    }));
    setItems((current) => [...current, ...next]);
  };
  const start = async () => {
    for (let index = 0; index < items.length; index += 1) {
      if (items[index].status !== "ready") continue;
      setItems((current) => current.map((item, i) => i === index ? { ...item, status: "uploading" } : item));
      try {
        await uploadInChunks(items[index].file, titleId, (progress, processing) => {
          setItems((current) => current.map((item, i) => i === index ? {
            ...item,
            progress,
            status: processing ? "processing" : "uploading",
          } : item));
        });
        setItems((current) => current.map((item, i) => i === index ? {
          ...item,
          progress: 100,
          status: "done",
          detail: titleName ? `Прикреплено к «${titleName}»` : "Добавлено в movieLib",
        } : item));
      } catch (error) {
        setItems((current) => current.map((item, i) => i === index ? {
          ...item,
          status: "error",
          detail: error instanceof Error ? error.message : "Ошибка загрузки",
        } : item));
      }
    }
    window.dispatchEvent(new Event("mlib:movie-library-changed"));
  };
  const close = () => { setItems([]); onClose(); };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <div className="modal upload-modal movie-upload-modal" role="dialog" aria-modal="true" aria-labelledby="movie-upload-title">
        <div className="modal-header">
          <div><div className="eyebrow">movieLib</div><h2 id="movie-upload-title">Добавить видео</h2></div>
          <button className="icon-button" onClick={close} aria-label="Закрыть"><X size={19} /></button>
        </div>
        <div className="modal-body">
          <input ref={inputRef} hidden type="file" multiple onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files && addFiles(event.target.files)} />
          <div
            className={`dropzone movie-dropzone ${dragging ? "dragging" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}
          >
            <div><UploadCloud size={36} /><h3>{titleName ? `Добавить видео к «${titleName}»` : "Перетащите фильмы или серии"}</h3><p>Любой размер · формат проверит FFmpeg · загрузка продолжится по частям</p></div>
          </div>
          {items.length > 0 && <div className="upload-list">{items.map((item, index) => (
            <div className="upload-item" key={`${item.file.name}-${item.file.lastModified}-${index}`}>
              <div className="upload-info">
                <span className="upload-name"><FileVideo2 size={15} />{item.file.name}<small>{formatBytes(item.file.size)}</small></span>
                <span className={`upload-status ${item.status}`}>
                  {item.status === "ready" && "Готов"}
                  {item.status === "uploading" && `${item.progress}%`}
                  {item.status === "processing" && "Проверяем видео…"}
                  {item.status === "done" && item.detail}
                  {item.status === "error" && item.detail}
                </span>
              </div>
              <div className="upload-progress"><span style={{ width: `${item.progress}%` }} /></div>
            </div>
          ))}</div>}
          <div className="movie-upload-note">{titleName ? `Файл будет сохранён именно в карточке «${titleName}». Для сериала сезон и серия определятся из имени файла, например S01E03.` : "Выберите карточку фильма или сериала в каталоге, чтобы прикрепить файл точно к ней."}</div>
          <div className="form-actions">
            <button className="button" onClick={close}>Закрыть</button>
            <button className="button primary" disabled={!items.some((item) => item.status === "ready")} onClick={() => void start()}>
              Загрузить {items.filter((item) => item.status === "ready").length || ""}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
