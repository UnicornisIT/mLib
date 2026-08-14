"use client";

import { Play, Shuffle } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { api } from "@/lib/api";
import { formatLongDuration } from "@/lib/format";
import type { AlbumDetail } from "@/lib/types";
import { usePlayer } from "@/providers/PlayerProvider";

export default function AlbumPage() {
  const { id } = useParams<{ id: string }>();
  const [album, setAlbum] = useState<AlbumDetail | null>(null);
  const player = usePlayer();
  useEffect(() => { void api<AlbumDetail>(`/music/albums/${id}`).then(setAlbum); }, [id]);
  if (!album) return <div className="content-page"><PageLoader /></div>;
  return <div className="content-page"><div className="detail-hero"><div className="detail-art"><Artwork id={album.artwork_id} alt={album.title} size={512} /></div><div className="detail-copy"><div className="eyebrow">Альбом</div><h1>{album.title}</h1><p>{album.album_artist}{album.year ? ` · ${album.year}` : ""}{album.genre ? ` · ${album.genre}` : ""} · {album.track_count} треков · {formatLongDuration(album.duration)}</p><div className="detail-actions"><button className="button primary" onClick={() => album.tracks[0] && player.playTrack(album.tracks[0], album.tracks)}><Play size={17} fill="currentColor" />Слушать</button><button className="button" onClick={() => { player.toggleShuffle(); if (album.tracks[0]) player.playTrack(album.tracks[0], album.tracks); }}><Shuffle size={16} />Перемешать</button></div></div></div><TrackTable tracks={album.tracks} onChanged={() => void api<AlbumDetail>(`/music/albums/${id}`).then(setAlbum)} /></div>;
}

