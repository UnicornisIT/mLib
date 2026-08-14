"use client";

import {
  ArrowUpRight,
  BookOpenText,
  Check,
  Clapperboard,
  Edit3,
  Gift,
  Headphones,
  Heart,
  Link2,
  LoaderCircle,
  PackageCheck,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type {
  Wish,
  WishCategory,
  WishPage,
  WishesDashboard,
  WishStatus,
  WishTargetType,
} from "@/lib/types";
import type { TmdbCatalogPage, TmdbCatalogTitle } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

const categories = {
  watch: { label: "Хочу посмотреть", short: "Посмотреть", icon: Clapperboard, target: "movie" as WishTargetType },
  read: { label: "Хочу прочитать", short: "Прочитать", icon: BookOpenText, target: "book" as WishTargetType },
  listen: { label: "Хочу послушать", short: "Послушать", icon: Headphones, target: "album" as WishTargetType },
  buy: { label: "Хочу купить", short: "Купить", icon: Gift, target: "item" as WishTargetType },
};

const targetLabels: Record<WishTargetType, string> = {
  movie: "Фильм",
  series: "Сериал",
  book: "Книга",
  album: "Альбом",
  game: "Игра",
  item: "Вещь",
  other: "Другое",
};

const targetsByCategory: Record<WishCategory, WishTargetType[]> = {
  watch: ["movie", "series", "other"],
  read: ["book", "other"],
  listen: ["album", "other"],
  buy: ["game", "item", "other"],
};

function matchedHref(wish: Wish) {
  if (!wish.matched_item_id) return null;
  if (wish.matched_service === "movie") return `/movie/${wish.matched_item_id}`;
  if (wish.matched_service === "music") return `/albums/${wish.matched_item_id}`;
  if (wish.matched_service === "books") return "/books";
  if (wish.matched_service === "games") return "/games";
  if (wish.matched_service === "collections") return "/collections";
  return null;
}

function safeBackground(url: string | null) {
  return url ? { backgroundImage: `url(${JSON.stringify(url)})` } : undefined;
}

function WishCard({ wish, onEdit, onToggle }: {
  wish: Wish;
  onEdit: () => void;
  onToggle: () => void;
}) {
  const config = categories[wish.category];
  const Icon = config.icon;
  const libraryHref = matchedHref(wish);
  return (
    <article className={`wish-card wish-card-${wish.category} ${wish.status === "fulfilled" ? "fulfilled" : ""}`}>
      <div className="wish-card-accent" />
      <div className="wish-card-top">
        <span className="wish-card-category"><Icon size={14} />{config.label}</span>
        <span className="wish-card-type">{targetLabels[wish.target_type]}</span>
      </div>
      {wish.image_url ? <div className="wish-card-image" style={safeBackground(wish.image_url)} /> : (
        <div className="wish-card-glyph" aria-hidden="true"><Icon size={36} /><i /></div>
      )}
      <div className="wish-card-content">
        <h3>{wish.title}</h3>
        {wish.creator && <p className="wish-card-creator">{wish.creator}</p>}
        {wish.notes && <p className="wish-card-notes">{wish.notes}</p>}
      </div>
      {wish.status === "fulfilled" && (
        <div className={`wish-complete-note ${wish.auto_fulfilled ? "automatic" : ""}`}>
          <PackageCheck size={15} />
          <span><strong>{wish.auto_fulfilled ? "Найдено в библиотеке" : "Выполнено"}</strong><small>{wish.auto_fulfilled ? "wishLib отметил автоматически" : "Отмечено вручную"}</small></span>
        </div>
      )}
      <footer className="wish-card-footer">
        <div>
          {wish.reference_url && <a href={wish.reference_url} target="_blank" rel="noreferrer" aria-label="Открыть источник"><Link2 size={14} /></a>}
          {libraryHref && <a href={libraryHref} aria-label="Открыть в библиотеке"><ArrowUpRight size={14} /></a>}
          <button type="button" onClick={onEdit} aria-label="Редактировать"><Edit3 size={14} /></button>
        </div>
        <button type="button" className="wish-toggle" onClick={onToggle}>
          {wish.status === "fulfilled" ? <><RotateCcw size={14} />Вернуть</> : <><Check size={14} />Готово</>}
        </button>
      </footer>
    </article>
  );
}

type WishDraft = {
  category: WishCategory;
  target_type: WishTargetType;
  title: string;
  creator: string;
  notes: string;
  reference_url: string;
  image_url: string;
};

function draftFrom(wish: Wish | null, category: WishCategory): WishDraft {
  if (wish) return {
    category: wish.category,
    target_type: wish.target_type,
    title: wish.title,
    creator: wish.creator || "",
    notes: wish.notes || "",
    reference_url: wish.reference_url || "",
    image_url: wish.image_url || "",
  };
  return { category, target_type: categories[category].target, title: "", creator: "", notes: "", reference_url: "", image_url: "" };
}

function WishEditor({ wish, initialCategory, onClose, onSaved, onDeleted }: {
  wish: Wish | null;
  initialCategory: WishCategory;
  onClose: () => void;
  onSaved: (wish: Wish) => void;
  onDeleted: (id: string) => void;
}) {
  const [draft, setDraft] = useState(() => draftFrom(wish, initialCategory));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState<TmdbCatalogTitle[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionMessage, setSuggestionMessage] = useState("");
  const [suppressedSuggestion, setSuppressedSuggestion] = useState("");
  const feedback = useFeedback();
  const set = <K extends keyof WishDraft>(key: K, value: WishDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const query = draft.title.trim();
    if (draft.category !== "watch" || query.length < 2 || query === suppressedSuggestion) {
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      setSuggestionsLoading(true);
      setSuggestionMessage("");
      const mediaType = draft.target_type === "movie" || draft.target_type === "series" ? draft.target_type : "all";
      const params = new URLSearchParams({ q: query, media_type: mediaType, sort: "popular", page: "1" });
      try {
        const catalog = await api<TmdbCatalogPage>(`/movie/catalog?${params}`);
        if (!active) return;
        setSuggestions(catalog.items.slice(0, 6));
        if (!catalog.configured) setSuggestionMessage("Каталог фильмов не подключён в настройках movieLib");
        else if (!catalog.items.length) setSuggestionMessage("Совпадений в каталоге не найдено");
      } catch (caught) {
        if (active) setSuggestionMessage(caught instanceof Error ? caught.message : "Не удалось загрузить подсказки");
      } finally {
        if (active) setSuggestionsLoading(false);
      }
    }, 320);
    return () => { active = false; window.clearTimeout(timer); };
  }, [draft.category, draft.target_type, draft.title, suppressedSuggestion]);

  const changeCategory = (category: WishCategory) => {
    setDraft((current) => ({
      ...current,
      category,
      target_type: targetsByCategory[category].includes(current.target_type) ? current.target_type : categories[category].target,
    }));
    setSuggestions([]);
    setSuggestionsLoading(false);
    setSuggestionMessage("");
    setSuppressedSuggestion("");
  };

  const chooseMovie = (title: TmdbCatalogTitle) => {
    setDraft((current) => ({
      ...current,
      title: title.title,
      target_type: title.media_type,
      image_url: title.poster_url || current.image_url,
      reference_url: current.reference_url || `https://www.themoviedb.org/${title.media_type === "series" ? "tv" : "movie"}/${title.tmdb_id}`,
    }));
    setSuppressedSuggestion(title.title);
    setSuggestions([]);
    setSuggestionMessage("");
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    const payload = {
      ...draft,
      creator: draft.creator || null,
      notes: draft.notes || null,
      reference_url: draft.reference_url || null,
      image_url: draft.image_url || null,
    };
    try {
      const saved = await api<Wish>(wish ? `/wishes/${wish.id}` : "/wishes", { method: wish ? "PATCH" : "POST", body: payload });
      onSaved(saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить желание");
    } finally { setBusy(false); }
  };

  const remove = async () => {
    if (!wish || !await feedback.confirm({ title: "Удалить желание?", message: `«${wish.title}» будет удалено из списка желаний.`, confirmLabel: "Удалить желание", destructive: true })) return;
    setBusy(true); setError("");
    try { await api(`/wishes/${wish.id}`, { method: "DELETE" }); onDeleted(wish.id); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось удалить желание"); setBusy(false); }
  };

  return (
    <div className="modal-backdrop wish-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <form className="wish-editor" role="dialog" aria-modal="true" aria-labelledby="wish-editor-title" onSubmit={(event) => void submit(event)}>
        <header className="wish-editor-header">
          <div><span>{wish ? "Карточка желания" : "Новое желание"}</span><h2 id="wish-editor-title">{wish ? `Редактировать «${wish.title}»` : "Что добавим в очередь?"}</h2></div>
          <button type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button>
        </header>
        <div className="wish-editor-body">
          <fieldset className="wish-category-picker">
            <legend>Я хочу</legend>
            <div>{(Object.keys(categories) as WishCategory[]).map((category) => {
              const config = categories[category]; const Icon = config.icon;
              return <button type="button" className={draft.category === category ? "active" : ""} onClick={() => changeCategory(category)} key={category}><Icon size={18} /><span>{config.short}</span></button>;
            })}</div>
          </fieldset>
          <div className="wish-editor-grid">
            <label className="wish-wide wish-title-field">
              <span>Название *</span>
              <div className="wish-title-input-wrap">
                <input
                  className="input"
                  required
                  autoFocus
                  value={draft.title}
                  onChange={(event) => {
                    set("title", event.target.value);
                    setSuppressedSuggestion("");
                    setSuggestions([]);
                    setSuggestionsLoading(false);
                    setSuggestionMessage("");
                  }}
                  placeholder="Например, Dune: Part Three"
                  autoComplete="off"
                  role={draft.category === "watch" ? "combobox" : undefined}
                  aria-autocomplete={draft.category === "watch" ? "list" : "none"}
                  aria-expanded={draft.category === "watch" && (suggestions.length > 0 || Boolean(suggestionMessage))}
                  aria-controls="wish-movie-suggestions"
                />
                {draft.category === "watch" && suggestionsLoading && <LoaderCircle className="spin wish-suggestion-spinner" size={17} />}
              </div>
              {draft.category === "watch" && (suggestions.length > 0 || suggestionMessage) && (
                <div className="wish-movie-suggestions" id="wish-movie-suggestions" role="listbox" aria-label="Подсказки фильмов и сериалов">
                  {suggestions.map((title) => (
                    <button type="button" role="option" aria-selected="false" onClick={() => chooseMovie(title)} key={`${title.media_type}-${title.tmdb_id}`}>
                      <i className={title.poster_url ? "has-poster" : ""} style={safeBackground(title.poster_url)}>{!title.poster_url && <Clapperboard size={18} />}</i>
                      <span><strong>{title.title}</strong><small>{title.media_type === "series" ? "Сериал" : "Фильм"}{title.year ? ` · ${title.year}` : ""}{title.original_title && title.original_title !== title.title ? ` · ${title.original_title}` : ""}</small></span>
                      <Plus size={16} />
                    </button>
                  ))}
                  {suggestionMessage && <p>{suggestionMessage}</p>}
                  <footer>Подсказки из каталога movieLib</footer>
                </div>
              )}
            </label>
            <label><span>Тип</span><select className="select" value={draft.target_type} onChange={(event) => { set("target_type", event.target.value as WishTargetType); setSuggestions([]); setSuggestionMessage(""); }}>{targetsByCategory[draft.category].map((target) => <option value={target} key={target}>{targetLabels[target]}</option>)}</select></label>
            <label><span>{draft.category === "read" ? "Автор" : draft.category === "listen" ? "Исполнитель" : "Автор / бренд"}</span><input className="input" value={draft.creator} onChange={(event) => set("creator", event.target.value)} placeholder="Необязательно" /></label>
            <label className="wish-wide"><span>Заметка</span><textarea className="textarea" value={draft.notes} onChange={(event) => set("notes", event.target.value)} placeholder="Почему это заинтересовало, где искать…" /></label>
            <label><span>Ссылка на источник</span><input className="input" type="url" value={draft.reference_url} onChange={(event) => set("reference_url", event.target.value)} placeholder="https://…" /></label>
            <label><span>Ссылка на обложку</span><input className="input" type="url" value={draft.image_url} onChange={(event) => set("image_url", event.target.value)} placeholder="https://…" /></label>
          </div>
          <p className="wish-matching-note"><Sparkles size={14} /><span>Когда объект с таким названием появится в соответствующей библиотеке, wishLib закроет желание автоматически. Данные трекеров при этом не дублируются.</span></p>
        </div>
        {error && <div className="wish-form-error" role="alert">{error}</div>}
        <footer className="wish-editor-footer">
          {wish && <button type="button" className="wish-delete" onClick={() => void remove()} disabled={busy}><Trash2 size={15} />Удалить</button>}
          <button type="button" className="wish-secondary" onClick={onClose}>Отмена</button>
          <button type="submit" className="wish-primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}{wish ? "Сохранить" : "Добавить желание"}</button>
        </footer>
      </form>
    </div>
  );
}

export default function WishesPage() {
  const [library, setLibrary] = useState<WishPage | null>(null);
  const [dashboard, setDashboard] = useState<WishesDashboard | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<"all" | WishCategory>("all");
  const [status, setStatus] = useState<WishStatus>("active");
  const [sort, setSort] = useState("updated");
  const [editing, setEditing] = useState<Wish | null | undefined>(undefined);
  const [initialCategory, setInitialCategory] = useState<WishCategory>("watch");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ category, status, sort });
    if (query.trim()) params.set("q", query.trim());
    try {
      const [wishes, stats] = await Promise.all([api<WishPage>(`/wishes?${params}`), api<WishesDashboard>("/wishes/dashboard")]);
      setLibrary(wishes); setDashboard(stats); setError("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось открыть wishLib"); }
    finally { setLoading(false); }
  }, [category, query, sort, status]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 220); return () => window.clearTimeout(timer); }, [load]);

  const openNew = (wishCategory: WishCategory = category === "all" ? "watch" : category) => {
    setInitialCategory(wishCategory); setEditing(null);
  };
  const toggle = async (wish: Wish) => {
    try {
      await api<Wish>(`/wishes/${wish.id}`, { method: "PATCH", body: { status: wish.status === "active" ? "fulfilled" : "active" } });
      void load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось изменить желание"); }
  };
  const grouped = useMemo(() => {
    const result: Record<WishCategory, Wish[]> = { watch: [], read: [], listen: [], buy: [] };
    for (const wish of library?.items || []) result[wish.category].push(wish);
    return result;
  }, [library]);
  const visibleCategories = category === "all" ? (Object.keys(categories) as WishCategory[]) : [category];

  return (
    <div className="wishes-page">
      <nav className="wishes-nav" aria-label="Навигация wishLib">
        <a href="#queue">Очередь</a><a href="#categories">Категории</a><button type="button" onClick={() => setStatus(status === "active" ? "fulfilled" : "active")}>{status === "active" ? "Выполненные" : "Активные"}</button>
        <button type="button" className="wish-primary wishes-add" onClick={() => openNew()}><Plus size={16} />Добавить желание</button>
      </nav>
      <div className="service-page-content">
        <section className="wishes-hero">
          <div className="wishes-hero-orbit" aria-hidden="true"><i /><i /><i /><i /><Heart size={52} fill="currentColor" /></div>
          <div className="wishes-hero-copy">
            <span className="wishes-overline"><Sparkles size={14} />Сквозная очередь mLib</span>
            <h1>Сначала<br /><em>пожелать.</em></h1>
            <p>Фильмы, книги, альбомы, игры и вещи — один спокойный список без повторения функций ваших библиотек.</p>
            <button type="button" className="wish-primary" onClick={() => openNew()}><Plus size={16} />Добавить желание</button>
          </div>
          <div className="wishes-hero-stats">
            <span><small>В очереди</small><strong>{dashboard?.active || 0}</strong></span>
            <span><small>Выполнено</small><strong>{dashboard?.fulfilled || 0}</strong></span>
            <span><small>Найдено автоматически</small><strong>{dashboard?.auto_fulfilled || 0}</strong></span>
          </div>
        </section>

        <section className="wishes-quick-add" id="categories" aria-label="Быстрое добавление по категориям">
          {(Object.keys(categories) as WishCategory[]).map((key) => {
            const config = categories[key]; const Icon = config.icon;
            return <button type="button" className={`wish-quick-${key}`} onClick={() => openNew(key)} key={key}><span><Icon size={19} /></span><div><small>{config.label}</small><strong>{dashboard?.by_category[key] || 0} в очереди</strong></div><Plus size={16} /></button>;
          })}
        </section>

        <section className="wishes-library" id="queue">
          <header className="wishes-section-heading">
            <div><span>{status === "active" ? "На потом — в хорошем смысле" : "История желаний"}</span><h2>{status === "active" ? "Моя очередь" : "Выполнено"}</h2></div>
            <div className="wishes-status-switch"><button type="button" className={status === "active" ? "active" : ""} onClick={() => setStatus("active")}>Активные</button><button type="button" className={status === "fulfilled" ? "active" : ""} onClick={() => setStatus("fulfilled")}>Выполненные</button></div>
          </header>
          <div className="wishes-toolbar">
            <label><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, автор или заметка" aria-label="Поиск желаний" /></label>
            <div>{(["all", ...Object.keys(categories)] as Array<"all" | WishCategory>).map((key) => <button type="button" className={category === key ? "active" : ""} onClick={() => setCategory(key)} key={key}>{key === "all" ? "Все" : categories[key].short}</button>)}</div>
            <select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Сортировка"><option value="updated">Недавно изменённые</option><option value="created">Сначала новые</option><option value="title">По названию</option></select>
          </div>
          {error && <div className="wishes-error" role="alert">{error}</div>}
          {loading ? <div className="wishes-loading"><LoaderCircle className="spin" size={28} /><span>Сверяем желания с библиотеками…</span></div>
          : library?.items.length ? <div className="wishes-groups">{visibleCategories.map((key) => grouped[key].length > 0 && <section className={`wish-group wish-group-${key}`} key={key}><header><span>{categories[key].label}</span><small>{grouped[key].length}</small></header><div>{grouped[key].map((wish) => <WishCard wish={wish} onEdit={() => setEditing(wish)} onToggle={() => void toggle(wish)} key={wish.id} />)}</div></section>)}</div>
          : <div className="wishes-empty"><span>{status === "active" ? <Heart size={34} /> : <PackageCheck size={34} />}</span><h3>{query || category !== "all" ? "Ничего не найдено" : status === "active" ? "Очередь пока свободна" : "Выполненных желаний пока нет"}</h3><p>{query || category !== "all" ? "Измените фильтр или поисковый запрос." : status === "active" ? "Добавьте фильм, книгу, альбом, игру или любую вещь — wishLib сам заметит, когда они появятся в ваших библиотеках." : "Здесь появятся желания, которые вы выполнили или которые wishLib нашёл в библиотеке."}</p>{status === "active" && !query && category === "all" && <button type="button" className="wish-primary" onClick={() => openNew()}><Plus size={16} />Добавить желание</button>}</div>}
        </section>
      </div>
      {editing !== undefined && <WishEditor wish={editing} initialCategory={initialCategory} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); void load(); }} onDeleted={() => { setEditing(undefined); void load(); }} />}
    </div>
  );
}
