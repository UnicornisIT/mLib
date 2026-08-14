"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";
import type { ArtistPage } from "@/lib/types";

export default function ArtistsPage() {
  const [data, setData] = useState<ArtistPage | null>(null);
  useEffect(() => { void api<ArtistPage>("/music/artists?page_size=100").then(setData); }, []);
  return <div className="content-page"><div className="page-heading"><div><div className="eyebrow">Коллекция</div><h1>Исполнители</h1><p>{data ? `${data.total} исполнителей` : "Загрузка…"}</p></div></div>{data && !data.items.length ? <EmptyState title="Исполнителей пока нет" description="Они появятся автоматически после добавления музыки." /> : <div className="artist-grid">{data?.items.map((artist) => <Link href={`/music/artists/${artist.id}`} className="artist-card" key={artist.id}><div className="artist-art"><Artwork id={artist.artwork_id} alt={artist.name} size={256} /></div><div className="album-title">{artist.name}</div><div className="album-meta">{artist.album_count} альбомов · {artist.track_count} треков</div></Link>)}</div>}</div>;
}
