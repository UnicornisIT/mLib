"use client";

import { useEffect, useState } from "react";
import { api, artworkUrl } from "@/lib/api";
import type { CatalogFileResult, CatalogTrack, Track } from "@/lib/types";

export type CatalogFilter = "all" | "with_file" | "without_file" | "not_found";

export const CATALOG_FILTERS: { value: CatalogFilter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "with_file", label: "С файлом" },
  { value: "without_file", label: "Нет файла" },
  { value: "not_found", label: "Не найдены в Apple" },
];

export const AUDIO_ACCEPT = "audio/*,.mp3,.m4a,.aac,.flac,.alac,.wav,.aif,.aiff,.ogg,.opus,.wma";

/** Catalog data replaces the file's tags on screen; the tags themselves stay untouched. */
export function trackDisplay(track: Track) {
  const catalog = track.catalog;
  return {
    title: catalog?.title || track.title,
    artist: catalog?.artist_name || track.artist.name,
    album: catalog?.album_title || track.album?.title || null,
    artworkUrl: catalog?.artwork_url ?? null,
  };
}

export function catalogHref(id: string) {
  return `/music/catalog/${id}`;
}

type AlbumIdentity = Pick<CatalogTrack, "artist_name" | "album_title" | "collection_id">;

/** Apple's album id groups tracks that credit different artists ("Daft Punk & Pharrell Williams"). */
export function catalogAlbumKey(item: AlbumIdentity) {
  return item.collection_id ? `apple:${item.collection_id}` : `${item.artist_name}\u0000${item.album_title ?? ""}`;
}

export function sameCatalogAlbum(item: AlbumIdentity, album: { collection: string | null; artist: string | null; title: string }) {
  if (album.collection) return item.collection_id === album.collection;
  return item.album_title === album.title && item.artist_name === album.artist;
}

export function catalogAlbumHref(item: AlbumIdentity) {
  const params = new URLSearchParams({ title: item.album_title ?? "" });
  if (item.collection_id) params.set("collection", item.collection_id);
  else params.set("artist", item.artist_name);
  return `/music/catalog/album?${params}`;
}

/** The lead artist shared by an album's tracks: "Daft Punk & X" and "Daft Punk, Y" give "Daft Punk". */
export function catalogAlbumArtist(names: string[]) {
  const unique = [...new Set(names)];
  if (unique.length <= 1) return unique[0] ?? "";
  let prefix = unique[0];
  for (const name of unique.slice(1)) {
    let index = 0;
    while (index < prefix.length && index < name.length && prefix[index] === name[index]) index += 1;
    prefix = prefix.slice(0, index);
  }
  const lead = prefix.replace(/[\s,&]+$/u, "").trim();
  return lead.length >= 2 ? lead : "Разные исполнители";
}

export function catalogDuration(durationMs: number | null) {
  if (!durationMs) return null;
  const seconds = Math.round(durationMs / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function isAudioFile(file: File) {
  if (file.type.startsWith("audio/")) return true;
  return /\.(mp3|m4a|aac|flac|alac|wav|aiff?|ogg|opus|wma)$/i.test(file.name);
}

export function hasDraggedFiles(event: { dataTransfer: DataTransfer | null }) {
  return Boolean(event.dataTransfer?.types.includes("Files"));
}

export async function uploadCatalogFile(catalogTrackId: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  const result = await api<CatalogFileResult>(`/music/transfer/tracks/${catalogTrackId}/file`, { method: "POST", body });
  window.dispatchEvent(new Event("mlib:library-changed"));
  return result;
}

/** Loads every catalog page for the given filters; the API caps a page at 200 items. */
export async function loadAllCatalogTracks(params: URLSearchParams) {
  const items: CatalogTrack[] = [];
  for (let page = 1; ; page += 1) {
    params.set("page", String(page));
    params.set("page_size", "200");
    const result = await api<{ items: CatalogTrack[]; pages: number }>(`/music/transfer/tracks?${params}`);
    items.push(...result.items);
    if (page >= result.pages) return items;
  }
}

export function catalogArtworkSource(item: { artwork_id?: string | null; artwork_url?: string | null }, size: 64 | 256 | 512 = 256) {
  return artworkUrl(item.artwork_id, size) ?? item.artwork_url ?? null;
}

const colorCache = new Map<string, string | null>();

function averageColor(image: HTMLImageElement) {
  const canvas = document.createElement("canvas");
  canvas.width = 24;
  canvas.height = 24;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(image, 0, 0, 24, 24);
  const { data } = context.getImageData(0, 0, 24, 24);
  let red = 0, green = 0, blue = 0, weight = 0;
  for (let index = 0; index < data.length; index += 4) {
    const [r, g, b] = [data[index], data[index + 1], data[index + 2]];
    // Saturated pixels describe a cover better than near-grey ones.
    const saturation = Math.max(r, g, b) - Math.min(r, g, b);
    const w = 1 + saturation / 32;
    red += r * w; green += g * w; blue += b * w; weight += w;
  }
  if (!weight) return null;
  return `rgb(${Math.round(red / weight)} ${Math.round(green / weight)} ${Math.round(blue / weight)})`;
}

/**
 * Dominant colour of a cover for background gradients. Apple artwork is only displayed:
 * the browser reads pixels of the image it already shows and nothing is stored.
 */
export function useArtworkColor(source: string | null) {
  const [color, setColor] = useState<{ source: string; value: string | null } | null>(null);
  useEffect(() => {
    if (!source || colorCache.has(source)) return;
    let cancelled = false;
    const image = new window.Image();
    image.crossOrigin = "anonymous";
    image.decoding = "async";
    image.onload = () => {
      let value: string | null = null;
      try { value = averageColor(image); } catch { value = null; }
      colorCache.set(source, value);
      if (!cancelled) setColor({ source, value });
    };
    image.onerror = () => {
      colorCache.set(source, null);
      if (!cancelled) setColor({ source, value: null });
    };
    image.src = source;
    return () => { cancelled = true; };
  }, [source]);
  if (source && colorCache.has(source)) return colorCache.get(source) ?? null;
  return color && color.source === source ? color.value : null;
}
