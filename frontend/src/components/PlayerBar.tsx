"use client";

import {
  Heart,
  ListMusic,
  Pause,
  Play,
  Repeat,
  Repeat1,
  Shuffle,
  SkipBack,
  SkipForward,
  Trash2,
  Volume1,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Artwork } from "@/components/Artwork";
import { api } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Track } from "@/lib/types";
import { usePlayer } from "@/providers/PlayerProvider";

export function PlayerBar() {
  const player = usePlayer();
  const [queueOpen, setQueueOpen] = useState(false);
  const favorite = async () => {
    if (!player.current) return;
    const updated = await api<Track>(`/music/tracks/${player.current.id}/favorite`, {
      method: player.current.favorite ? "DELETE" : "POST",
    });
    player.updateTrack(updated);
  };
  return (
    <>
      {queueOpen && (
        <div className="queue-drawer">
          <div className="queue-header">
            <div><h3>Очередь</h3><span className="track-subtitle">{player.queue.length} композиций</span></div>
            <div style={{ display: "flex" }}>
              <button className="icon-button small" onClick={player.clearQueue} aria-label="Очистить очередь"><Trash2 size={16} /></button>
              <button className="icon-button small" onClick={() => setQueueOpen(false)} aria-label="Закрыть очередь"><X size={17} /></button>
            </div>
          </div>
          <div className="queue-list">
            {player.queue.map((track, index) => (
              <div className={`queue-item ${index === player.currentIndex ? "current" : ""}`} key={`${track.id}-${index}`}>
                <button className="queue-item-art" onClick={() => player.playTrack(track, player.queue)} aria-label={`Воспроизвести ${track.title}`}>
                  <Artwork id={track.artwork_id} alt={track.title} size={64} />
                </button>
                <button className="action-item" style={{ display: "block" }} onClick={() => player.playTrack(track, player.queue)}>
                  <span className="track-title">{track.title}</span>
                  <span className="track-subtitle">{track.artist.name}</span>
                </button>
                <button className="icon-button small" onClick={() => player.removeFromQueue(index)} aria-label="Удалить из очереди"><X size={15} /></button>
              </div>
            ))}
            {!player.queue.length && <div className="empty-state" style={{ minHeight: 180 }}><div><p>Очередь пуста</p></div></div>}
          </div>
        </div>
      )}
      <footer className="player" aria-label="Музыкальный плеер">
        <div className="now-playing">
          <div className="now-art"><Artwork id={player.current?.artwork_id} alt={player.current?.title ?? "Нет трека"} size={64} /></div>
          <div className="now-copy">
            <div className="now-title">{player.current?.title ?? "Ничего не играет"}</div>
            {player.current ? (
              <Link className="now-artist" href={`/music/artists/${player.current.artist.id}`}>{player.current.artist.name}</Link>
            ) : <div className="now-artist">Выберите композицию</div>}
          </div>
          {player.current && (
            <button className={`icon-button small favorite-button ${player.current.favorite ? "active" : ""}`} onClick={() => void favorite()} aria-label="Избранное">
              <Heart size={16} fill={player.current.favorite ? "currentColor" : "none"} />
            </button>
          )}
        </div>
        <div className="player-center">
          <div className="player-controls">
            <button className={`icon-button secondary-control ${player.shuffle ? "active" : ""}`} onClick={player.toggleShuffle} aria-label="Перемешать"><Shuffle size={16} /></button>
            <button className="icon-button" onClick={player.previous} aria-label="Предыдущий трек"><SkipBack size={20} fill="currentColor" /></button>
            <button className="play-button" onClick={player.togglePlay} disabled={!player.current} aria-label={player.playing ? "Пауза" : "Воспроизвести"}>
              {player.playing ? <Pause size={19} fill="currentColor" /> : <Play size={19} fill="currentColor" style={{ marginLeft: 2 }} />}
            </button>
            <button className="icon-button" onClick={player.next} aria-label="Следующий трек"><SkipForward size={20} fill="currentColor" /></button>
            <button className={`icon-button secondary-control ${player.repeat !== "off" ? "active" : ""}`} onClick={player.cycleRepeat} aria-label={`Повтор: ${player.repeat}`}>
              {player.repeat === "one" ? <Repeat1 size={16} /> : <Repeat size={16} />}
            </button>
          </div>
          <div className="progress-line">
            <span>{formatTime(player.currentTime)}</span>
            <input
              className="range"
              type="range"
              min={0}
              max={Math.max(1, player.duration)}
              step={0.1}
              value={Math.min(player.currentTime, player.duration || 0)}
              onChange={(event) => player.seek(Number(event.target.value))}
              aria-label="Позиция воспроизведения"
            />
            <span>{formatTime(player.duration)}</span>
          </div>
        </div>
        <div className="player-right">
          <button className={`icon-button ${queueOpen ? "active" : ""}`} onClick={() => setQueueOpen((value) => !value)} aria-label="Очередь"><ListMusic size={18} /></button>
          <button className="icon-button" onClick={player.toggleMute} aria-label="Отключить звук">
            {player.muted || player.volume === 0 ? <VolumeX size={18} /> : player.volume < .5 ? <Volume1 size={18} /> : <Volume2 size={18} />}
          </button>
          <input className="volume-range" type="range" min={0} max={1} step={0.01} value={player.volume} onChange={(event) => player.setVolume(Number(event.target.value))} aria-label="Громкость" />
        </div>
      </footer>
    </>
  );
}
