"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, streamUrl } from "@/lib/api";
import type { Track } from "@/lib/types";

export type RepeatMode = "off" | "all" | "one";
type PlayerContextValue = {
  queue: Track[];
  current: Track | null;
  currentIndex: number;
  playing: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  muted: boolean;
  shuffle: boolean;
  repeat: RepeatMode;
  playTrack: (track: Track, context?: Track[]) => void;
  togglePlay: () => void;
  next: () => void;
  previous: () => void;
  seek: (seconds: number) => void;
  setVolume: (value: number) => void;
  toggleMute: () => void;
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  addNext: (track: Track) => void;
  addToQueue: (track: Track) => void;
  removeFromQueue: (index: number) => void;
  moveQueueItem: (from: number, to: number) => void;
  clearQueue: () => void;
  updateTrack: (track: Track) => void;
};

const PlayerContext = createContext<PlayerContextValue | null>(null);

type SavedPlayer = {
  queue?: Track[];
  index?: number;
  volume?: number;
  shuffle?: boolean;
  repeat?: RepeatMode;
};

function readSavedPlayer(): SavedPlayer {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem("mlib-player") ?? "{}") as SavedPlayer;
  } catch {
    return {};
  }
}

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const recordedTrack = useRef<string | null>(null);
  const [queue, setQueue] = useState<Track[]>(() => readSavedPlayer().queue?.slice(0, 500) ?? []);
  const [currentIndex, setCurrentIndex] = useState(() => readSavedPlayer().index ?? -1);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(() => readSavedPlayer().volume ?? 0.8);
  const [muted, setMuted] = useState(false);
  const [shuffle, setShuffle] = useState(() => readSavedPlayer().shuffle ?? false);
  const [repeat, setRepeat] = useState<RepeatMode>(() => readSavedPlayer().repeat ?? "off");
  const current = currentIndex >= 0 ? queue[currentIndex] ?? null : null;

  useEffect(() => {
    localStorage.setItem("mlib-player", JSON.stringify({ queue, index: currentIndex, volume, shuffle, repeat }));
  }, [currentIndex, queue, repeat, shuffle, volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !current) return;
    audio.src = streamUrl(current.id);
    audio.load();
    recordedTrack.current = null;
    setCurrentTime(0);
    setDuration(current.duration);
    if (playing) void audio.play().catch(() => setPlaying(false));
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume;
      audioRef.current.muted = muted;
    }
  }, [muted, volume]);

  const playTrack = useCallback((track: Track, context?: Track[]) => {
    if (context?.length) {
      const index = context.findIndex((item) => item.id === track.id);
      setQueue(context);
      setCurrentIndex(index >= 0 ? index : 0);
    } else {
      setQueue((existing) => {
        const index = existing.findIndex((item) => item.id === track.id);
        if (index >= 0) setCurrentIndex(index);
        else {
          setCurrentIndex(existing.length);
          return [...existing, track];
        }
        return existing;
      });
    }
    setPlaying(true);
  }, []);

  const next = useCallback(() => {
    if (!queue.length) return;
    if (shuffle && queue.length > 1) {
      let index = currentIndex;
      while (index === currentIndex) index = Math.floor(Math.random() * queue.length);
      setCurrentIndex(index);
      setPlaying(true);
      return;
    }
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setPlaying(true);
    } else if (repeat === "all") {
      setCurrentIndex(0);
      setPlaying(true);
    } else setPlaying(false);
  }, [currentIndex, queue.length, repeat, shuffle]);

  const previous = useCallback(() => {
    const audio = audioRef.current;
    if (audio && audio.currentTime > 4) {
      audio.currentTime = 0;
      return;
    }
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setPlaying(true);
    } else if (repeat === "all" && queue.length) {
      setCurrentIndex(queue.length - 1);
      setPlaying(true);
    }
  }, [currentIndex, queue.length, repeat]);

  const value = useMemo<PlayerContextValue>(
    () => ({
      queue,
      current,
      currentIndex,
      playing,
      currentTime,
      duration,
      volume,
      muted,
      shuffle,
      repeat,
      playTrack,
      togglePlay: () => {
        const audio = audioRef.current;
        if (!audio || !current) return;
        if (audio.paused) void audio.play();
        else audio.pause();
      },
      next,
      previous,
      seek: (seconds) => {
        if (audioRef.current) audioRef.current.currentTime = seconds;
      },
      setVolume: (nextVolume) => setVolumeState(Math.min(1, Math.max(0, nextVolume))),
      toggleMute: () => setMuted((value) => !value),
      toggleShuffle: () => setShuffle((value) => !value),
      cycleRepeat: () => setRepeat((value) => (value === "off" ? "all" : value === "all" ? "one" : "off")),
      addNext: (track) =>
        setQueue((items) => {
          const nextQueue = [...items];
          nextQueue.splice(Math.max(0, currentIndex + 1), 0, track);
          return nextQueue;
        }),
      addToQueue: (track) => setQueue((items) => [...items, track]),
      removeFromQueue: (index) => {
        setQueue((items) => items.filter((_, itemIndex) => itemIndex !== index));
        if (index < currentIndex) setCurrentIndex((value) => value - 1);
        else if (index === currentIndex) setPlaying(false);
      },
      moveQueueItem: (from, to) =>
        setQueue((items) => {
          const nextQueue = [...items];
          const [item] = nextQueue.splice(from, 1);
          nextQueue.splice(to, 0, item);
          if (currentIndex === from) setCurrentIndex(to);
          return nextQueue;
        }),
      clearQueue: () => {
        setQueue([]);
        setCurrentIndex(-1);
        setPlaying(false);
      },
      updateTrack: (track) => setQueue((items) => items.map((item) => item.id === track.id ? track : item)),
    }),
    [
      current,
      currentIndex,
      currentTime,
      duration,
      muted,
      next,
      playTrack,
      playing,
      previous,
      queue,
      repeat,
      shuffle,
      volume,
    ],
  );

  return (
    <PlayerContext.Provider value={value}>
      {children}
      <audio
        ref={audioRef}
        preload="metadata"
        onPlay={() => {
          setPlaying(true);
          if (current && recordedTrack.current !== current.id) {
            recordedTrack.current = current.id;
            void api<void>(`/music/tracks/${current.id}/played`, { method: "POST" }).catch(() => undefined);
          }
        }}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onDurationChange={(event) => setDuration(event.currentTarget.duration || current?.duration || 0)}
        onEnded={() => {
          if (repeat === "one" && audioRef.current) {
            audioRef.current.currentTime = 0;
            void audioRef.current.play();
          } else next();
        }}
      />
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const context = useContext(PlayerContext);
  if (!context) throw new Error("usePlayer must be used inside PlayerProvider");
  return context;
}
