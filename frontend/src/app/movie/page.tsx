"use client";

import { CalendarDays, ChevronLeft, ChevronRight, Clapperboard, Dices, Film, ListChecks, Search, Tv } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { MovieCard } from "@/components/MovieCard";
import { TmdbMovieCard } from "@/components/TmdbMovieCard";
import { api } from "@/lib/api";
import type { MediaTitle, MediaTitlePage, MovieDashboard, TmdbCatalogPage, TmdbCatalogTitle } from "@/lib/types";

type Filter = "all" | "movie" | "series";

export default function MoviePage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<MovieDashboard | null>(null);
  const [library, setLibrary] = useState<MediaTitlePage | null>(null);
  const [catalog, setCatalog] = useState<TmdbCatalogPage | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sort, setSort] = useState("popular");
  const [page, setPage] = useState(1);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(() => api<MovieDashboard>("/movie/dashboard").then(setDashboard), []);
  const loadLibrary = useCallback(() => api<MediaTitlePage>("/movie/titles?page_size=100&sort=added&tracked=true").then(setLibrary), []);
  const loadCatalog = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), media_type: filter, sort });
    if (searchQuery) params.set("q", searchQuery);
    return api<TmdbCatalogPage>(`/movie/catalog?${params}`).then((data) => { setCatalog(data); setError(""); });
  }, [filter, page, searchQuery, sort]);

  useEffect(() => {
    const timer = window.setTimeout(() => { setPage(1); setSearchQuery(query.trim()); }, 350);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    void loadCatalog().catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось загрузить каталог"));
  }, [loadCatalog]);

  useEffect(() => {
    Promise.all([loadDashboard(), loadLibrary()]).catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось открыть movieLib"));
    const reload = () => { void loadDashboard(); void loadLibrary(); void loadCatalog(); };
    window.addEventListener("mlib:movie-library-changed", reload);
    return () => window.removeEventListener("mlib:movie-library-changed", reload);
  }, [loadCatalog, loadDashboard, loadLibrary]);

  const openCard = async (title: TmdbCatalogTitle) => {
    if (title.local_title_id) {
      router.push(`/movie/${title.local_title_id}`);
      return;
    }
    const key = `${title.media_type}-${title.tmdb_id}`;
    setOpening(key);
    setError("");
    try {
      const saved = await api<MediaTitle>(`/movie/catalog/${title.media_type}/${title.tmdb_id}`, { method: "POST" });
      router.push(`/movie/${saved.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось открыть карточку");
      setOpening(null);
    }
  };

  const upcoming = library?.items.filter((title) => title.next_air_date).slice(0, 4) ?? [];
  const hasLibrary = Boolean(library?.total);

  return (
    <div className="movie-library-page">
      <header className="movie-library-nav">
        <nav aria-label="Разделы movieLib"><a href="#catalog">Каталог</a><a href="#library">Мои списки</a><a href="#continue">Смотрю</a><Link href="/movie/game">Игра</Link><Link href="/movie/profile">Статистика</Link></nav>
      </header>

      <div className="service-page-content">
        <section className="movie-library-hero">
          <div className="movie-hero-copy">
            <div className="movie-kicker">Личный трекер фильмов и сериалов</div>
            <h1>Смотрите. Отмечайте. Не теряйте сюжет.</h1>
            <p>Собирайте списки, отмечайте просмотренные фильмы и конкретные эпизоды, следите за прогрессом сезонов. Карточки и даты обновляются автоматически.</p>
            <div className="movie-hero-actions">
              <a className="button primary movie-primary" href="#catalog"><Search size={18} />Найти фильм</a>
              <Link className="button movie-secondary" href="/movie/game"><Dices size={18} />Сыграть</Link>
              {hasLibrary && <a className="button movie-secondary" href="#library"><ListChecks size={17} />Мои списки</a>}
            </div>
          </div>
          <div className="movie-hero-art" aria-hidden="true">
            <div className="movie-hero-frame frame-a"><span /></div>
            <div className="movie-hero-frame frame-b"><span /></div>
            <div className="movie-hero-disc"><i /><i /><i /><i /></div>
          </div>
          {dashboard && <div className="movie-stats">
            <span><strong>{dashboard.movies}</strong>просмотрено фильмов</span>
            <span><strong>{dashboard.series}</strong>сериалов в списках</span>
            <span><strong>{dashboard.episodes}</strong>просмотрено эпизодов</span>
          </div>}
        </section>

        {error && <div className="form-error movie-error">{error}</div>}

        {!!dashboard?.continue_watching.length && <section className="movie-section" id="continue">
          <div className="movie-section-heading"><div><span>Вернуться к просмотру</span><h2>Продолжить</h2></div></div>
          <div className="continue-row">{dashboard.continue_watching.map(({ title, file }) => {
            const duration = file ? file.progress?.duration || file.duration : 0;
            const percent = file && duration
              ? Math.min(100, (file.progress?.position || 0) / duration * 100)
              : title.progress_percent;
            const progressLabel = file
              ? file.display_title
              : `${title.watched_count} из ${title.total_episodes || "—"} эпизодов`;
            return <Link href={file ? `/movie/${title.id}?file=${file.id}` : `/movie/${title.id}`} className="continue-card" key={file?.id || title.id}>
              <div className="continue-art" style={title.backdrop_url ? { backgroundImage: `url(${title.backdrop_url})` } : undefined}>
                {!title.backdrop_url && <Clapperboard size={34} />}
                <span className="continue-play"><Film size={18} /></span>
                <span className="continue-progress"><i style={{ width: `${percent}%` }} /></span>
              </div>
              <strong>{title.title}</strong><span>{progressLabel}</span>
            </Link>;
          })}</div>
        </section>}

        <section className="movie-section" id="catalog">
          <div className="movie-section-heading catalog-heading">
            <div><span>База фильмов и сериалов</span><h2>Каталог</h2></div>
            <div className="movie-catalog-tools">
              <label className="movie-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, актёр или режиссёр" /></label>
              <select className="movie-sort" value={sort} onChange={(event) => { setPage(1); setSort(event.target.value); }} aria-label="Сортировка">
                <option value="popular">Сначала популярные</option><option value="rating">По рейтингу</option><option value="new">Сначала новые</option>
              </select>
            </div>
          </div>
          <div className="movie-filter-row">
            <button className={filter === "all" ? "active" : ""} onClick={() => { setPage(1); setFilter("all"); }}>Всё <span>{catalog?.total ? catalog.total.toLocaleString("ru-RU") : ""}</span></button>
            <button className={filter === "movie" ? "active" : ""} onClick={() => { setPage(1); setFilter("movie"); }}><Film size={14} />Фильмы</button>
            <button className={filter === "series" ? "active" : ""} onClick={() => { setPage(1); setFilter("series"); }}><Tv size={14} />Сериалы</button>
          </div>

          {catalog === null ? <div className="movie-catalog-loading"><span className="loading-mark" /></div> : !catalog.configured ? (
            <div className="movie-empty-catalog"><span><Clapperboard size={30} /></span><h3>Подключите каталог TMDB</h3><p>Добавьте Read Access Token через шестерёнку рядом с кнопкой выхода — после этого здесь появится большая актуальная база фильмов и сериалов.</p></div>
          ) : catalog.items.length > 0 ? <>
            <div className="movie-grid">{catalog.items.map((title, index) => {
              const key = `${title.media_type}-${title.tmdb_id}`;
              return <TmdbMovieCard title={title} loading={opening === key} onOpen={() => void openCard(title)} priority={index < 6} key={key} />;
            })}</div>
            {catalog.pages > 1 && <div className="movie-catalog-pagination">
              <button className="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft size={16} />Назад</button>
              <span>{page} из {catalog.pages}</span>
              <button className="button" disabled={page >= catalog.pages} onClick={() => setPage((current) => current + 1)}>Дальше<ChevronRight size={16} /></button>
            </div>}
          </> : <div className="movie-empty-catalog"><span><Search size={30} /></span><h3>Ничего не найдено</h3><p>Попробуйте другое название или измените фильтр.</p></div>}
          {catalog?.configured && <div className="tmdb-attribution">Данные и изображения предоставлены <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">TMDB</a>. This product uses the TMDB API but is not endorsed or certified by TMDB.</div>}
        </section>

        <section className="movie-section" id="library">
          <div className="movie-section-heading"><div><span>Смотрю · буду · посмотрел</span><h2>Мои списки</h2></div><strong className="movie-library-count">{library?.total ?? 0}</strong></div>
          {library?.items.length ? <div className="movie-grid">{library.items.map((title, index) => <MovieCard title={title} priority={index < 6} key={title.id} />)}</div> : (
            <div className="movie-empty-catalog"><span><ListChecks size={30} /></span><h3>Списки пока пусты</h3><p>Откройте фильм или сериал и выберите статус просмотра — локальный файл для этого не требуется.</p><a className="button primary" href="#catalog">Перейти в каталог</a></div>
          )}
        </section>

        {!!upcoming.length && <section className="movie-section" id="upcoming">
          <div className="movie-section-heading"><div><span>Новые эпизоды</span><h2>Скоро выходят</h2></div><CalendarDays size={22} /></div>
          <div className="upcoming-list">{upcoming.map((title) => <Link href={`/movie/${title.id}`} key={title.id}><time>{new Date(`${title.next_air_date}T00:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}</time><span><strong>{title.title}</strong><small>{title.original_title}</small></span><Tv size={17} /></Link>)}</div>
        </section>}
      </div>
    </div>
  );
}
