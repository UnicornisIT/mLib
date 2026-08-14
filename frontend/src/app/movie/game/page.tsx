"use client";

import {
  ArrowLeft,
  BookmarkPlus,
  Check,
  Clapperboard,
  Clock3,
  Eye,
  ListX,
  LoaderCircle,
  RotateCcw,
  Sparkles,
  Star,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  MediaTitle,
  MediaTitlePage,
  TitleTracking,
  TmdbCatalogPage,
  TmdbCatalogTitle,
} from "@/lib/types";

type SessionStats = {
  watched: number;
  planned: number;
  deferred: number;
};

type EveningPick = TmdbCatalogTitle & { local_title_id: string };

const emptyStats: SessionStats = { watched: 0, planned: 0, deferred: 0 };

function movieKey(title: TmdbCatalogTitle) {
  return `${title.media_type}-${title.tmdb_id}`;
}

function shuffle<T>(items: T[]) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result;
}

function ChoiceCard({
  title,
  busy,
  disabled,
  onChoose,
}: {
  title: TmdbCatalogTitle;
  busy: boolean;
  disabled: boolean;
  onChoose: (choice: "watched" | "planned" | "deferred") => void;
}) {
  return (
    <article className={`movie-game-card${busy ? " busy" : ""}`}>
      <div className="movie-game-poster">
        {title.poster_url ? (
          <Image
            src={title.poster_url}
            alt={`Постер фильма «${title.title}»`}
            fill
            sizes="(max-width: 680px) 82vw, 330px"
            priority
          />
        ) : (
          <div className="movie-game-placeholder"><Clapperboard size={48} /><span>{title.title}</span></div>
        )}
        <span className="movie-game-number">{title.media_type === "series" ? "Сериал" : "Фильм"}</span>
        {busy && <span className="movie-game-saving"><LoaderCircle className="spin" size={22} />Сохраняем</span>}
      </div>

      <div className="movie-game-copy">
        <div className="movie-game-meta">
          <span>{title.year || "Год неизвестен"}</span>
          {title.tmdb_rating && <span><Star size={13} fill="currentColor" />{title.tmdb_rating.toFixed(1)}</span>}
        </div>
        <h2>{title.title}</h2>
        {title.original_title && title.original_title !== title.title && <small>{title.original_title}</small>}
        <p>{title.overview || "Описание пока не добавлено, но решение можно принять по постеру и рейтингу."}</p>
      </div>

      <div className="movie-game-actions" aria-label={`Статус фильма «${title.title}»`}>
        <button type="button" className="watched" disabled={disabled} onClick={() => onChoose("watched")}>
          <Eye size={17} /><span><strong>Смотрел</strong><small>В просмотренные</small></span>
        </button>
        <button type="button" className="planned" disabled={disabled} onClick={() => onChoose("planned")}>
          <BookmarkPlus size={17} /><span><strong>Буду смотреть</strong><small>Выбрать на вечер</small></span>
        </button>
        <button type="button" className="deferred" disabled={disabled} onClick={() => onChoose("deferred")}>
          <RotateCcw size={17} /><span><strong>Не смотрел</strong><small>Вернуть в конец</small></span>
        </button>
      </div>
    </article>
  );
}

