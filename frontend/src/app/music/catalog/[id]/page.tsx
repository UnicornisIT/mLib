"use client";

import { ArrowLeft, FileAudio, Link2, Link2Off, Play, Search, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { useCatalogUpload, useFileDrop } from "@/components/CatalogCard";
import { CatalogHero, ExternalLinks } from "@/components/CatalogHero";
import { PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import { AUDIO_ACCEPT, catalogAlbumHref, catalogArtworkSource, catalogDuration } from "@/lib/catalog";
import { formatTime } from "@/lib/format";
import type { CatalogFileResult, CatalogTrack, Track, TrackPage } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";
import { useFeedback } from "@/providers/FeedbackProvider";
import { usePlayer } from "@/providers/PlayerProvider";

const STATUS_TEXT: Record<CatalogTrack["enrich_status"], string | null> = {
  enriched: null,
  pending: "Ищем трек в Apple Music — обложка и ссылка появятся позже.",
  not_found: "Трек не найден в Apple Music: показаны данные из экспорта.",
  error: "Не удалось связаться с Apple Music. Повторите поиск на странице переноса.",
};

function formatSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

export default function CatalogTrackPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const player = usePlayer();
  const feedback = useFeedback();
  const inputRef = useRef<HTMLInputElement>(null);
  const [item, setItem] = useState<CatalogTrack | null>(null);
  const [file, setFile] = useState<Track | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canEdit = Boolean(user?.is_admin);

  const load = useCallback(async () => {
    try {
      const next = await api<CatalogTrack>(`/music/transfer/tracks/${id}`);
      const linked = next.track_id ? await api<Track>(`/music/tracks/${next.track_id}`) : null;
      setItem(next);
      setFile(linked);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить трек");
    }
  }, [id]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the request resolves
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  const { uploading, upload } = useCatalogUpload((updated, track) => { setItem(updated); setFile(track); });
  const { dragging, handlers } = useFileDrop(canEdit && Boolean(item && !item.has_file) && !uploading, (dropped) => item && void upload(item, dropped));

  const unlink = async () => {
    if (!item) return;
    const accepted = await feedback.confirm({
      title: "Отвязать файл?",
      message: "Файл останется в медиатеке как обычный трек, а карточка каталога снова будет без файла.",
      confirmLabel: "Отвязать",
    });
    if (!accepted) return;
    setBusy(true);
    try {
      setItem(await api<CatalogTrack>(`/music/transfer/tracks/${item.id}/file`, { method: "DELETE" }));
      setFile(null);
      window.dispatchEvent(new Event("mlib:library-changed"));
      feedback.notify("Файл отвязан");
    } catch (caught) {
      feedback.notify(caught instanceof Error ? caught.message : "Не удалось отвязать файл", "error");
    } finally {
      setBusy(false);
    }
  };

  if (error && !item) return <div className="content-page"><div className="form-error" role="alert">{error}</div><Link className="button" href="/music/catalog"><ArrowLeft size={16} />К каталогу</Link></div>;
  if (!item) return <div className="content-page"><PageLoader rows={4} /></div>;

  const duration = file ? formatTime(file.duration) : catalogDuration(item.duration_ms);
  const status = STATUS_TEXT[item.enrich_status];

  return (
    <div className="content-page catalog-detail">
      <Link className="catalog-back" href="/music/catalog"><ArrowLeft size={15} />Каталог</Link>
      <CatalogHero source={catalogArtworkSource(item, 64)} art={<Artwork id={item.artwork_id} url={item.artwork_url} alt={item.title} size={512} />}>
        <div className="eyebrow">Трек</div>
        <h1>{item.title}</h1>
        <p className="catalog-hero-artist">{item.artist_name}</p>
        <p className="catalog-hero-meta">
          {item.album_title && (item.album_key ? <Link href={catalogAlbumHref(item.album_key)}>{item.album_title}</Link> : <span>{item.album_title}</span>)}
          {[item.year, duration].filter(Boolean).map((value) => <span key={String(value)}>{value}</span>)}
          {!item.has_file && <span className="catalog-pill">Нет файла</span>}
        </p>
        <div className="catalog-actions">
          {file && <button className="button primary" type="button" onClick={() => player.playTrack(file, [file])}><Play size={17} fill="currentColor" />Слушать</button>}
          <ExternalLinks appleMusicUrl={item.apple_music_url} spotifyUrl={item.spotify_url} />
        </div>
        {status && <p className="transfer-note">{status}</p>}
      </CatalogHero>

      {item.has_file && file ? (
        <section className="catalog-file" aria-label="Файл">
          <div className="catalog-file-icon"><FileAudio size={22} /></div>
          <div className="catalog-file-copy">
            <strong>Файл в медиатеке</strong>
            <span>{[file.format.toUpperCase(), file.bitrate ? `${Math.round(file.bitrate / 1000)} кбит/с` : null, formatSize(file.file_size), formatTime(file.duration)].filter(Boolean).join(" · ")}</span>
            <span>Теги файла: {file.title} — {file.artist.name}{file.album ? ` · ${file.album.title}` : ""}. На экране показываются данные каталога, сами теги не меняются.</span>
          </div>
          {canEdit && <button className="button ghost danger" type="button" disabled={busy} onClick={() => void unlink()}><Link2Off size={15} />Отвязать</button>}
        </section>
      ) : canEdit ? (
        <>
          <input
            ref={inputRef}
            hidden
            type="file"
            accept={AUDIO_ACCEPT}
            aria-label="Аудиофайл для трека"
            onChange={(event: ChangeEvent<HTMLInputElement>) => { const picked = event.target.files?.[0]; event.target.value = ""; if (picked) void upload(item, picked); }}
          />
          <section
            className={`catalog-dropzone ${dragging ? "dragging" : ""} ${uploading ? "uploading" : ""}`}
            aria-label="Файл"
            {...handlers}
          >
            <UploadCloud size={30} />
            <div>
              <strong>{uploading ? "Загружаем файл…" : dragging ? "Отпустите, чтобы добавить файл" : "У этого трека пока нет файла"}</strong>
              <span>Перетащите аудиофайл сюда или выберите его на диске. Файл привяжется именно к этому треку, даже если его теги отличаются.</span>
            </div>
            <button className="button primary" type="button" disabled={uploading} onClick={() => inputRef.current?.click()}><UploadCloud size={16} />Загрузить файл</button>
          </section>
          <LinkExisting item={item} onLinked={(result) => { setItem(result.catalog_track); setFile(result.track); }} />
        </>
      ) : (
        <p className="transfer-note">Файла пока нет. Добавить его может администратор mLib.</p>
      )}
    </div>
  );
}

/** Lets an admin attach a file that is already in the library to this catalog track. */
function LinkExisting({ item, onLinked }: { item: CatalogTrack; onLinked: (result: CatalogFileResult) => void }) {
  const feedback = useFeedback();
  // Track search matches title, artist or album separately, so the title alone is the best start.
  const [query, setQuery] = useState(item.title);
  const [results, setResults] = useState<Track[] | null>(null);
  const [busy, setBusy] = useState(false);

  const search = async (event: FormEvent) => {
    event.preventDefault();
    const term = query.trim();
    if (!term) return;
    try {
      setResults((await api<TrackPage>(`/music/tracks?${new URLSearchParams({ q: term, page_size: "8" })}`)).items);
    } catch (caught) {
      feedback.notify(caught instanceof Error ? caught.message : "Не удалось выполнить поиск", "error");
    }
  };

  const link = async (track: Track) => {
    setBusy(true);
    try {
      const result = await api<CatalogFileResult>(`/music/transfer/tracks/${item.id}/file`, { method: "PUT", body: { track_id: track.id } });
      window.dispatchEvent(new Event("mlib:library-changed"));
      feedback.notify(result.detail);
      onLinked(result);
    } catch (caught) {
      feedback.notify(caught instanceof Error ? caught.message : "Не удалось привязать файл", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="catalog-link-existing" aria-label="Привязать файл из медиатеки">
      <h2>Файл уже в медиатеке?</h2>
      <form onSubmit={(event) => void search(event)}>
        <label className="catalog-search">
          <Search size={16} />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Поиск файла в медиатеке" />
        </label>
        <button className="button" type="submit">Найти</button>
      </form>
      {results && (results.length ? (
        <ul>
          {results.map((track) => (
            <li key={track.id}>
              <span className="track-art"><Artwork id={track.artwork_id} url={track.catalog?.artwork_url} alt={track.title} size={64} /></span>
              <span className="track-copy">
                <span className="track-title">{track.title}</span>
                <span className="track-subtitle">{track.artist.name}{track.album ? ` · ${track.album.title}` : ""} · {formatTime(track.duration)}{track.catalog ? ` · уже привязан к «${track.catalog.title}»` : ""}</span>
              </span>
              <button className="button" type="button" disabled={busy || Boolean(track.catalog)} onClick={() => void link(track)}><Link2 size={15} />Привязать</button>
            </li>
          ))}
        </ul>
      ) : <p className="transfer-note">В медиатеке ничего не нашлось.</p>)}
    </section>
  );
}
