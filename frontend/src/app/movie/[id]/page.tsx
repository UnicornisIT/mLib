"use client";

import { ArrowLeft, Check, Clapperboard, FileVideo2, ListX, Play, Star, UploadCloud } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PageLoader } from "@/components/EmptyState";
import { EpisodeTracker } from "@/components/EpisodeTracker";
import { MovieUploadDialog } from "@/components/MovieUploadDialog";
import { PersonFilmographyDialog } from "@/components/PersonFilmographyDialog";
import { api, movieStreamUrl } from "@/lib/api";
import { formatBytes, formatLongDuration } from "@/lib/format";
import type {
  CreditPerson,
  MediaTitleDetail,
  MovieFile,
  MovieProgress,
  MovieTrackingStatus,
  SeriesTrackingStatus,
  TitleTracking,
} from "@/lib/types";

const seriesStatuses: Array<{ value: SeriesTrackingStatus; label: string }> = [
  { value: "watching", label: "Смотрю" },
  { value: "planned", label: "Буду смотреть" },
  { value: "completed", label: "Посмотрел" },
  { value: "dropped", label: "Перестал" },
];

const movieStatuses: Array<{ value: MovieTrackingStatus; label: string }> = [
  { value: "watched", label: "Посмотрел" },
  { value: "planned", label: "Буду смотреть" },
];

