"use client";

import { ArrowLeft, Play, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { useCatalogUpload, useFileDrop } from "@/components/CatalogCard";
import { CatalogHero, ExternalLinks } from "@/components/CatalogHero";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import { catalogArtworkSource, catalogDuration, catalogHref, loadAllCatalogTracks } from "@/lib/catalog";
import type { CatalogTrack, Track } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";
import { usePlayer } from "@/providers/PlayerProvider";

export default function CatalogAlbumPage() {
  return <Suspense fallback={<div className="content-page"><PageLoader rows={6} /></div>}><CatalogAlbum /></Suspense>;
}

function CatalogAlbum() {
  const searchParams = useSearchParams();
  const artist = searchParams.get("artist") ?? "";
  const title = searchParams.get("title") ?? "";
  const { user } = useAuth();
  const player = usePlayer();
  const [items, setItems] = useState<CatalogTrack[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      // Search narrows the list by album title; the exact album is picked here.
      const found = await loadAllCatalogTracks(new URLSearchParams({ status: "all", q: title }));
      setItems(found.filter((item) => item.album_title === title && item.artist_name === artist));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить альбом");
    }
  }, [artist, title]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the request resolves
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  const update = (updated: CatalogTrack) => setItems((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? null);

  if (error) return <div className="content-page"><div className="form-error" role="alert">{error}</div></div>;
  if (!items) return <div className="content-page"><PageLoader rows={6} /></div>;
  if (!items.length) return <div className="content-page"><EmptyState title="Альбом не найден" description="В каталоге нет треков этого альбома." action={<Link className="button" href="/music/catalog" style={{ marginTop: 16 }}>К каталогу</Link>} /></div>;

  const cover = items.find((item) => item.artwork_id) ?? items.find((item) => item.artwork_url) ?? items[0];
  const year = items.find((item) => item.year)?.year;
  const withFile = items.filter((item) => item.has_file);
  const totalMs = items.reduce((sum, item) => sum + (item.duration_ms ?? 0), 0);
  const playAll = async () => {
    const tracks = await Promise.all(withFile.map((item) => api<Track>(`/music/tracks/${item.track_id}`)));
    if (tracks[0]) player.playTrack(tracks[0], tracks);
  };

  return (
    <div className="content-page catalog-detail">
      <Link className="catalog-back" href="/music/catalog"><ArrowLeft size={15} />Каталог</Link>
      <CatalogHero source={catalogArtworkSource(cover, 64)} art={<Artwork id={cover.artwork_id} url={cover.artwork_url} alt={title} size={512} />}>
        <div className="eyebrow">Альбом</div>
        <h1>{title}</h1>
        <p className="catalog-hero-artist">{artist}</p>
        <p className="catalog-hero-meta">
          {year && <span>{year}</span>}
          <span>{items.length} в каталоге</span>
          {totalMs > 0 && <span>{Math.round(totalMs / 60000)} мин</span>}
          {withFile.length < items.length && <span className="catalog-pill">Без файла: {items.length - withFile.length}</span>}
        </p>
        <div className="detail-actions">
          {withFile.length > 0 && <button className="button primary" type="button" onClick={() => void playAll()}><Play size={17} fill="currentColor" />Слушать</button>}
          <ExternalLinks appleMusicUrl={cover.apple_music_url} />
        </div>
      </CatalogHero>
      <ol className="catalog-tracklist" aria-label="Треки альбома">
        {items.map((item, index) => <AlbumRow key={item.id} item={item} index={index} canUpload={Boolean(user?.is_admin)} onUpdated={update} />)}
      </ol>
    </div>
  );
}

function AlbumRow({ item, index, canUpload, onUpdated }: { item: CatalogTrack; index: number; canUpload: boolean; onUpdated: (item: CatalogTrack) => void }) {
  const { uploading, upload } = useCatalogUpload((updated) => onUpdated(updated));
  const { dragging, handlers } = useFileDrop(canUpload && !item.has_file && !uploading, (file) => void upload(item, file));
  return (
    <li className={`${item.has_file ? "" : "no-file"} ${dragging ? "dragging" : ""}`} {...handlers}>
      <span className="catalog-tracklist-index">{index + 1}</span>
      <Link href={catalogHref(item.id)} className="catalog-tracklist-title">{item.title}</Link>
      {!item.has_file && <span className="catalog-pill">{uploading ? "Загружаем…" : dragging ? <><UploadCloud size={12} />Отпустите</> : "Нет файла"}</span>}
      <span className="catalog-tracklist-time">{catalogDuration(item.duration_ms) ?? "—"}</span>
    </li>
  );
}
