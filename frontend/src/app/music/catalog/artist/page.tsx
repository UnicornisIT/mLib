"use client";

import { ArrowLeft, Play } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { CatalogAlbumCard } from "@/components/CatalogAlbumCard";
import { countText } from "@/components/CatalogArtistCard";
import { CatalogHero } from "@/components/CatalogHero";
import { CatalogList } from "@/components/CatalogList";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import { catalogArtworkSource } from "@/lib/catalog";
import type { CatalogArtistDetail, CatalogTrack, Track } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";
import { usePlayer } from "@/providers/PlayerProvider";

export default function CatalogArtistPage() {
  return <Suspense fallback={<div className="content-page"><PageLoader rows={6} /></div>}><CatalogArtist /></Suspense>;
}

function CatalogArtist() {
  const key = useSearchParams().get("key") ?? "";
  const { user } = useAuth();
  const player = usePlayer();
  const [artist, setArtist] = useState<CatalogArtistDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const detail = await api<CatalogArtistDetail>(`/music/transfer/artist?${new URLSearchParams({ key })}`);
      setArtist(detail);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить исполнителя");
    }
  }, [key]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the request resolves
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  const update = (updated: CatalogTrack) => setArtist((current) => current && { ...current, tracks: current.tracks.map((item) => item.id === updated.id ? updated : item) });

  if (error && !artist) {
    return <div className="content-page"><EmptyState title="Исполнитель не найден" description={error} action={<Link className="button" href="/music/artists" style={{ marginTop: 16 }}>К исполнителям</Link>} /></div>;
  }
  if (!artist) return <div className="content-page"><PageLoader rows={6} /></div>;

  const withFile = artist.tracks.filter((item) => item.track_id);
  const playAll = async () => {
    const tracks = await Promise.all(withFile.map((item) => api<Track>(`/music/tracks/${item.track_id}`)));
    if (tracks[0]) player.playTrack(tracks[0], tracks);
  };

  return (
    <div className="content-page catalog-detail">
      <Link className="catalog-back" href="/music/artists"><ArrowLeft size={15} />Исполнители</Link>
      <CatalogHero round source={catalogArtworkSource(artist, 64)} art={<Artwork id={artist.artwork_id} url={artist.artwork_url} alt={artist.name} size={512} />}>
        <div className="eyebrow">Исполнитель</div>
        <h1>{artist.name}</h1>
        <p className="catalog-hero-meta">
          <span>{countText(artist.album_count, ["альбом", "альбома", "альбомов"])}</span>
          <span>{countText(artist.track_count, ["трек", "трека", "треков"])} в каталоге</span>
          {withFile.length < artist.track_count && <span className="catalog-pill">Без файла: {artist.track_count - withFile.length}</span>}
        </p>
        <div className="catalog-actions">
          {withFile.length > 0 && <button className="button primary" type="button" onClick={() => void playAll()}><Play size={17} fill="currentColor" />Слушать</button>}
        </div>
      </CatalogHero>
      {!!artist.albums.length && (
        <section className="section">
          <div className="section-header"><h2 className="section-title">Альбомы</h2></div>
          <div className="catalog-grid" aria-label="Альбомы исполнителя">
            {artist.albums.map((album) => <CatalogAlbumCard key={album.key} album={album} />)}
          </div>
        </section>
      )}
      <section className="section">
        <div className="section-header"><h2 className="section-title">Треки</h2></div>
        <CatalogList items={artist.tracks} canUpload={Boolean(user?.is_admin)} onUpdated={update} />
      </section>
    </div>
  );
}
