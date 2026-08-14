"use client";

import { BookOpenText, Headphones, LibraryBig, Plus, Search, SlidersHorizontal, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BookCard } from "@/components/BookCard";
import { BookDetailsDialog } from "@/components/BookDetailsDialog";
import { BookUploadDialog } from "@/components/BookUploadDialog";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { Book, BookPage, BooksDashboard } from "@/lib/types";

type Filter = "all" | "ebook" | "audiobook";

function bookCountLabel(count: number) {
  const lastTwo = count % 100;
  if (lastTwo >= 11 && lastTwo <= 14) return "книг";
  const last = count % 10;
  if (last === 1) return "книга";
  if (last >= 2 && last <= 4) return "книги";
  return "книг";
}

export default function BooksPage() {
  const [library, setLibrary] = useState<BookPage | null>(null);
  const [dashboard, setDashboard] = useState<BooksDashboard | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("added");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selected, setSelected] = useState<Book | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams({ media_type: filter, sort });
    if (query.trim()) params.set("q", query.trim());
    try {
      const [books, stats] = await Promise.all([
        api<BookPage>(`/books?${params}`),
        api<BooksDashboard>("/books/dashboard"),
      ]);
      setLibrary(books); setDashboard(stats); setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось открыть bookLib");
    }
  }, [filter, query, sort]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer); }, [load]);
  const recent = useMemo(() => library?.items.slice(0, 6) || [], [library]);
  const hasBooks = Boolean(dashboard?.total);

  return (
    <div className="books-page">
      <header className="books-nav">
        <nav aria-label="Разделы bookLib"><a href="#library">Библиотека</a><a href="#recent">Недавние</a><button type="button" onClick={() => setUploadOpen(true)}>Добавить книгу</button></nav>
        <button className="button primary book-primary books-add" type="button" onClick={() => setUploadOpen(true)}><Plus size={17} />Добавить книгу</button>
      </header>

      <div className="service-page-content">
        <section className={`books-hero ${hasBooks ? "" : "empty"}`}>
          <div className="books-hero-copy">
            <div className="books-kicker">Личная книжная полка</div>
            <h1>Все истории <br />в одном месте.</h1>
            <p>Загружайте электронные и аудиокниги вручную, добавляйте свои обложки и собирайте библиотеку, которая выглядит именно по-вашему.</p>
            <button className="button primary book-primary" type="button" onClick={() => setUploadOpen(true)}><Plus size={18} />Загрузить первую книгу</button>
          </div>
          <div className="books-hero-art" aria-hidden="true">
            <div className="hero-book hero-book-one"><i /><span>mLib<br /><strong>READS</strong></span></div>
            <div className="hero-book hero-book-two"><i /><span>YOUR<br /><strong>STORIES</strong></span></div>
            <div className="hero-book hero-book-three"><i /><Headphones size={32} /></div>
          </div>
          {dashboard && <div className="books-stats">
            <span><BookOpenText size={18} /><strong>{dashboard.ebooks}</strong><small>электронных</small></span>
            <span><Headphones size={18} /><strong>{dashboard.audiobooks}</strong><small>аудиокниг</small></span>
            <span><UsersRound size={18} /><strong>{dashboard.authors}</strong><small>авторов</small></span>
            <span><LibraryBig size={18} /><strong>{formatBytes(dashboard.storage_bytes)}</strong><small>в хранилище</small></span>
          </div>}
        </section>

        {error && <div className="form-error books-error">{error}</div>}

        {recent.length > 0 && filter === "all" && !query && <section className="books-section" id="recent">
          <div className="books-section-heading"><div><span>Последние пополнения</span><h2>Недавно добавленные</h2></div></div>
          <div className="books-grid books-recent-grid">{recent.map((book) => <BookCard key={book.id} book={book} onOpen={() => setSelected(book)} />)}</div>
        </section>}

        <section className="books-section" id="library">
          <div className="books-section-heading books-library-heading">
            <div><span>Ваша коллекция</span><h2>Библиотека</h2></div>
            <div className="books-count" aria-label={`${library?.total ?? 0} ${bookCountLabel(library?.total ?? 0)} в коллекции`}>
              <LibraryBig size={15} aria-hidden="true" />
              <strong>{library?.total ?? 0}</strong>
              <span>{bookCountLabel(library?.total ?? 0)}</span>
            </div>
          </div>
          <div className="books-toolbar">
            <div className="books-filters" role="group" aria-label="Тип книги">
              <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>Все <span>{dashboard?.total || 0}</span></button>
              <button className={filter === "ebook" ? "active" : ""} onClick={() => setFilter("ebook")}><BookOpenText size={15} />Электронные</button>
              <button className={filter === "audiobook" ? "active" : ""} onClick={() => setFilter("audiobook")}><Headphones size={15} />Аудиокниги</button>
            </div>
            <label className="books-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, автор, жанр…" /></label>
            <label className="books-sort"><SlidersHorizontal size={16} /><select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Сортировка"><option value="added">Сначала новые</option><option value="title">По названию</option><option value="author">По автору</option><option value="year">По году</option></select></label>
          </div>

          {library === null ? <div className="books-loading"><span className="loading-mark" /></div> : library.items.length ? (
            <div className="books-grid">{library.items.map((book) => <BookCard key={book.id} book={book} onOpen={() => setSelected(book)} />)}</div>
          ) : (
            <div className="books-empty">
              <span>{query ? <Search size={31} /> : <BookOpenText size={31} />}</span>
              <h3>{query ? "Ничего не найдено" : "На полке пока пусто"}</h3>
              <p>{query ? "Попробуйте другое название, автора или измените фильтр." : "Добавьте электронную или аудиокнигу с компьютера — обложку и описание вы выбираете сами."}</p>
              {!query && <button className="button primary book-primary" type="button" onClick={() => setUploadOpen(true)}><Plus size={16} />Добавить книгу</button>}
            </div>
          )}
        </section>
      </div>

      <BookUploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={(book) => { void load(); setSelected(book); }} />
      {selected && <BookDetailsDialog book={selected} onClose={() => setSelected(null)} onDeleted={() => { setSelected(null); void load(); }} />}
    </div>
  );
}
