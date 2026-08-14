"use client";

import { UploadCloud, X } from "lucide-react";
import { ChangeEvent, DragEvent, useRef, useState } from "react";
import type { UploadResult } from "@/lib/types";

type FileState = { file: File; progress: number; status: "ready" | "uploading" | "done" | "error"; detail?: string };

function uploadOne(item: FileState, onProgress: (value: number) => void): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const body = new FormData();
    body.append("files", item.file);
    request.open("POST", "/api/music/upload");
    request.withCredentials = true;
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new Error("Соединение с сервером прервано"));
    request.onload = () => {
      try {
        const payload = JSON.parse(request.responseText) as UploadResult[] | { detail?: string };
        if (request.status < 200 || request.status >= 300) {
          reject(new Error(!Array.isArray(payload) && payload.detail ? payload.detail : "Не удалось загрузить файл"));
        } else resolve((payload as UploadResult[])[0]);
      } catch {
        reject(new Error("Сервер вернул некорректный ответ"));
      }
    };
    request.send(body);
  });
}

export function UploadDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<FileState[]>([]);
  const [dragging, setDragging] = useState(false);
  if (!open) return null;

  const addFiles = (files: FileList | File[]) => {
    const next = Array.from(files).map((file) => ({ file, progress: 0, status: "ready" as const }));
    setItems((current) => [...current, ...next]);
  };
  const upload = async () => {
    for (let index = 0; index < items.length; index += 1) {
      if (items[index].status !== "ready") continue;
      setItems((current) => current.map((item, i) => i === index ? { ...item, status: "uploading" } : item));
      try {
        const result = await uploadOne(items[index], (progress) =>
          setItems((current) => current.map((item, i) => i === index ? { ...item, progress } : item)),
        );
        const failed = result.status === "error";
        setItems((current) => current.map((item, i) => i === index ? {
          ...item,
          progress: 100,
          status: failed ? "error" : "done",
          detail: result.detail,
        } : item));
      } catch (error) {
        setItems((current) => current.map((item, i) => i === index ? {
          ...item,
          status: "error",
          detail: error instanceof Error ? error.message : "Ошибка загрузки",
        } : item));
      }
    }
    window.dispatchEvent(new Event("mlib:library-changed"));
  };
  const close = () => {
    setItems([]);
    onClose();
  };
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <div className="modal upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title">
        <div className="modal-header">
          <h2 id="upload-title">Добавить музыку</h2>
          <button className="icon-button" onClick={close} aria-label="Закрыть"><X size={19} /></button>
        </div>
        <div className="modal-body">
          <input
            ref={inputRef}
            hidden
            type="file"
            multiple
            accept=".mp3,.flac,.m4a,.aac,.ogg,.wav,.opus,audio/*"
            onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files && addFiles(event.target.files)}
          />
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}
          >
            <div>
              <UploadCloud size={34} color="var(--accent)" />
              <h3>Перетащите аудиофайлы сюда</h3>
              <p>или нажмите, чтобы выбрать один или несколько файлов</p>
            </div>
          </div>
          {items.length > 0 && (
            <div className="upload-list">
              {items.map((item, index) => (
                <div className="upload-item" key={`${item.file.name}-${item.file.lastModified}-${index}`}>
                  <div className="upload-info">
                    <span className="upload-name">{item.file.name}</span>
                    <span className={`upload-status ${item.status}`}>
                      {item.status === "ready" && "Готов"}
                      {item.status === "uploading" && `${item.progress}%`}
                      {item.status === "done" && (item.detail || "Добавлено")}
                      {item.status === "error" && (item.detail || "Ошибка")}
                    </span>
                  </div>
                  <div className="upload-progress"><span style={{ width: `${item.progress}%` }} /></div>
                </div>
              ))}
            </div>
          )}
          <div className="form-actions">
            <button className="button" onClick={close}>Закрыть</button>
            <button className="button primary" disabled={!items.some((item) => item.status === "ready")} onClick={() => void upload()}>
              Загрузить {items.filter((item) => item.status === "ready").length || ""}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
