"use client";

import { Play } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { Artwork } from "@/components/Artwork";
import { PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { api } from "@/lib/api";
import type { ArtistDetail } from "@/lib/types";
import { usePlayer } from "@/providers/PlayerProvider";

export default function ArtistPage() {
  const { id } = useParams<{ id: string }>();
  const [artist, setArtist] = useState<ArtistDetail | null>(null);
  const player = usePlayer();
  const load = () => api<ArtistDetail>(`/music/artists/${id}`).then(setArtist);
  useEffect(() => { void load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!artist) return <div className="content-page"><PageLoader /></div>;
  return <div className="content-page"><div className="detail-hero"><div className="detail-art artist-avatar"><Artwork id={artist.artwork_id} alt={artist.name} size={512} /></div><div className="detail-copy"><div className="eyebrow">Исполнитель</div><h1>{artist.name}</h1><p>{artist.album_count} альбомов · {artist.track_count} композиций</p><div className="detail-actions"><button className="button primary" onClick={() => artist.tracks[0] && player.playTrack(artist.tracks[0], artist.tracks)}><Play size={17} fill="currentColor" />Слушать</button></div></div></div>{!!artist.tracks.length && <section><div className="section-header"><h2 className="section-title">Популярные композиции</h2></div><TrackTable tracks={artist.tracks.slice(0, 10)} compact onChanged={() => void load()} /></section>}{!!artist.albums.length && <section className="section"><div className="section-header"><h2 className="section-title">Альбомы</h2></div><div className="album-grid">{artist.albums.map((album) => <AlbumCard album={album} key={album.id} />)}</div></section>}</div>;
}

