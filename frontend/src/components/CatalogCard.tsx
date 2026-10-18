"use client";

import { LoaderCircle, Play, UploadCloud } from "lucide-react";
import Link from "next/link";
import { DragEvent, useRef, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { api } from "@/lib/api";
import { catalogHref, hasDraggedFiles, isAudioFile, uploadCatalogFile } from "@/lib/catalog";
import type { CatalogTrack, Track } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";
import { usePlayer } from "@/providers/PlayerProvider";

/** Drag-and-drop of a single audio file onto an element, with a counter so child elements do not flicker the state. */
export function useFileDrop(enabled: boolean, onFile: (file: File) => void) {
  const depth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const accepts = (event: DragEvent) => enabled && hasDraggedFiles(event);
  return {
    dragging,
    handlers: {
      onDragEnter: (event: DragEvent) => {
        if (!accepts(event)) return;
        event.preventDefault();
        depth.current += 1;
        setDragging(true);
      },
      onDragOver: (event: DragEvent) => {
        if (!accepts(event)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      },
      onDragLeave: (event: DragEvent) => {
        if (!accepts(event)) return;
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setDragging(false);
      },
      onDrop: (event: DragEvent) => {
        if (!accepts(event)) return;
        event.preventDefault();
        depth.current = 0;
        setDragging(false);
        const file = event.dataTransfer.files[0];
        if (file) onFile(file);
      },
    },
  };
}

/** Uploads one file into a catalog track and reports the outcome through toasts. */
export function useCatalogUpload(onUploaded: (item: CatalogTrack, track: Track) => void) {
  const feedback = useFeedback();
  const [uploading, setUploading] = useState(false);
  const upload = async (item: CatalogTrack, file: File) => {
    if (!isAudioFile(file)) {
      feedback.notify("Перетащите аудиофайл: MP3, M4A, FLAC, WAV или другой", "error");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadCatalogFile(item.id, file);
      onUploaded(result.catalog_track, result.track);
      feedback.notify(result.status === "added" ? `Файл добавлен в «${item.title}»` : result.detail);
    } catch (caught) {
      feedback.notify(caught instanceof Error ? caught.message : "Не удалось загрузить файл", "error");
    } finally {
      setUploading(false);
    }
  };
  return { uploading, upload };
}

export function CatalogCard({
  item,
  canUpload,
  onUpdated,
}: {
  item: CatalogTrack;
  canUpload: boolean;
  onUpdated: (item: CatalogTrack) => void;
}) {
  const player = usePlayer();
  const { uploading, upload } = useCatalogUpload((updated) => onUpdated(updated));
  const { dragging, handlers } = useFileDrop(canUpload && !item.has_file && !uploading, (file) => void upload(item, file));
  const href = catalogHref(item.id);

  const play = async () => {
    if (!item.track_id) return;
    const track = await api<Track>(`/music/tracks/${item.track_id}`);
    player.playTrack(track, [track]);
  };

  return (
    <article
      className={`catalog-card ${item.has_file ? "" : "no-file"} ${dragging ? "dragging" : ""}`}
      aria-label={`${item.title} — ${item.artist_name}`}
      {...handlers}
    >
      <div className="catalog-card-art">
        <Link href={href} tabIndex={-1} aria-hidden="true">
          <Artwork id={item.artwork_id} url={item.artwork_url} alt={item.title} size={256} />
        </Link>
        {item.has_file ? (
          <button className="album-play" type="button" onClick={() => void play()} aria-label={`Воспроизвести ${item.title}`}>
            <Play size={20} fill="currentColor" />
          </button>
        ) : (
          <span className="catalog-badge">Нет файла</span>
        )}
        {(dragging || uploading) && (
          <div className="catalog-drop-overlay" aria-live="polite">
            {uploading ? <LoaderCircle className="spin" size={26} /> : <UploadCloud size={26} />}
            <span>{uploading ? "Загружаем файл…" : "Отпустите, чтобы добавить файл"}</span>
          </div>
        )}
      </div>
      <Link href={href} className="album-title">{item.title}</Link>
      <div className="album-meta">{item.artist_name}{item.album_title ? ` · ${item.album_title}` : ""}</div>
    </article>
  );
}
