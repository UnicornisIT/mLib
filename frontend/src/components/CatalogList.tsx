"use client";

import { LoaderCircle, Search, UploadCloud } from "lucide-react";
import Link from "next/link";
import { Artwork } from "@/components/Artwork";
import { useCatalogUpload, useFileDrop } from "@/components/CatalogCard";
import { catalogDuration, catalogHref } from "@/lib/catalog";
import type { CatalogTrack } from "@/lib/types";

function appleSearchUrl(item: CatalogTrack) {
  return `https://music.apple.com/search?${new URLSearchParams({ term: `${item.artist_name} ${item.title}` })}`;
}

function status(item: CatalogTrack): { label: string; tone: "file" | "missing" | "pending" | "plain" } {
  if (item.has_file) return { label: "Файл есть", tone: "file" };
  if (item.enrich_status === "pending") return { label: "Ищем в Apple", tone: "pending" };
  if (item.enrich_status === "not_found" || item.enrich_status === "error") return { label: "Не найден в Apple", tone: "missing" };
  return { label: "Нет файла", tone: "plain" };
}

function CatalogRow({ item, canUpload, onUpdated }: { item: CatalogTrack; canUpload: boolean; onUpdated: (item: CatalogTrack) => void }) {
  const { uploading, upload } = useCatalogUpload((updated) => onUpdated(updated));
  const { dragging, handlers } = useFileDrop(canUpload && !item.has_file && !uploading, (file) => void upload(item, file));
  const state = status(item);
  const missing = state.tone === "missing";
  return (
    <li className={`catalog-row ${item.has_file ? "" : "no-file"} ${dragging ? "dragging" : ""}`} aria-label={`${item.title} — ${item.artist_name}`} {...handlers}>
      <span className="catalog-row-art"><Artwork id={item.artwork_id} url={item.artwork_url} alt={item.title} size={64} /></span>
      <span className="catalog-row-copy">
        <Link className="catalog-row-title" href={catalogHref(item.id)}>{item.title}</Link>
        <span className="catalog-row-sub">{item.artist_name}{item.album_title ? ` · ${item.album_title}` : ""}</span>
      </span>
      <span className={`catalog-status ${state.tone}`}>
        {uploading ? <><LoaderCircle className="spin" size={12} />Загружаем…</> : dragging ? <><UploadCloud size={12} />Отпустите</> : state.label}
      </span>
      <span className="catalog-row-time">{catalogDuration(item.duration_ms) ?? "—"}</span>
      <span className="catalog-row-links">
        {missing ? (
          <>
            <a href={appleSearchUrl(item)} target="_blank" rel="noreferrer"><Search size={13} />Apple Music</a>
            <a href={item.spotify_url} target="_blank" rel="noreferrer"><Search size={13} />Spotify</a>
          </>
        ) : item.apple_music_url ? (
          <a href={item.apple_music_url} target="_blank" rel="noreferrer">Apple Music</a>
        ) : null}
      </span>
    </li>
  );
}

/** Plain track list of the catalog: readable for long libraries and for tracks Apple did not find. */
export function CatalogList({ items, canUpload, onUpdated }: { items: CatalogTrack[]; canUpload: boolean; onUpdated: (item: CatalogTrack) => void }) {
  return (
    <ol className="catalog-list" aria-label="Список треков каталога">
      {items.map((item) => <CatalogRow key={item.id} item={item} canUpload={canUpload} onUpdated={onUpdated} />)}
    </ol>
  );
}