export default function MovieGamePage() {
  const [queue, setQueue] = useState<TmdbCatalogTitle[]>([]);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState(2);
  const [lastPage, setLastPage] = useState(1);
  const [stats, setStats] = useState<SessionStats>(emptyStats);
  const [eveningPick, setEveningPick] = useState<EveningPick | null>(null);
  const [cancellingPick, setCancellingPick] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const trackedIds = useRef(new Set<string>());
  const loadedPages = useRef(new Set<number>());

  const appendCatalog = useCallback((catalog: TmdbCatalogPage) => {
    setConfigured(catalog.configured);
    setLastPage(Math.max(1, catalog.pages));
    const available = catalog.items.filter((title) => !title.local_title_id || !trackedIds.current.has(title.local_title_id));
    setQueue((current) => {
      const existing = new Set(current.map(movieKey));
      return [...current, ...shuffle(available.filter((title) => !existing.has(movieKey(title))))];
    });
  }, []);

  const loadMore = useCallback(async (page: number) => {
    if (loadedPages.current.has(page)) return;
    loadedPages.current.add(page);
    setLoadingMore(true);
    try {
      const catalog = await api<TmdbCatalogPage>(`/movie/catalog?page=${page}&media_type=all&sort=popular`);
      appendCatalog(catalog);
      setNextPage(page + 1);
    } catch (caught) {
      loadedPages.current.delete(page);
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить следующую пару вариантов");
    } finally {
      setLoadingMore(false);
    }
  }, [appendCatalog]);

  useEffect(() => {
    let active = true;
    const start = async () => {
      setLoading(true);
      setError("");
      try {
        const [tracked, catalog] = await Promise.all([
          api<MediaTitlePage>("/movie/titles?tracked=true&page_size=100"),
          api<TmdbCatalogPage>("/movie/catalog?page=1&media_type=all&sort=popular"),
        ]);
        if (!active) return;
        trackedIds.current = new Set(tracked.items.map((title) => title.id));
        loadedPages.current.add(1);
        appendCatalog(catalog);
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Не удалось запустить игру");
      } finally {
        if (active) setLoading(false);
      }
    };
    void start();
    return () => { active = false; };
  }, [appendCatalog]);

  useEffect(() => {
    if (!loading && !loadingMore && configured && queue.length < 8 && nextPage <= lastPage) {
      const timer = window.setTimeout(() => void loadMore(nextPage), 0);
      return () => window.clearTimeout(timer);
    }
  }, [configured, lastPage, loadMore, loading, loadingMore, nextPage, queue.length]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 2800);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const visibleMovies = useMemo(() => queue.slice(0, 2), [queue]);
  const resolved = stats.watched + stats.planned;

  const choose = async (title: TmdbCatalogTitle, choice: "watched" | "planned" | "deferred") => {
    const key = movieKey(title);
    setError("");
    if (choice === "deferred") {
      setQueue((current) => [...current.filter((item) => movieKey(item) !== key), title]);
      setStats((current) => ({ ...current, deferred: current.deferred + 1 }));
      setNotice(`«${title.title}» вернётся позже`);
      return;
    }

    setBusyKey(key);
    try {
      let titleId = title.local_title_id;
      if (!titleId) {
        const saved = await api<MediaTitle>(`/movie/catalog/${title.media_type}/${title.tmdb_id}`, { method: "POST" });
        titleId = saved.id;
      }
      await api<TitleTracking>(`/movie/titles/${titleId}/tracking`, {
        method: "PUT",
        body: { status: choice === "planned" ? "planned" : title.media_type === "series" ? "completed" : "watched" },
      });
      trackedIds.current.add(titleId);
      setQueue((current) => current.filter((item) => movieKey(item) !== key));
      setStats((current) => ({ ...current, [choice]: current[choice] + 1 }));
      if (choice === "planned") {
        setEveningPick({ ...title, local_title_id: titleId });
      } else {
        setNotice(`«${title.title}» отправлен в просмотренные`);
      }
      window.dispatchEvent(new Event("mlib:movie-library-changed"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить выбор");
    } finally {
      setBusyKey(null);
    }
  };

  const cancelEveningPick = async () => {
    if (!eveningPick) return;
    setCancellingPick(true);
    setError("");
    try {
      await api<void>(`/movie/titles/${eveningPick.local_title_id}/tracking`, { method: "DELETE" });
      trackedIds.current.delete(eveningPick.local_title_id);
      setQueue((current) => current.some((title) => movieKey(title) === movieKey(eveningPick))
        ? current
        : [...current, eveningPick]);
      setStats((current) => ({ ...current, planned: Math.max(0, current.planned - 1) }));
      setEveningPick(null);
      setNotice(`Выбор «${eveningPick.title}» отменён — вариант вернулся в конец очереди`);
      window.dispatchEvent(new Event("mlib:movie-library-changed"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отменить выбор");
    } finally {
      setCancellingPick(false);
    }
  };

  return (
    <div className="movie-library-page movie-game-page">
      <header className="movie-library-nav movie-game-nav">
        <Link href="/movie" className="movie-game-back"><ArrowLeft size={16} />К каталогу</Link>
        <nav aria-label="Разделы игры"><Link href="/movie">movieLib</Link><Link href="/movie/profile">Профиль</Link></nav>
        <div className="movie-game-round"><Sparkles size={14} /><span>Разобрано</span><strong>{resolved}</strong></div>
      </header>

      <div className="service-page-content">
        <section className="movie-game-intro">
          <div>
            <span>Выбор на вечер</span>
            <h1>Что будем смотреть сегодня?</h1>
            <p>Сравнивайте два фильма или сериала. «Буду смотреть» завершит раунд и сохранит победителя в планы, просмотренное попадёт в профиль, а незнакомый вариант вернётся в конце очереди.</p>
          </div>
          <div className="movie-game-stats" aria-label="Результаты текущей сессии">
            <span><Eye size={16} /><strong>{stats.watched}</strong><small>уже видел</small></span>
            <span><BookmarkPlus size={16} /><strong>{stats.planned}</strong><small>выбрано</small></span>
            <span><Clock3 size={16} /><strong>{stats.deferred}</strong><small>на потом</small></span>
          </div>
        </section>

        {error && <div className="form-error movie-game-error" role="alert">{error}</div>}
        {notice && <div className="movie-game-notice" role="status"><Check size={15} />{notice}</div>}

        {loading ? (
          <div className="movie-game-loading"><span className="loading-mark" /><p>Подбираем первую пару…</p></div>
        ) : !configured ? (
          <div className="movie-empty-catalog movie-game-empty">
            <span><Clapperboard size={30} /></span><h3>Сначала подключите каталог TMDB</h3>
            <p>Игра берёт популярные фильмы и сериалы из каталога. Добавьте токен TMDB в настройках movieLib и возвращайтесь.</p>
            <Link className="button primary" href="/movie/settings">Открыть настройки</Link>
          </div>
        ) : eveningPick ? (
          <section className="movie-game-result">
            <div className="movie-game-result-art" style={eveningPick.backdrop_url ? { backgroundImage: `url(${eveningPick.backdrop_url})` } : undefined}>
              {!eveningPick.backdrop_url && <Clapperboard size={55} />}
            </div>
            <div className="movie-game-result-copy">
              <span><Sparkles size={14} />Выбор на сегодня</span>
              <h2>{eveningPick.title}</h2>
              <p>{eveningPick.overview || "Выбор сделан — осталось устроиться поудобнее и включить просмотр."}</p>
              <div>
                <Link className="button primary movie-primary" href={`/movie/${eveningPick.local_title_id}`}>Открыть карточку</Link>
                <button type="button" className="button movie-secondary" disabled={cancellingPick} onClick={() => setEveningPick(null)}><RotateCcw size={16} />Выбрать ещё</button>
                <button type="button" className="button movie-game-cancel" disabled={cancellingPick} onClick={() => void cancelEveningPick()}>
                  {cancellingPick ? <LoaderCircle className="spin" size={16} /> : <ListX size={16} />}Отменить выбор
                </button>
              </div>
            </div>
          </section>
        ) : visibleMovies.length ? (
          <>
            <section className="movie-game-board" aria-label="Два фильма или сериала на выбор">
              {visibleMovies.map((title) => (
                <ChoiceCard
                  title={title}
                  busy={busyKey === movieKey(title)}
                  disabled={busyKey !== null}
                  onChoose={(choice) => void choose(title, choice)}
                  key={movieKey(title)}
                />
              ))}
            </section>
            <div className="movie-game-queue-note">
              <span>{queue.length} вариантов в текущей очереди</span>
              {loadingMore && <span><LoaderCircle className="spin" size={13} />Добавляем новые</span>}
            </div>
          </>
        ) : (
          <div className="movie-empty-catalog movie-game-empty">
            <span><Check size={30} /></span><h3>Очередь разобрана</h3>
            <p>Все предложенные фильмы и сериалы получили статус. Результаты уже сохранены в вашем профиле.</p>
            <Link className="button primary" href="/movie/profile">Открыть профиль</Link>
          </div>
        )}

        <div className="tmdb-attribution">Данные и изображения предоставлены <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">TMDB</a>. This product uses the TMDB API but is not endorsed or certified by TMDB.</div>
      </div>
    </div>
  );
}
