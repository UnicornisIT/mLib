"use client";

import { Menu, Plus, Search } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const SEARCH_PATH = "/music/search";
const SEARCH_DELAY_MS = 250;

export function Topbar({ onMenu, onUpload }: { onMenu: () => void; onUpload: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const onSearchPage = pathname.startsWith(SEARCH_PATH);
  const urlQuery = onSearchPage ? params.get("q") ?? "" : "";
  const [query, setQuery] = useState(urlQuery);
  const [shownQuery, setShownQuery] = useState(urlQuery);
  const timer = useRef<number | undefined>(undefined);

  // Leaving the search page or opening a search link replaces the text; typing never fights the URL.
  if (urlQuery !== shownQuery) {
    setShownQuery(urlQuery);
    if (urlQuery !== query.trim()) setQuery(urlQuery);
  }

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const go = (text: string) => {
    window.clearTimeout(timer.current);
    const value = text.trim();
    const alreadyThere = window.location.pathname.startsWith(SEARCH_PATH);
    if (value) {
      const url = `${SEARCH_PATH}?${new URLSearchParams({ q: value })}`;
      // The first letter opens the results; further typing updates them without piling up history.
      if (alreadyThere) router.replace(url, { scroll: false });
      else router.push(url);
    } else if (alreadyThere) {
      router.replace(SEARCH_PATH, { scroll: false });
    }
  };

  const change = (value: string) => {
    setQuery(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => go(value), SEARCH_DELAY_MS);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    go(query);
  };

  return (
    <header className="topbar">
      <button className="icon-button menu-trigger" onClick={onMenu} aria-label="Открыть меню"><Menu size={20} /></button>
      <form className="search-box" onSubmit={submit} role="search">
        <Search size={17} />
        <input
          className="search-input"
          type="search"
          value={query}
          onChange={(event) => change(event.target.value)}
          placeholder="Треки, альбомы, исполнители"
          aria-label="Поиск по медиатеке"
        />
      </form>
      <div className="topbar-actions">
        <button className="button primary" onClick={onUpload}><Plus size={17} /><span>Добавить музыку</span></button>
      </div>
    </header>
  );
}
