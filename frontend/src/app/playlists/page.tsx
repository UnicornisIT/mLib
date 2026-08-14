"use client";

import { ChevronDown, ChevronUp, ListMusic, Plus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";
import { formatLongDuration } from "@/lib/format";
import type { Playlist } from "@/lib/types";
import { usePlayer } from "@/providers/PlayerProvider";
import { useFeedback } from "@/providers/FeedbackProvider";

export default function PlaylistsPage() {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selected, setSelected] = useState<Playlist | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const player = usePlayer();
  const feedback = useFeedback();
  const startCreating = () => {
    setError("");
    setCreating(true);
  };
  const load = useCallback(async () => {
    try {
      const list = await api<Playlist[]>("/music/playlists");
      setPlaylists(list);
      if (selected) {
        const match = list.find((item) => item.id === selected.id);
        if (match) setSelected(await api<Playlist>(`/music/playlists/${match.id}`));
        else setSelected(null);
      }
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить плейлисты");
    }
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // Data fetching is the external synchronization performed by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const open = async (playlist: Playlist) => {
    try {
      setSelected(await api<Playlist>(`/music/playlists/${playlist.id}`));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось открыть плейлист");
    }
  };
  const create = async () => {
    try {
      const playlist = await api<Playlist>("/music/playlists", { method: "POST", body: { name: name.trim(), description: description.trim() || null } });
      setCreating(false); setName(""); setDescription(""); setError("");
      await load(); await open(playlist);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать плейлист");
    }
  };
  const removePlaylist = async () => {
    if (!selected || !await feedback.confirm({ title: "Удалить плейлист?", message: `Плейлист «${selected.name}» будет удалён. Музыкальные файлы останутся в медиатеке.`, confirmLabel: "Удалить плейлист", destructive: true })) return;
    try {
      await api<void>(`/music/playlists/${selected.id}`, { method: "DELETE" });
      setSelected(null); await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить плейлист");
    }
  };
  const removeItem = async (itemId: string) => {
    if (!selected) return;
    try {
      setSelected(await api<Playlist>(`/music/playlists/${selected.id}/tracks/${itemId}`, { method: "DELETE" }));
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось удалить трек из плейлиста");
    }
  };
  const move = async (index: number, direction: -1 | 1) => {
    if (!selected?.items) return;
    const target = index + direction;
    if (target < 0 || target >= selected.items.length) return;
    const ids = selected.items.map((item) => item.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      setSelected(await api<Playlist>(`/music/playlists/${selected.id}/tracks/reorder`, { method: "PUT", body: { item_ids: ids } }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить порядок треков");
    }
  };
  return (
    <div className="content-page">
      <div className="page-heading"><div><div className="eyebrow">Моя коллекция</div><h1>Плейлисты</h1><p>Собирайте музыку для любого настроения</p></div><button className="button primary" onClick={startCreating}><Plus size={17} />Создать плейлист</button></div>
      {!creating && error && <div className="form-error" role="alert">{error}</div>}
      {!playlists.length ? <EmptyState title="Первый плейлист — с чистого листа" description="Создайте подборку и добавляйте треки через меню любой композиции." action={<button className="button primary" onClick={startCreating}>Создать плейлист</button>} /> : (
        <div className="playlist-layout">
          <div className="playlist-sidebar">{playlists.map((playlist) => <button className={`playlist-choice ${selected?.id === playlist.id ? "active" : ""}`} key={playlist.id} onClick={() => void open(playlist)}><span><strong>{playlist.name}</strong><span>{playlist.track_count} треков</span></span><ListMusic size={17} /></button>)}</div>
          <div>
            {!selected && <EmptyState title="Выберите плейлист" description="Композиции выбранной подборки появятся здесь." />}
            {selected && <><div className="section-header"><div><h2 className="section-title">{selected.name}</h2><div className="album-meta">{selected.track_count} треков · {formatLongDuration(selected.duration)}</div></div><div className="page-actions"><button className="button primary" disabled={!selected.items?.length} onClick={() => selected.items?.[0] && player.playTrack(selected.items[0].track, selected.items.map((item) => item.track))}>Слушать</button><button className="icon-button" onClick={() => void removePlaylist()} aria-label="Удалить плейлист"><Trash2 size={17} /></button></div></div>
              {selected.items?.length ? <div className="table-shell">{selected.items.map((item, index) => <div className="track-row" style={{ gridTemplateColumns: "42px minmax(0, 1fr) 110px 100px" }} key={item.id}><span className="track-index">{index + 1}</span><button className="track-main" style={{ border: 0, background: "none", textAlign: "left", cursor: "pointer" }} onClick={() => player.playTrack(item.track, selected.items!.map((value) => value.track))}><span className="track-art"><Artwork id={item.track.artwork_id} alt={item.track.title} size={64} /></span><span className="track-copy"><span className="track-title">{item.track.title}</span><span className="track-subtitle">{item.track.artist.name}</span></span></button><span><button className="icon-button small" disabled={index === 0} onClick={() => void move(index, -1)}><ChevronUp size={15} /></button><button className="icon-button small" disabled={index === selected.items!.length - 1} onClick={() => void move(index, 1)}><ChevronDown size={15} /></button></span><button className="button ghost danger" onClick={() => void removeItem(item.id)}>Удалить</button></div>)}</div> : <EmptyState title="Плейлист пуст" description="Откройте меню трека и выберите «Добавить в плейлист»." />}
            </>}
          </div>
        </div>
      )}
      {creating && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setCreating(false)}><div className="modal" style={{ width: 470 }} role="dialog" aria-modal="true" aria-labelledby="playlist-create-title"><div className="modal-header"><h2 id="playlist-create-title">Новый плейлист</h2><button className="icon-button" type="button" onClick={() => setCreating(false)} aria-label="Закрыть"><X size={18} /></button></div><div className="modal-body"><div className="field"><label htmlFor="playlist-name">Название</label><input id="playlist-name" className="input" autoFocus maxLength={255} value={name} onChange={(event) => setName(event.target.value)} /></div><div className="field"><label htmlFor="playlist-description">Описание</label><textarea id="playlist-description" className="textarea" maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></div>{error && <div className="form-error" role="alert">{error}</div>}<div className="form-actions"><button className="button" type="button" onClick={() => setCreating(false)}>Отмена</button><button className="button primary" type="button" disabled={!name.trim()} onClick={() => void create()}>Создать</button></div></div></div></div>}
    </div>
  );
}
