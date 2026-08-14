"use client";

import { Menu, Plus, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function Topbar({ onMenu, onUpload }: { onMenu: () => void; onUpload: () => void }) {
  const router = useRouter();
  const params = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const search = (event: FormEvent) => {
    event.preventDefault();
    const value = query.trim();
    if (value) router.push(`/music/search?q=${encodeURIComponent(value)}`);
  };
  return (
    <header className="topbar">
      <button className="icon-button menu-trigger" onClick={onMenu} aria-label="Открыть меню"><Menu size={20} /></button>
      <form className="search-box" onSubmit={search} role="search">
        <Search size={17} />
        <input
          className="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
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
