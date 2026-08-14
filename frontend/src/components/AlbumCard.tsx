"use client";

import { Play } from "lucide-react";
import Link from "next/link";
import { Artwork } from "@/components/Artwork";
import { api } from "@/lib/api";
import type { Album, AlbumDetail } from "@/lib/types";
import { usePlayer } from "@/providers/PlayerProvider";

export function AlbumCard({ album }: { album: Album }) {
  const player = usePlayer();
  const play = async () => {
    const detail = await api<AlbumDetail>(`/music/albums/${album.id}`);
    if (detail.tracks[0]) player.playTrack(detail.tracks[0], detail.tracks);
  };
  return (
    <article className="album-card">
      <div className="album-art-wrap">
        <Link href={`/music/albums/${album.id}`} aria-label={album.title}><Artwork id={album.artwork_id} alt={album.title} size={256} /></Link>
        <button className="album-play" onClick={() => void play()} aria-label={`Воспроизвести альбом ${album.title}`}><Play size={20} fill="currentColor" /></button>
      </div>
      <Link href={`/music/albums/${album.id}`} className="album-title">{album.title}</Link>
      <div className="album-meta">{album.album_artist}{album.year ? ` · ${album.year}` : ""}</div>
    </article>
  );
}