export default function MovieDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const requestedFile = searchParams.get("file");
  const [title, setTitle] = useState<MediaTitleDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(requestedFile);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedPerson, setSelectedPerson] = useState<CreditPerson | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const lastSaved = useRef(0);
  const loadedTitleId = useRef<string | null>(null);
  const loadRequest = useRef(0);

  const loadTitle = useCallback(() => {
    const requestId = ++loadRequest.current;
    return api<MediaTitleDetail>(`/movie/titles/${id}`).then((data) => {
      if (requestId !== loadRequest.current) return;
      const requested = requestedFile && data.files.some((file) => file.id === requestedFile) ? requestedFile : null;
      const fallback = requested || data.files.find((file) => !file.progress?.completed)?.id || data.files[0]?.id || null;
      setTitle(data);
      setError("");
      setSelectedId((current) => {
        const changedTitle = loadedTitleId.current !== data.id;
        loadedTitleId.current = data.id;
        if (changedTitle) return fallback;
        return current && data.files.some((file) => file.id === current) ? current : fallback;
      });
    });
  }, [id, requestedFile]);

  useEffect(() => {
    void loadTitle().catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось открыть карточку"));
    const reload = () => void loadTitle();
    window.addEventListener("mlib:movie-library-changed", reload);
    return () => window.removeEventListener("mlib:movie-library-changed", reload);
  }, [loadTitle]);

  const selected = useMemo(() => title?.files.find((file) => file.id === selectedId) ?? null, [selectedId, title]);

  const updateStatus = async (status: SeriesTrackingStatus | MovieTrackingStatus) => {
    setStatusBusy(true);
    setError("");
    try {
      const tracking = await api<TitleTracking>(`/movie/titles/${id}/tracking`, {
        method: "PUT",
        body: { status },
      });
      setTitle((current) => current ? { ...current, tracking } : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить статус");
    } finally {
      setStatusBusy(false);
    }
  };

  const clearStatus = async () => {
    setStatusBusy(true);
    setError("");
    try {
      await api<void>(`/movie/titles/${id}/tracking`, { method: "DELETE" });
      setTitle((current) => current ? { ...current, tracking: null } : current);
      window.dispatchEvent(new Event("mlib:movie-library-changed"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось убрать статус");
    } finally {
      setStatusBusy(false);
    }
  };

  const saveProgress = (file: MovieFile, completed = false) => {
    const player = videoRef.current;
    if (!player) return;
    void api<MovieProgress>(`/movie/files/${file.id}/progress`, {
      method: "PUT",
      body: { position: player.currentTime, duration: player.duration || file.duration, ...(completed ? { completed: true } : {}) },
    }).then((progress) => { if (progress.completed) void loadTitle(); });
  };

  const onLoaded = () => {
    const player = videoRef.current;
    if (!player || !selected?.progress || selected.progress.completed) return;
    if (selected.progress.position < player.duration - 5) player.currentTime = selected.progress.position;
  };

  const onTimeUpdate = () => {
    const player = videoRef.current;
    if (!player || !selected || player.currentTime - lastSaved.current < 10) return;
    lastSaved.current = player.currentTime;
    saveProgress(selected);
  };

  if (error && !title) return <div className="movie-detail-page"><div className="form-error">{error}</div></div>;
  if (!title || title.id !== id) return <div className="movie-detail-page"><PageLoader /></div>;

  const statuses = title.media_type === "series" ? seriesStatuses : movieStatuses;
  const statusLabel = statuses.find((item) => item.value === title.tracking?.status)?.label;
  const progressLabel = title.media_type === "series"
    ? `${title.watched_count} из ${title.total_episodes || "—"} эпизодов`
    : title.tracking?.status === "watched" ? "Просмотрен" : title.runtime_minutes ? `${title.runtime_minutes} мин` : null;

  return (
    <div className="movie-detail-page">
      <section className="movie-detail-hero" style={title.backdrop_url ? { backgroundImage: `linear-gradient(90deg, #11120f 5%, rgba(17,18,15,.9) 42%, rgba(17,18,15,.28)), url(${title.backdrop_url})` } : undefined}>
        <Link href="/movie" className="movie-back"><ArrowLeft size={17} />Каталог</Link>
        <div className="movie-detail-poster">{title.poster_url ? <Image src={title.poster_url} alt={`Постер ${title.title}`} fill sizes="220px" priority /> : <Clapperboard size={42} />}</div>
        <div className="movie-detail-copy">
          <div className="movie-kicker">{title.media_type === "series" ? "Сериал" : "Фильм"}{statusLabel ? ` · ${statusLabel}` : " · Не добавлен в список"}</div>
          <h1>{title.title}</h1>
          {title.original_title && title.original_title !== title.title && <div className="movie-original-title">{title.original_title}</div>}
          <div className="movie-detail-meta">
            <span>{title.year || "Год неизвестен"}</span>
            {title.tmdb_rating && <span><Star size={14} fill="currentColor" />{title.tmdb_rating.toFixed(1)}</span>}
            {progressLabel && <span>{progressLabel}</span>}
            {title.genres.slice(0, 3).map((genre) => <span key={genre}>{genre}</span>)}
          </div>
          <p>{title.overview || "Описание пока отсутствует."}</p>
          <div className="tracking-status-actions" aria-label="Статус просмотра">
            {statuses.map((item) => (
              <button
                type="button"
                className={`tracking-status-button ${title.tracking?.status === item.value ? "active" : ""}`}
                disabled={statusBusy}
                onClick={() => void updateStatus(item.value)}
                key={item.value}
              >
                {title.tracking?.status === item.value && <Check size={15} />}{item.label}
              </button>
            ))}
            {title.tracking && (
              <button
                type="button"
                className="tracking-status-button remove"
                disabled={statusBusy}
                onClick={() => void clearStatus()}
              >
                <ListX size={15} />Убрать из моих списков
              </button>
            )}
          </div>
          {selected && <button className="movie-local-play-link" onClick={() => { videoRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); void videoRef.current?.play(); }}><Play size={14} fill="currentColor" />{selected.progress?.position ? "Продолжить локальное видео" : "Смотреть локальный файл"}</button>}
        </div>
      </section>

      {error && <div className="form-error movie-detail-error">{error}</div>}

      {title.media_type === "series" && <EpisodeTracker title={title} onChanged={() => void loadTitle()} />}

      {!!(title.directors.length || title.cast.length) && <section className="movie-credits-section">
        <div className="movie-credits-heading"><span>Съёмочная группа</span><h2>Люди за этой историей</h2></div>
        {!!title.directors.length && <div className="movie-credit-group">
          <h3>{title.media_type === "series" ? "Режиссёры и создатели" : "Режиссёр"}</h3>
          <div className="movie-credit-list">{title.directors.map((person) => <button type="button" className="movie-credit-person" onClick={() => setSelectedPerson(person)} aria-label={`Открыть фильмографию: ${person.name}`} key={`director-${person.tmdb_id}`}>
            <span className="movie-credit-avatar">{person.profile_url ? <Image src={person.profile_url} alt={person.name} fill sizes="52px" /> : person.name.slice(0, 1)}</span>
            <span><strong>{person.name}</strong><small>{person.role}</small></span>
          </button>)}</div>
        </div>}
        {!!title.cast.length && <div className="movie-credit-group">
          <h3>В главных ролях</h3>
          <div className="movie-credit-list cast">{title.cast.map((person) => <button type="button" className="movie-credit-person" onClick={() => setSelectedPerson(person)} aria-label={`Открыть фильмографию: ${person.name}`} key={`cast-${person.tmdb_id}`}>
            <span className="movie-credit-avatar">{person.profile_url ? <Image src={person.profile_url} alt={person.name} fill sizes="52px" /> : person.name.slice(0, 1)}</span>
            <span><strong>{person.name}</strong><small>{person.role || "Актёр"}</small></span>
          </button>)}</div>
        </div>}
      </section>}

      {title.files.length ? (
        <section className="movie-local-section">
          <div className="movie-local-heading">
            <div><span>Дополнительная возможность</span><h2>Локальное видео</h2></div>
            <button className="button movie-secondary" onClick={() => setUploadOpen(true)}><UploadCloud size={16} />Добавить файл</button>
          </div>
          <div className="movie-watch-layout">
            <div className="movie-player-column">
              <div className="movie-player-shell">
                {selected ? <video
                  ref={videoRef}
                  key={selected.id}
                  controls
                  playsInline
                  preload="metadata"
                  poster={title.backdrop_url || title.poster_url || undefined}
                  src={movieStreamUrl(selected.id)}
                  onLoadedMetadata={onLoaded}
                  onTimeUpdate={onTimeUpdate}
                  onPause={() => saveProgress(selected)}
                  onEnded={() => saveProgress(selected, true)}
                /> : <div className="movie-no-file"><FileVideo2 size={30} /><strong>Файл не выбран</strong></div>}
              </div>
              {selected && <div className="movie-player-info"><div><strong>{selected.display_title}</strong><span>{selected.original_filename}</span></div><span>{selected.width && selected.height ? `${selected.width}×${selected.height} · ` : ""}{selected.video_codec || selected.format} · {formatBytes(selected.file_size)}</span></div>}
            </div>
            <aside className="movie-episodes local-file-list">
              <div className="movie-episodes-heading"><div><span>Файлы</span><h2>{title.media_type === "series" ? "Локальные эпизоды" : "Версии"}</h2></div><strong>{title.file_count}</strong></div>
              <div className="movie-episode-list">{title.files.map((file) => {
                const duration = file.progress?.duration || file.duration;
                const percent = file.progress?.completed ? 100 : duration ? (file.progress?.position || 0) / duration * 100 : 0;
                return <button className={selectedId === file.id ? "active" : ""} onClick={() => { setSelectedId(file.id); lastSaved.current = 0; }} key={file.id}>
                  <span className="episode-index">{file.progress?.completed ? <Check size={14} /> : file.episode_number ?? <Play size={13} />}</span>
                  <span className="episode-copy"><strong>{file.display_title}</strong><small>{file.duration ? formatLongDuration(file.duration) : file.format.toUpperCase()}</small><i><em style={{ width: `${percent}%` }} /></i></span>
                </button>;
              })}</div>
            </aside>
          </div>
        </section>
      ) : (
        <section className="movie-local-addon">
          <div><FileVideo2 size={21} /><span><strong>Есть локальный файл?</strong><small>Его можно добавить и смотреть прямо в movieLib. Для трекинга это необязательно.</small></span></div>
          <button className="button movie-secondary" onClick={() => setUploadOpen(true)}><UploadCloud size={16} />Добавить видео</button>
        </section>
      )}
      <MovieUploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} titleId={title.id} titleName={title.title} />
      <PersonFilmographyDialog open={selectedPerson !== null} person={selectedPerson} onClose={() => setSelectedPerson(null)} />
    </div>
  );
}
