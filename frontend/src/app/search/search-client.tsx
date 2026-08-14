"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { Artwork } from "@/components/Artwork";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export function SearchClient({ query }: { query: string }) {
  const [result, setResult] = useState<SearchResult | null>(() => query ? null : { tracks: [], albums: [], artists: [] });
  useEffect(() => {
    if (query) void api<SearchResult>(`/music/search?q=${encodeURIComponent(query)}&limit=20`).then(setResult);
  }, [query]);
  const empty = result && !result.tracks.length && !result.albums.length && !result.artists.length;
  return (
    <div className="content-page">
      <div className="page-heading"><div><div className="eyebrow">Поиск</div><h1>{query ? `«${query}»` : "Найдите свою музыку"}</h1><p>Треки, альбомы и исполнители в вашей коллекции</p></div></div>
      {!result && <PageLoader />}
      {empty && <EmptyState title="Ничего не найдено" description="Попробуйте изменить запрос или проверьте написание." />}
      {!!result?.tracks.length && <section><div className="section-header"><h2 className="section-title">Композиции</h2></div><TrackTable tracks={result.tracks} compact /></section>}
      {!!result?.albums.length && <section className="section"><div className="section-header"><h2 className="section-title">Альбомы</h2></div><div className="album-grid">{result.albums.map((album) => <AlbumCard key={album.id} album={album} />)}</div></section>}
      {!!result?.artists.length && <section className="section"><div className="section-header"><h2 className="section-title">Исполнители</h2></div><div className="artist-grid">{result.artists.map((artist) => <Link className="artist-card" href={`/music/artists/${artist.id}`} key={artist.id}><div className="artist-art"><Artwork id={artist.artwork_id} alt={artist.name} size={256} /></div><div className="album-title">{artist.name}</div><div className="album-meta">{artist.track_count} треков</div></Link>)}</div></section>}
    </div>
  );
}
