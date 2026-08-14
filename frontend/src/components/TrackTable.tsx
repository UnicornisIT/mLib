"use client";

import {
  CircleCheck,
  Heart,
  ListEnd,
  ListPlus,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  Plus,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Artwork } from "@/components/Artwork";
import { GenreCombobox } from "@/components/GenreCombobox";
import { api } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import { metadataIssueText } from "@/lib/metadata-quality";
import type { Playlist, Track } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";
import { usePlayer } from "@/providers/PlayerProvider";

export function TrackTable({
  tracks,
  onChanged,
  compact = false,
  startIndex = 0,
}: {
  tracks: Track[];
  onChanged?: () => void;
  compact?: boolean;
  startIndex?: number;
}) {
  const player = usePlayer();
  const feedback = useFeedback();
  const [menu, setMenu] = useState<string | null>(null);
  const [editing, setEditing] = useState<Track | null>(null);
  const [playlistTrack, setPlaylistTrack] = useState<Track | null>(null);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [overrides, setOverrides] = useState<Record<string, Track>>({});
  const displayTracks = tracks.map((track) => overrides[track.id] ?? track);

  const toggleFavorite = async (track: Track) => {
    const updated = await api<Track>(`/music/tracks/${track.id}/favorite`, { method: track.favorite ? "DELETE" : "POST" });
    setOverrides((values) => ({ ...values, [track.id]: updated }));
    player.updateTrack(updated);
  };
  const remove = async (track: Track) => {
    const accepted = await feedback.confirm({
      title: "Удалить трек?",
      message: `«${track.title}» будет удалён из медиатеки вместе с исходным файлом. Это действие нельзя отменить.`,
      confirmLabel: "Удалить трек",
      destructive: true,
    });
    if (!accepted) return;
    try {
      await api<void>(`/music/tracks/${track.id}`, { method: "DELETE" });
      setMenu(null);
      feedback.notify("Трек удалён из медиатеки");
      onChanged?.();
    } catch (error) {
      feedback.notify(error instanceof Error ? error.message : "Не удалось удалить трек", "error");
    }
  };
  const choosePlaylist = async (track: Track) => {
    setMenu(null);
    setPlaylistTrack(track);
    setPlaylists(await api<Playlist[]>("/music/playlists"));
  };
  const addToPlaylist = async (playlist: Playlist) => {
    if (!playlistTrack) return;
    await api<Playlist>(`/music/playlists/${playlist.id}/tracks`, { method: "POST", body: { track_id: playlistTrack.id } });
    setPlaylistTrack(null);
    feedback.notify(`Трек добавлен в «${playlist.name}»`);
  };
  const markMetadataReviewed = async (track: Track) => {
    const updated = await api<Track>(`/music/tracks/${track.id}/metadata-reviewed`, { method: "POST" });
    setOverrides((values) => ({ ...values, [track.id]: updated }));
    setMenu(null);
    window.dispatchEvent(new Event("mlib:library-changed"));
    onChanged?.();
  };

  return (
    <>
      <div className="table-shell">
        {!compact && (
          <div className="track-header">
            <span title="Позиция в текущем списке">#</span><span>Композиция</span><span className="track-col-album">Альбом</span>
            <span className="track-col-genre">Жанр</span><span className="track-col-date">Добавлено</span><span>Время</span><span />
          </div>
        )}
        {displayTracks.map((track, index) => {
          const isCurrent = player.current?.id === track.id;
          return (
            <div className={`track-row ${isCurrent ? "current" : ""}`} key={track.id}>
              <div className="track-index">
                <span className="track-index-number">{startIndex + index + 1}</span>
                <button className="icon-button small row-play" onClick={() => isCurrent ? player.togglePlay() : player.playTrack(track, displayTracks)} aria-label={`Воспроизвести ${track.title}`}>
                  {isCurrent && player.playing ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                </button>
              </div>
              <div className="track-main">
                <div className="track-art"><Artwork id={track.artwork_id} alt={track.title} size={64} /></div>
                <div className="track-copy">
                  <div className="track-title-line">
                    {track.needs_attention && (
                      <button
                        className={`metadata-alert ${track.metadata_status}`}
                        type="button"
                        aria-label={`Требует внимания: ${metadataIssueText(track.metadata_issues)}`}
                        title={metadataIssueText(track.metadata_issues)}
                        onClick={() => setEditing(track)}
                      >
                        <span aria-hidden="true">!</span>
                      </button>
                    )}
                    <button className="track-title" style={{ border: 0, padding: 0, background: "none", cursor: "pointer" }} onDoubleClick={() => player.playTrack(track, displayTracks)}>{track.title}</button>
                  </div>
                  <Link className="track-subtitle" href={`/music/artists/${track.artist.id}`}>{track.artist.name}</Link>
                </div>
              </div>
              <div className="track-col-album truncate">
                {track.album ? <Link className="track-link" href={`/music/albums/${track.album.id}`}>{track.album.title}</Link> : <span className="track-link">—</span>}
              </div>
              <span className="track-col-genre truncate" style={{ color: "var(--muted)" }}>{track.genre ?? "—"}</span>
              <span className="track-col-date" style={{ color: "var(--muted)" }}>{formatDate(track.date_added)}</span>
              <div className="track-time" style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 2 }}>
                <button className={`icon-button small favorite-button ${track.favorite ? "active" : ""}`} onClick={() => void toggleFavorite(track)} aria-label="Избранное">
                  <Heart size={14} fill={track.favorite ? "currentColor" : "none"} />
                </button>
                {formatTime(track.duration)}
              </div>
              <div className="menu-wrap">
                <button className="icon-button small" onClick={() => setMenu(menu === track.id ? null : track.id)} aria-label="Действия"><MoreHorizontal size={17} /></button>
                {menu === track.id && (
                  <div className="action-menu">
                    <button className="action-item" onClick={() => { player.playTrack(track, displayTracks); setMenu(null); }}><Play size={15} />Воспроизвести</button>
                    <button className="action-item" onClick={() => { player.addNext(track); setMenu(null); }}><ListPlus size={15} />Воспроизвести следующим</button>
                    <button className="action-item" onClick={() => { player.addToQueue(track); setMenu(null); }}><ListEnd size={15} />Добавить в очередь</button>
                    <button className="action-item" onClick={() => void choosePlaylist(track)}><Plus size={15} />Добавить в плейлист</button>
                    <button className="action-item" onClick={() => void toggleFavorite(track).then(() => setMenu(null))}><Heart size={15} />{track.favorite ? "Убрать из любимых" : "Добавить в любимые"}</button>
                    <button className="action-item" onClick={() => { setEditing(track); setMenu(null); }}><Pencil size={15} />Редактировать</button>
                    {track.needs_attention && <button className="action-item" onClick={() => void markMetadataReviewed(track)}><CircleCheck size={15} />Метаданные верны</button>}
                    <button className="action-item danger" onClick={() => void remove(track)}><Trash2 size={15} />Удалить из библиотеки</button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {editing && <EditTrackDialog track={editing} onClose={() => setEditing(null)} onSaved={(updated) => {
        setOverrides((values) => ({ ...values, [updated.id]: updated }));
        player.updateTrack(updated);
        setEditing(null);
        window.dispatchEvent(new Event("mlib:library-changed"));
        onChanged?.();
      }} />}
      {playlistTrack && (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setPlaylistTrack(null)}>
          <div className="modal" style={{ width: 430 }} role="dialog" aria-modal="true">
            <div className="modal-header"><h2>Добавить в плейлист</h2><button className="icon-button" onClick={() => setPlaylistTrack(null)}><X size={18} /></button></div>
            <div className="modal-body">
              <div className="nav-group">
                {playlists.map((playlist) => (
                  <button key={playlist.id} className="playlist-choice" onClick={() => void addToPlaylist(playlist)}>
                    <span><strong>{playlist.name}</strong><span>{playlist.track_count} треков</span></span><Plus size={17} />
                  </button>
                ))}
              </div>
              {!playlists.length && <p style={{ color: "var(--muted)" }}>Сначала создайте плейлист на странице «Плейлисты».</p>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function EditTrackDialog({ track, onClose, onSaved }: { track: Track; onClose: () => void; onSaved: (track: Track) => void }) {
  const [values, setValues] = useState({
    title: track.title,
    artist: track.artist.name,
    album: track.album?.title ?? "",
    album_artist: track.album_artist ?? "",
    genre: track.genre ?? "",
    year: track.year?.toString() ?? "",
    track_number: track.track_number?.toString() ?? "",
    disc_number: track.disc_number?.toString() ?? "",
  });
  const [error, setError] = useState("");
  const save = async () => {
    try {
      const number = (value: string) => value ? Number(value) : null;
      const updated = await api<Track>(`/music/tracks/${track.id}`, {
        method: "PATCH",
        body: {
          ...values,
          album: values.album || null,
          album_artist: values.album_artist || null,
          genre: values.genre || null,
          year: number(values.year),
          track_number: number(values.track_number),
          disc_number: number(values.disc_number),
        },
      });
      onSaved(updated);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить изменения");
    }
  };
  const field = (key: keyof typeof values, label: string, type = "text") => (
    <label className="field"><span>{label}</span><input className="input" type={type} value={values[key]} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>
  );
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">
        <div className="modal-header"><h2>Информация о треке</h2><button className="icon-button" onClick={onClose}><X size={18} /></button></div>
        <div className="modal-body">
          {track.needs_attention && (
            <div className={`metadata-review-banner ${track.metadata_status}`}>
              <TriangleAlert size={18} />
              <div><strong>Проверьте метаданные</strong><span>{metadataIssueText(track.metadata_issues)}</span></div>
            </div>
          )}
          {field("title", "Название")}{field("artist", "Исполнитель")}{field("album", "Альбом")}{field("album_artist", "Исполнитель альбома")}
          <GenreCombobox value={values.genre} onChange={(genre) => setValues({ ...values, genre })} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {field("year", "Год", "number")}{field("track_number", "№ в альбоме", "number")}{field("disc_number", "№ диска", "number")}
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="form-actions"><button className="button" onClick={onClose}>Отмена</button><button className="button primary" onClick={() => void save()}>Сохранить</button></div>
        </div>
      </div>
    </div>
  );
}
