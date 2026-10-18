"use client";

import { ArrowRightLeft, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CSSProperties, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { CatalogCard } from "@/components/CatalogCard";
import { CatalogList } from "@/components/CatalogList";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import {
  CATALOG_FILTERS,
  CatalogFilter,
  catalogAlbumArtist,
  catalogAlbumHref,
  catalogAlbumKey,
  catalogArtworkSource,
  loadAllCatalogTracks,
  useArtworkColor,
} from "@/lib/catalog";
import type { CatalogTrack, CatalogTrackPage } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

const PAGE_SIZE = 60;
const ENRICH_POLL_MS = 4000;

type View = "tracks" | "list" | "albums";
const VIEWS: { value: View; label: string }[] = [
  { value: "tracks", label: "Обложки" },
  { value: "list", label: "Список" },
  { value: "albums", label: "Альбомы" },
];

function parseView(value: string | null): View {
  return VIEWS.some((option) => option.value === value) ? value as View : "tracks";
}

function parseFilter(value: string | null): CatalogFilter {
  return CATALOG_FILTERS.some((option) => option.value === value) ? value as CatalogFilter : "all";
}
type CatalogAlbum = { key: string; title: string; artist: string; year: number | null; tracks: CatalogTrack[]; withFile: number; cover: CatalogTrack };

function groupAlbums(items: CatalogTrack[]): CatalogAlbum[] {
  const albums = new Map<string, CatalogAlbum>();
  for (const item of items) {
    if (!item.album_title) continue;
    const key = catalogAlbumKey(item);
    const album = albums.get(key) ?? { key, title: item.album_title, artist: item.artist_name, year: item.year, tracks: [], withFile: 0, cover: item };
    album.tracks.push(item);
    if (item.has_file) album.withFile += 1;
    // A cover from a local file is preferred over Apple artwork for the whole album.
    if (!album.cover.artwork_id && (item.artwork_id || (!album.cover.artwork_url && item.artwork_url))) album.cover = item;
    album.year ??= item.year;
    albums.set(key, album);
  }
  for (const album of albums.values()) album.artist = catalogAlbumArtist(album.tracks.map((track) => track.artist_name));
  return [...albums.values()].sort((a, b) => a.artist.localeCompare(b.artist, "ru") || a.title.localeCompare(b.title, "ru"));
}

const FILTER_SUMMARY: Record<CatalogFilter, string> = {
  all: "в каталоге. Обложки и ссылки — из Apple Music; файлы можно перетащить прямо на карточку.",
  with_file: "с файлом в медиатеке.",
  without_file: "без файла. Перетащите аудиофайл на трек, чтобы добавить его.",
  enriched: "найдено в Apple Music: у них есть обложки и ссылки.",
  not_found: "не найдено в Apple Music. Показаны данные из экспорта; найти трек вручную можно по ссылкам в списке.",
};

function trackCountText(count: number) {
  const tens = count % 100;
  const ones = count % 10;
  if (tens >= 11 && tens <= 14) return `${count} треков`;
  if (ones === 1) return `${count} трек`;
  if (ones >= 2 && ones <= 4) return `${count} трека`;
  return `${count} треков`;
}

function CatalogAlbumCard({ album }: { album: CatalogAlbum }) {
  const href = catalogAlbumHref(album.cover);
  const missing = album.tracks.length - album.withFile;
  return (
    <article className={`catalog-card ${album.withFile ? "" : "no-file"}`}>
      <div className="catalog-card-art">
        <Link href={href} aria-label={`Альбом ${album.title}`}>
          <Artwork id={album.cover.artwork_id} url={album.cover.artwork_url} alt={album.title} size={256} />
        </Link>
        {missing > 0 && <span className="catalog-badge">{album.withFile ? `Нет файлов: ${missing}` : "Нет файлов"}</span>}
      </div>
      <Link href={href} className="album-title">{album.title}</Link>
      <div className="album-meta">{album.artist}{album.year ? ` · ${album.year}` : ""}</div>
    </article>
  );
}

export default function MusicCatalogPage() {
  return <Suspense fallback={<div className="content-page"><PageLoader rows={6} /></div>}><MusicCatalog /></Suspense>;
}

function MusicCatalog() {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // View, filter and search live in the URL so other pages can link straight to a list.
  const view = parseView(searchParams.get("view"));
  const filter = parseFilter(searchParams.get("status"));
  const term = searchParams.get("q")?.trim() ?? "";
  const [query, setQuery] = useState(term);
  const [shownTerm, setShownTerm] = useState(term);
  if (term !== shownTerm) {
    setShownTerm(term);
    setQuery(term);
  }
  const [items, setItems] = useState<CatalogTrack[] | null>(null);
  const [pages, setPages] = useState({ loaded: 0, total: 0, count: 0 });
  const [albumItems, setAlbumItems] = useState<CatalogTrack[] | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const loadedPages = useRef(0);

  // Quick successive changes must build on each other, not on a URL that has not updated yet.
  const requested = useRef<Record<"view" | "status" | "q", string>>({ view, status: filter, q: term });
  useEffect(() => {
    requested.current = { view, status: filter, q: term };
  }, [view, filter, term]);
  const navigate = useCallback((changes: Partial<Record<"view" | "status" | "q", string>>) => {
    const state = { ...requested.current, ...changes };
    requested.current = state;
    const next = new URLSearchParams();
    if (state.view !== "tracks") next.set("view", state.view);
    if (state.status !== "all") next.set("status", state.status);
    if (state.q) next.set("q", state.q);
    const search = next.toString();
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  }, [pathname, router]);

  useEffect(() => {
    const value = query.trim();
    if (value === term) return;
    const timer = window.setTimeout(() => navigate({ q: value }), 300);
    return () => window.clearTimeout(timer);
  }, [navigate, query, term]);

  const params = useCallback((page: number) => {
    const search = new URLSearchParams({ status: filter, page: String(page), page_size: String(PAGE_SIZE) });
    if (term) search.set("q", term);
    return search;
  }, [filter, term]);

  // Refetches every page already shown so a background change does not collapse the grid.
  const reload = useCallback(async () => {
    try {
      const count = Math.max(1, loadedPages.current);
      const results = await Promise.all(Array.from({ length: count }, (_, index) => api<CatalogTrackPage>(`/music/transfer/tracks?${params(index + 1)}`)));
      const last = results[results.length - 1];
      setItems(results.flatMap((result) => result.items));
      setPages({ loaded: count, total: last.pages, count: last.total });
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить каталог");
    }
  }, [params]);

  const reloadAlbums = useCallback(async () => {
    try {
      const search = params(1);
      search.delete("page");
      const loaded = await loadAllCatalogTracks(search);
      setAlbumItems(loaded);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить альбомы");
    }
  }, [params]);

  useEffect(() => {
    loadedPages.current = 1;
    // Filters changed: show the skeleton instead of results for the previous filters.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItems(null);
    setAlbumItems(null);
    void reload();
  }, [reload]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the request resolves
    if (view === "albums") void reloadAlbums();
  }, [view, reloadAlbums]);

  const refresh = useCallback(() => {
    void reload();
    if (view === "albums") void reloadAlbums();
  }, [reload, reloadAlbums, view]);
  useLibraryChanged(refresh);

  // Apple lookup runs in the background after an import: keep covers and links coming in.
  const enriching = Boolean(items?.some((item) => item.enrich_status === "pending"));
  useEffect(() => {
    if (!enriching) return;
    const timer = window.setInterval(refresh, ENRICH_POLL_MS);
    return () => window.clearInterval(timer);
  }, [enriching, refresh]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const next = await api<CatalogTrackPage>(`/music/transfer/tracks?${params(loadedPages.current + 1)}`);
      loadedPages.current += 1;
      setItems((current) => [...(current ?? []), ...next.items]);
      setPages({ loaded: loadedPages.current, total: next.pages, count: next.total });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить каталог");
    } finally {
      setLoadingMore(false);
    }
  };

  const updateItem = (updated: CatalogTrack) => {
    setItems((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? null);
  };

  const albums = useMemo(() => albumItems ? groupAlbums(albumItems) : null, [albumItems]);
  const heroSource = items?.map((item) => catalogArtworkSource(item, 64)).find(Boolean) ?? null;
  const heroColor = useArtworkColor(heroSource);
  const style = heroColor ? { "--catalog-tint": heroColor } as CSSProperties : undefined;
  const canUpload = Boolean(user?.is_admin);
  const emptyLibrary = items !== null && pages.count === 0 && filter === "all" && !term;

  return (
    <div className="catalog-page" style={style}>
      <div className="catalog-backdrop" aria-hidden="true" />
      <div className="content-page">
        <div className="page-heading">
          <div>
            <div className="eyebrow">musicLib · Каталог</div>
            <h1>Каталог</h1>
            <p>{items === null ? "Загружаем треки…" : emptyLibrary ? "Здесь собираются треки из перенесённой фонотеки — с файлами и без." : term ? `По запросу «${term}»: ${trackCountText(pages.count)}.` : `${trackCountText(pages.count)} ${FILTER_SUMMARY[filter]}`}</p>
          </div>
          <div className="page-actions">
            <Link className="button" href="/music/transfer"><ArrowRightLeft size={16} />Перенести фонотеку</Link>
          </div>
        </div>

        {!emptyLibrary && (
          <div className="catalog-toolbar">
            <div className="catalog-segmented" role="tablist" aria-label="Вид каталога">
              {VIEWS.map((option) => (
                <button key={option.value} type="button" role="tab" aria-selected={view === option.value} className={view === option.value ? "active" : ""} onClick={() => navigate({ view: option.value })}>{option.label}</button>
              ))}
            </div>
            <label className="catalog-search">
              <Search size={16} />
              <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, исполнитель или альбом" aria-label="Поиск по каталогу" />
            </label>
            <div className="catalog-filters" role="group" aria-label="Фильтр каталога">
              {CATALOG_FILTERS.map((option) => (
                <button key={option.value} type="button" aria-pressed={filter === option.value} className={filter === option.value ? "active" : ""} onClick={() => navigate({ status: option.value })}>{option.label}</button>
              ))}
            </div>
          </div>
        )}

        {error && <div className="form-error" role="alert">{error}</div>}

        {emptyLibrary ? (
          <EmptyState
            title="Каталог пока пуст"
            description="Загрузите экспорт фонотеки Apple Music — здесь появятся все треки с обложками, даже те, для которых ещё нет файла."
            action={<Link className="button primary" href="/music/transfer" style={{ marginTop: 16 }}><ArrowRightLeft size={16} />Перенести фонотеку</Link>}
          />
        ) : view !== "albums" ? (
          items === null ? <CatalogSkeleton /> : items.length ? (
            <>
              {view === "list" ? <CatalogList items={items} canUpload={canUpload} onUpdated={updateItem} /> : (
                <div className="catalog-grid" aria-label="Треки каталога">
                  {items.map((item) => <CatalogCard key={item.id} item={item} canUpload={canUpload} onUpdated={updateItem} />)}
                </div>
              )}
              {pages.loaded < pages.total && (
                <div className="catalog-more">
                  <button className="button" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? "Загружаем…" : "Показать ещё"}</button>
                </div>
              )}
            </>
          ) : <EmptyState title="Ничего не найдено" description="Попробуйте другой запрос или фильтр." />
        ) : albums === null ? <CatalogSkeleton /> : albums.length ? (
          <div className="catalog-grid" aria-label="Альбомы каталога">
            {albums.map((album) => <CatalogAlbumCard key={album.key} album={album} />)}
          </div>
        ) : <EmptyState title="Альбомов не найдено" description="У найденных треков нет названия альбома." />}
      </div>
    </div>
  );
}

function CatalogSkeleton() {
  return (
    <div className="catalog-grid" aria-label="Загрузка">
      {Array.from({ length: 12 }, (_, index) => <div className="catalog-card" key={index}><div className="catalog-card-art skeleton" /></div>)}
    </div>
  );
}
