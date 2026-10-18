"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { Artwork } from "@/components/Artwork";
import { CatalogAlbumCard } from "@/components/CatalogAlbumCard";
import { CatalogArtistCard, countText } from "@/components/CatalogArtistCard";
import { CatalogList } from "@/components/CatalogList";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import type { CatalogAlbum, CatalogArtist, CatalogTrack, SearchResult } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

const LIMIT = 20;

type CatalogSearch = { tracks: CatalogTrack[]; tracks_total: number; albums: CatalogAlbum[]; artists: CatalogArtist[] };
type Results = { query: string; catalog: CatalogSearch; library: SearchResult };

export function SearchClient({ query }: { query: string }) {
  const { user } = useAuth();
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState("");
  const latest = useRef(query);

  const load = useCallback(async () => {
    latest.current = query;
    if (!query) return;
    try {
      const params = new URLSearchParams({ q: query, limit: String(LIMIT) });
      const [catalog, library] = await Promise.all([
        api<CatalogSearch>(`/music/transfer/search?${params}`),
        api<SearchResult>(`/music/search?${params}`),
      ]);
      // Answers to letters typed earlier may arrive after the latest one.
      if (latest.current !== query) return;
      setResults({ query, catalog, library });
      setError("");
    } catch (caught) {
      if (latest.current === query) setError(caught instanceof Error ? caught.message : "Не удалось выполнить поиск");
    }
  }, [query]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the requests resolve
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  const shown = query && results ? results : null;
  const updateTrack = (updated: CatalogTrack) => setResults((current) => current && {
    ...current,
    catalog: { ...current.catalog, tracks: current.catalog.tracks.map((item) => item.id === updated.id ? updated : item) },
  });

  // Files linked to the catalog are shown through it; the rest of the library is listed on its own.
  const library = useMemo(() => {
    if (!shown) return null;
    const albums = new Set(shown.catalog.albums.flatMap((album) => album.local_album_ids));
    const artists = new Set(shown.catalog.artists.flatMap((artist) => artist.local_artist_ids));
    return {
      tracks: shown.library.tracks.filter((track) => !track.catalog),
      albums: shown.library.albums.filter((album) => !albums.has(album.id)),
      artists: shown.library.artists.filter((artist) => !artists.has(artist.id)),
    };
  }, [shown]);

  const total = shown && library
    ? shown.catalog.tracks_total + shown.catalog.albums.length + shown.catalog.artists.length + library.tracks.length + library.albums.length + library.artists.length
    : 0;
  const searching = Boolean(query) && results?.query !== query && !error;

  return (
    <div className="content-page search-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Поиск</div>
          <h1>{query ? `«${query}»` : "Найдите свою музыку"}</h1>
          <p>{!query ? "Начните вводить название трека, альбома или исполнителя в строке поиска." : searching ? "Ищем…" : "Треки, альбомы и исполнители каталога и ваших файлов"}</p>
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {query && !shown && !error && <PageLoader />}
      {shown && library && (
        <div className={searching ? "search-results stale" : "search-results"}>
          {total === 0 && <EmptyState title="Ничего не найдено" description="Попробуйте изменить запрос или проверьте написание." />}
          {!!shown.catalog.artists.length && (
            <section className="section">
              <div className="section-header"><h2 className="section-title">Исполнители</h2></div>
              <div className="artist-grid">{shown.catalog.artists.map((artist) => <CatalogArtistCard key={artist.key} artist={artist} />)}</div>
            </section>
          )}
          {!!shown.catalog.tracks.length && (
            <section className="section">
              <div className="section-header">
                <h2 className="section-title">Треки</h2>
                {shown.catalog.tracks_total > shown.catalog.tracks.length && (
                  <Link className="section-link" href={`/music/catalog?${new URLSearchParams({ view: "list", q: query })}`}>
                    Все {countText(shown.catalog.tracks_total, ["трек", "трека", "треков"])} в каталоге
                  </Link>
                )}
              </div>
              <CatalogList items={shown.catalog.tracks} canUpload={Boolean(user?.is_admin)} onUpdated={updateTrack} />
            </section>
          )}
          {!!shown.catalog.albums.length && (
            <section className="section">
              <div className="section-header"><h2 className="section-title">Альбомы</h2></div>
              <div className="catalog-grid">{shown.catalog.albums.map((album) => <CatalogAlbumCard key={album.key} album={album} />)}</div>
            </section>
          )}
          {!!library.tracks.length && (
            <section className="section">
              <div className="section-header"><h2 className="section-title">Файлы вне каталога</h2></div>
              <TrackTable tracks={library.tracks} compact onChanged={() => void load()} />
            </section>
          )}
          {!!library.albums.length && (
            <section className="section">
              <div className="section-header"><h2 className="section-title">Альбомы из файлов</h2></div>
              <div className="album-grid">{library.albums.map((album) => <AlbumCard key={album.id} album={album} />)}</div>
            </section>
          )}
          {!!library.artists.length && (
            <section className="section">
              <div className="section-header"><h2 className="section-title">Исполнители из файлов</h2></div>
              <div className="artist-grid">
                {library.artists.map((artist) => (
                  <Link className="artist-card" href={`/music/artists/${artist.id}`} key={artist.id}>
                    <div className="artist-art"><Artwork id={artist.artwork_id} alt={artist.name} size={256} /></div>
                    <div className="album-title">{artist.name}</div>
                    <div className="album-meta">{countText(artist.track_count, ["трек", "трека", "треков"])}</div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
