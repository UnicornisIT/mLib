"use client";

import { Album as AlbumIcon, Clock3, Disc3, Music2, Plus, UsersRound } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import { formatLongDuration } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function MusicHomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api<Dashboard>("/music/dashboard").then(setData).catch((caught) => setError(caught.message)), []);
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(load);
  return (
    <div className="content-page music-page">
      {!data && !error && <PageLoader rows={7} />}
      {error && <div className="form-error">{error}</div>}
      {data && data.tracks === 0 && (
        <div className="hero">
          <div className="hero-main">
            <div className="eyebrow">musicLib · Ваша новая медиатека</div>
            <h1>Музыка, которая принадлежит вам.</h1>
            <p>Добавьте первые аудиофайлы — mLib прочитает теги, найдёт альбомы и исполнителей и сразу подготовит всё к прослушиванию.</p>
            <div style={{ marginTop: 22, position: "relative", zIndex: 1 }}>
              <button className="button primary" onClick={() => window.dispatchEvent(new Event("mlib:open-upload"))}><Plus size={17} />Добавить первую музыку</button>
            </div>
          </div>
          <div className="hero-side">
            <div className="stat-card"><Music2 size={20} /><div><div className="stat-value">0</div><div className="stat-label">треков</div></div></div>
            <div className="stat-card"><AlbumIcon size={20} /><div><div className="stat-value">0</div><div className="stat-label">альбомов</div></div></div>
            <div className="stat-card"><UsersRound size={20} /><div><div className="stat-value">0</div><div className="stat-label">исполнителей</div></div></div>
            <div className="stat-card"><Clock3 size={20} /><div><div className="stat-value">—</div><div className="stat-label">время музыки</div></div></div>
          </div>
        </div>
      )}
      {data && data.tracks > 0 && (
        <>
          <div className="page-heading"><div><div className="eyebrow">musicLib · Ваша медиатека</div><h1>Снова к музыке.</h1><p>{formatLongDuration(data.duration)} музыки в коллекции</p></div></div>
          <div className="hero-side" style={{ marginBottom: 38 }}>
            <div className="stat-card"><Music2 size={20} /><div><div className="stat-value">{data.tracks}</div><div className="stat-label">треков</div></div></div>
            <div className="stat-card"><AlbumIcon size={20} /><div><div className="stat-value">{data.albums}</div><div className="stat-label">альбомов</div></div></div>
            <div className="stat-card"><UsersRound size={20} /><div><div className="stat-value">{data.artists}</div><div className="stat-label">исполнителей</div></div></div>
            <div className="stat-card"><Disc3 size={20} /><div><div className="stat-value">{data.genres}</div><div className="stat-label">жанров</div></div></div>
          </div>
          <section className="section">
            <div className="section-header"><h2 className="section-title">Недавно добавленные</h2><Link className="section-link" href="/music/tracks">Все треки</Link></div>
            <TrackTable tracks={data.recently_added.slice(0, 8)} compact onChanged={load} />
          </section>
          {!!data.albums_recent.length && <section className="section"><div className="section-header"><h2 className="section-title">Альбомы</h2><Link className="section-link" href="/music/albums">Смотреть все</Link></div><div className="album-grid">{data.albums_recent.map((album) => <AlbumCard key={album.id} album={album} />)}</div></section>}
          {!!data.recently_played.length && <section className="section"><div className="section-header"><h2 className="section-title">Недавно слушали</h2></div><TrackTable tracks={data.recently_played.slice(0, 8)} compact onChanged={load} /></section>}
        </>
      )}
    </div>
  );
}
