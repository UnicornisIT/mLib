"use client";

import {
  Award,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  Edit3,
  Gamepad2,
  ImageIcon,
  LoaderCircle,
  Plus,
  Search,
  ShoppingBag,
  Sparkles,
  Star,
  Trash2,
  Trophy,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Game, GamePage, GamePlatform, GamesDashboard, GameStatus } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

const platforms: Array<"all" | GamePlatform> = ["all", "PC", "PlayStation", "Xbox", "Switch", "Retro"];
const statuses: { value: GameStatus; label: string; short: string }[] = [
  { value: "not_started", label: "Не начато", short: "Не начато" },
  { value: "playing", label: "Играю", short: "Играю" },
  { value: "completed", label: "Пройдено", short: "Пройдено" },
  { value: "completed_100", label: "100%", short: "100%" },
  { value: "abandoned", label: "Заброшено", short: "Заброшено" },
];

const statusLabel = (value: GameStatus) => statuses.find((item) => item.value === value)?.label || value;

function formatPlaytime(minutes: number) {
  if (!minutes) return "0 ч";
  if (minutes < 60) return `${minutes} мин`;
  const hours = minutes / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} ч`;
}

function safeBackground(url: string | null) {
  return url ? { backgroundImage: `url(${JSON.stringify(url)})` } : undefined;
}

function GameArtwork({ game, className = "" }: { game: Game; className?: string }) {
  return (
    <div
      className={`game-artwork ${game.cover_url ? "has-image" : ""} ${className}`}
      style={safeBackground(game.cover_url)}
      role="img"
      aria-label={game.cover_url ? `Обложка игры «${game.title}»` : `Обложка для «${game.title}» не добавлена`}
    >
      {!game.cover_url && <><Gamepad2 size={38} /><span>{game.title.slice(0, 1)}</span></>}
    </div>
  );
}

function GameCard({ game, onOpen }: { game: Game; onOpen: () => void }) {
  const achievementPercent = game.achievements_total
    ? Math.min(100, Math.round((game.achievements_unlocked / game.achievements_total) * 100))
    : 0;
  return (
    <article className="game-card">
      <button type="button" className="game-card-open" onClick={onOpen} aria-label={`Открыть «${game.title}»`} />
      <div className="game-card-cover">
        <GameArtwork game={game} />
        <span className="game-platform-badge">{game.platform}</span>
        <span className={`game-status game-status-${game.status}`}>{statusLabel(game.status)}</span>
        {game.personal_rating !== null && <span className="game-rating"><Star size={12} fill="currentColor" />{game.personal_rating}</span>}
      </div>
      <div className="game-card-copy">
        <div className="game-card-title"><h3>{game.title}</h3><ChevronRight size={18} /></div>
        <p>{game.developer || "Разработчик не указан"}{game.release_year ? ` · ${game.release_year}` : ""}</p>
        <div className="game-card-meta">
          <span><Clock3 size={13} />{formatPlaytime(game.playtime_minutes)}</span>
          <span><Trophy size={13} />{game.achievements_unlocked}/{game.achievements_total || "—"}</span>
        </div>
        <div className="game-achievement-line"><i style={{ width: `${achievementPercent}%` }} /></div>
      </div>
    </article>
  );
}

type Draft = {
  title: string; developer: string; publisher: string; release_year: string; genre: string;
  platform: GamePlatform; purchase_date: string; acquired_from: string; status: GameStatus;
  playtime_hours: string; personal_rating: string; achievements_unlocked: string;
  achievements_total: string; cover_url: string; screenshots: string;
};

const blankDraft: Draft = {
  title: "", developer: "", publisher: "", release_year: "", genre: "", platform: "PC",
  purchase_date: "", acquired_from: "", status: "not_started", playtime_hours: "",
  personal_rating: "", achievements_unlocked: "", achievements_total: "", cover_url: "", screenshots: "",
};

function draftFrom(game: Game | null): Draft {
  if (!game) return blankDraft;
  return {
    title: game.title, developer: game.developer || "", publisher: game.publisher || "",
    release_year: game.release_year?.toString() || "", genre: game.genre || "", platform: game.platform,
    purchase_date: game.purchase_date || "", acquired_from: game.acquired_from || "", status: game.status,
    playtime_hours: game.playtime_minutes ? String(Number((game.playtime_minutes / 60).toFixed(1))) : "",
    personal_rating: game.personal_rating?.toString() || "", achievements_unlocked: game.achievements_unlocked?.toString() || "",
    achievements_total: game.achievements_total?.toString() || "", cover_url: game.cover_url || "",
    screenshots: game.screenshots.join("\n"),
  };
}

function GameEditor({ game, onClose, onSaved, onDeleted }: {
  game: Game | null; onClose: () => void; onSaved: (game: Game) => void; onDeleted: (id: string) => void;
}) {
  const [draft, setDraft] = useState(() => draftFrom(game));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const feedback = useFeedback();
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError("");
    const nullableNumber = (value: string) => value.trim() ? Number(value) : null;
    const payload = {
      title: draft.title.trim(), developer: draft.developer || null, publisher: draft.publisher || null,
      release_year: nullableNumber(draft.release_year), genre: draft.genre || null, platform: draft.platform,
      purchase_date: draft.purchase_date || null, acquired_from: draft.acquired_from || null, status: draft.status,
      playtime_minutes: Math.max(0, Math.round((Number(draft.playtime_hours) || 0) * 60)),
      personal_rating: nullableNumber(draft.personal_rating),
      achievements_unlocked: Math.max(0, Number(draft.achievements_unlocked) || 0),
      achievements_total: Math.max(0, Number(draft.achievements_total) || 0), cover_url: draft.cover_url || null,
      screenshots: draft.screenshots.split("\n").map((url) => url.trim()).filter(Boolean),
    };
    try {
      const saved = await api<Game>(game ? `/games/${game.id}` : "/games", { method: game ? "PATCH" : "POST", body: payload });
      onSaved(saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить игру");
    } finally { setBusy(false); }
  };

  const remove = async () => {
    if (!game || !await feedback.confirm({ title: "Удалить игру?", message: `«${game.title}» будет удалена из gameLib.`, confirmLabel: "Удалить игру", destructive: true })) return;
    setBusy(true); setError("");
    try { await api(`/games/${game.id}`, { method: "DELETE" }); onDeleted(game.id); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось удалить игру"); setBusy(false); }
  };

  return (
    <div className="modal-backdrop game-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <form className="game-editor" onSubmit={(event) => void submit(event)} role="dialog" aria-modal="true" aria-labelledby="game-editor-title">
        <header className="game-editor-header">
          <div><span>{game ? "Карточка игры" : "Новая игра"}</span><h2 id="game-editor-title">{game ? `Редактировать «${game.title}»` : "Добавить в gameLib"}</h2></div>
          <button type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button>
        </header>
        <div className="game-editor-body">
          <aside className="game-cover-editor">
            <div className={`game-cover-preview ${draft.cover_url ? "has-image" : ""}`} style={safeBackground(draft.cover_url || null)}>
              {!draft.cover_url && <><ImageIcon size={35} /><span>Обложка появится здесь</span></>}
            </div>
            <label><span>Ссылка на обложку</span><input className="input" type="url" value={draft.cover_url} onChange={(e) => set("cover_url", e.target.value)} placeholder="https://…" /></label>
            <label><span>Ссылки на скриншоты</span><textarea className="textarea" value={draft.screenshots} onChange={(e) => set("screenshots", e.target.value)} placeholder="Каждая ссылка с новой строки" /></label>
          </aside>
          <div className="game-editor-fields">
            <label className="game-wide"><span>Название *</span><input className="input" required autoFocus value={draft.title} onChange={(e) => set("title", e.target.value)} placeholder="Например, Disco Elysium" /></label>
            <label><span>Разработчик</span><input className="input" value={draft.developer} onChange={(e) => set("developer", e.target.value)} /></label>
            <label><span>Издатель</span><input className="input" value={draft.publisher} onChange={(e) => set("publisher", e.target.value)} /></label>
            <label><span>Год</span><input className="input" type="number" min="1950" max="2100" value={draft.release_year} onChange={(e) => set("release_year", e.target.value)} /></label>
            <label><span>Жанр</span><input className="input" value={draft.genre} onChange={(e) => set("genre", e.target.value)} placeholder="RPG, стратегия…" /></label>
            <label><span>Платформа</span><select className="select" value={draft.platform} onChange={(e) => set("platform", e.target.value as GamePlatform)}>{platforms.slice(1).map((value) => <option key={value}>{value}</option>)}</select></label>
            <label><span>Статус</span><select className="select" value={draft.status} onChange={(e) => set("status", e.target.value as GameStatus)}>{statuses.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>
            <label><span>Дата покупки</span><input className="input" type="date" value={draft.purchase_date} onChange={(e) => set("purchase_date", e.target.value)} /></label>
            <label><span>Где приобретена</span><input className="input" value={draft.acquired_from} onChange={(e) => set("acquired_from", e.target.value)} placeholder="Steam, PS Store…" /></label>
            <label><span>Время в игре, ч</span><input className="input" type="number" min="0" step="0.1" value={draft.playtime_hours} onChange={(e) => set("playtime_hours", e.target.value)} /></label>
            <label><span>Личная оценка</span><input className="input" type="number" min="0" max="10" step="0.5" value={draft.personal_rating} onChange={(e) => set("personal_rating", e.target.value)} placeholder="из 10" /></label>
            <label><span>Достижений получено</span><input className="input" type="number" min="0" value={draft.achievements_unlocked} onChange={(e) => set("achievements_unlocked", e.target.value)} /></label>
            <label><span>Достижений всего</span><input className="input" type="number" min="0" value={draft.achievements_total} onChange={(e) => set("achievements_total", e.target.value)} /></label>
          </div>
        </div>
        {error && <div className="game-form-error" role="alert">{error}</div>}
        <footer className="game-editor-footer">
          {game && <button type="button" className="game-delete" onClick={() => void remove()} disabled={busy}><Trash2 size={15} />Удалить</button>}
          <button type="button" className="game-secondary-button" onClick={onClose}>Отмена</button>
          <button type="submit" className="game-primary-button" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}{game ? "Сохранить" : "Добавить игру"}</button>
        </footer>
      </form>
    </div>
  );
}

function GameDetails({ game, onClose, onEdit, onStatus }: { game: Game; onClose: () => void; onEdit: () => void; onStatus: (status: GameStatus) => void }) {
  const shots = game.screenshots.slice(0, 6);
  return (
    <div className="modal-backdrop game-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="game-details" role="dialog" aria-modal="true" aria-labelledby="game-details-title">
        <button className="game-details-close" type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button>
        <div className="game-details-visual">
          <GameArtwork game={game} className="game-details-cover" />
          <div className="game-details-platform"><Gamepad2 size={15} />{game.platform}</div>
        </div>
        <div className="game-details-copy">
          <div className="game-details-kicker"><span className={`game-status game-status-${game.status}`}>{statusLabel(game.status)}</span>{game.genre && <small>{game.genre}</small>}</div>
          <h2 id="game-details-title">{game.title}</h2>
          <p className="game-details-by">{game.developer || "Разработчик не указан"}{game.publisher && game.publisher !== game.developer ? ` · ${game.publisher}` : ""}{game.release_year ? ` · ${game.release_year}` : ""}</p>
          <div className="game-details-stats">
            <span><Clock3 size={18} /><small>Время в игре</small><strong>{formatPlaytime(game.playtime_minutes)}</strong></span>
            <span><Star size={18} /><small>Моя оценка</small><strong>{game.personal_rating ?? "—"}<i>{game.personal_rating !== null ? "/10" : ""}</i></strong></span>
            <span><Trophy size={18} /><small>Достижения</small><strong>{game.achievements_unlocked}<i>/{game.achievements_total || "—"}</i></strong></span>
          </div>
          <div className="game-details-facts">
            <span><CalendarDays size={15} /><small>Дата покупки</small><strong>{game.purchase_date ? new Date(`${game.purchase_date}T00:00:00`).toLocaleDateString("ru-RU") : "Не указана"}</strong></span>
            <span><ShoppingBag size={15} /><small>Где приобретена</small><strong>{game.acquired_from || "Не указано"}</strong></span>
          </div>
          {shots.length > 0 && <div className="game-screenshots"><div><ImageIcon size={14} /><span>Скриншоты</span><small>{shots.length}</small></div><section>{shots.map((url, index) => <a href={url} target="_blank" rel="noreferrer" style={safeBackground(url)} aria-label={`Открыть скриншот ${index + 1}`} key={`${url}-${index}`} />)}</section></div>}
          <div className="game-status-flow" aria-label="Статус прохождения">{statuses.map((item, index) => <button type="button" className={game.status === item.value ? "active" : ""} onClick={() => onStatus(item.value)} key={item.value}><i>{index + 1}</i><span>{item.short}</span></button>)}</div>
          <button type="button" className="game-edit-button" onClick={onEdit}><Edit3 size={16} />Редактировать карточку</button>
        </div>
      </section>
    </div>
  );
}

export default function GamesPage() {
  const [library, setLibrary] = useState<GamePage | null>(null);
  const [dashboard, setDashboard] = useState<GamesDashboard | null>(null);
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState<"all" | GamePlatform>("all");
  const [status, setStatus] = useState<"all" | GameStatus>("all");
  const [sort, setSort] = useState("updated");
  const [selected, setSelected] = useState<Game | null>(null);
  const [editing, setEditing] = useState<Game | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ platform, status, sort });
    if (query.trim()) params.set("q", query.trim());
    try {
      const [games, stats] = await Promise.all([api<GamePage>(`/games?${params}`), api<GamesDashboard>("/games/dashboard")]);
      setLibrary(games); setDashboard(stats); setError("");
      setSelected((current) => current ? games.items.find((game) => game.id === current.id) || current : null);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось открыть gameLib"); }
    finally { setLoading(false); }
  }, [platform, query, sort, status]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 220); return () => window.clearTimeout(timer); }, [load]);
  const featured = useMemo(() => library?.items.find((game) => game.status === "playing") || library?.items[0] || null, [library]);

  const saved = (game: Game) => { setEditing(undefined); setSelected(game); void load(); };
  const deleted = (id: string) => { setEditing(undefined); if (selected?.id === id) setSelected(null); void load(); };
  const changeStatus = async (gameStatus: GameStatus) => {
    if (!selected || selected.status === gameStatus) return;
    try { const updated = await api<Game>(`/games/${selected.id}`, { method: "PATCH", body: { status: gameStatus } }); setSelected(updated); void load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось изменить статус"); }
  };

  return (
    <div className="games-page">
      <nav className="games-nav" aria-label="Навигация gameLib">
        <a href="#library">Библиотека</a><a href="#playing">Сейчас играю</a><a href="#platforms">Платформы</a>
        <button type="button" className="game-primary-button games-add" onClick={() => setEditing(null)}><Plus size={16} />Добавить игру</button>
      </nav>
      <div className="service-page-content">
        <section className="games-hero" id="playing">
          <div className="games-hero-grid" aria-hidden="true" />
          <div className="games-hero-copy">
            <span className="games-overline"><Sparkles size={14} />Личная игротека</span>
            <h1>Ваши миры.<br /><em>Ваш прогресс.</em></h1>
            <p>Игры всех поколений — с историей покупок, часами, достижениями и тем самым статусом «ещё один квест».</p>
            <button type="button" className="game-primary-button" onClick={() => setEditing(null)}><Plus size={16} />Добавить игру</button>
          </div>
          {featured ? <button type="button" className="games-featured" onClick={() => setSelected(featured)}>
            <GameArtwork game={featured} /><span>Сейчас в фокусе</span><strong>{featured.title}</strong><small>{statusLabel(featured.status)} · {formatPlaytime(featured.playtime_minutes)}</small>
          </button> : <div className="games-hero-console" aria-hidden="true"><i /><Gamepad2 size={88} /><span>PLAYER ONE</span></div>}
          <div className="games-stats">
            <span><small>В библиотеке</small><strong>{dashboard?.total || 0}</strong><i>игр</i></span>
            <span><small>Сейчас играю</small><strong>{dashboard?.playing || 0}</strong><i>активно</i></span>
            <span><small>Время в игре</small><strong>{Math.round((dashboard?.playtime_minutes || 0) / 60)}</strong><i>часов</i></span>
            <span><small>Закрыто на 100%</small><strong>{dashboard?.completed_100 || 0}</strong><i>идеально</i></span>
          </div>
        </section>

        <section className="games-library" id="library">
          <header className="games-section-heading"><div><span>Коллекция игрока</span><h2>Моя библиотека</h2></div><p>{library?.total || 0} игр · {dashboard?.completed || 0} пройдено</p></header>
          <div className="games-toolbar" id="platforms">
            <label className="games-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, студия или жанр" aria-label="Поиск игр" /></label>
            <div className="games-platforms" aria-label="Платформа">{platforms.map((item) => <button type="button" className={platform === item ? "active" : ""} onClick={() => setPlatform(item)} key={item}>{item === "all" ? "Все" : item}</button>)}</div>
            <select className="games-filter" value={status} onChange={(event) => setStatus(event.target.value as "all" | GameStatus)} aria-label="Статус прохождения"><option value="all">Все статусы</option>{statuses.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select>
            <select className="games-filter" value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Сортировка"><option value="updated">Недавно изменённые</option><option value="title">По названию</option><option value="year">По году</option><option value="rating">По оценке</option><option value="playtime">По времени в игре</option></select>
          </div>

          {error && <div className="games-error" role="alert">{error}</div>}
          {loading ? <div className="games-loading"><LoaderCircle className="spin" size={28} /><span>Загружаем сохранение…</span></div>
          : library?.items.length ? <div className="games-grid">{library.items.map((game) => <GameCard game={game} onOpen={() => setSelected(game)} key={game.id} />)}</div>
          : <div className="games-empty"><span><Gamepad2 size={34} /></span><h3>{query || platform !== "all" || status !== "all" ? "Ничего не найдено" : "Ваша игротека начинается здесь"}</h3><p>{query || platform !== "all" || status !== "all" ? "Измените фильтры или поисковый запрос." : "Добавьте первую игру — обложка, платформа, прогресс и достижения соберутся в одной красивой карточке."}</p>{!query && platform === "all" && status === "all" && <button type="button" className="game-primary-button" onClick={() => setEditing(null)}><Plus size={16} />Добавить игру</button>}</div>}
        </section>
        <div className="games-future"><Award size={17} /><span><strong>Следующий уровень:</strong> импорт библиотеки Steam с часами и достижениями.</span></div>
      </div>

      {selected && editing === undefined && <GameDetails game={selected} onClose={() => setSelected(null)} onEdit={() => setEditing(selected)} onStatus={(value) => void changeStatus(value)} />}
      {editing !== undefined && <GameEditor game={editing} onClose={() => setEditing(undefined)} onSaved={saved} onDeleted={deleted} />}
    </div>
  );
}
