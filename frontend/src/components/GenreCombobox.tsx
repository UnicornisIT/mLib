"use client";

import { Check, ChevronDown, Search } from "lucide-react";
import { FocusEvent, KeyboardEvent, useEffect, useId, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { MUSIC_GENRES } from "@/lib/music-genres";
import type { Genre } from "@/lib/types";

const RESULT_LIMIT = 80;
const POPULAR_GENRES = [
  "pop",
  "rock",
  "hip hop",
  "electronic",
  "r&b",
  "indie",
  "alternative rock",
  "dance",
  "jazz",
  "classical",
  "metal",
  "folk",
  "country",
  "blues",
  "reggae",
  "soul",
  "funk",
  "punk",
  "house",
  "techno",
  "ambient",
  "latin",
  "k-pop",
  "soundtrack",
];

const normalized = (value: string) => value.trim().toLocaleLowerCase();

export function GenreCombobox({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [libraryGenres, setLibraryGenres] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    void api<Genre[]>("/music/genres")
      .then((genres) => {
        if (active) setLibraryGenres(genres.map((genre) => genre.name));
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const allGenres = useMemo(() => {
    const unique = new Map<string, string>();
    for (const genre of [...libraryGenres, ...MUSIC_GENRES]) {
      const key = normalized(genre);
      if (key && !unique.has(key)) unique.set(key, genre);
    }
    return [...unique.values()];
  }, [libraryGenres]);

  const matches = useMemo(() => {
    const query = normalized(value);
    const libraryOrder = new Map(libraryGenres.map((genre, index) => [normalized(genre), index]));
    const popularOrder = new Map(POPULAR_GENRES.map((genre, index) => [genre, index]));
    return allGenres
      .filter((genre) => !query || normalized(genre).includes(query))
      .sort((left, right) => {
        const leftKey = normalized(left);
        const rightKey = normalized(right);
        const leftLibrary = libraryOrder.get(leftKey);
        const rightLibrary = libraryOrder.get(rightKey);
        if (leftLibrary !== undefined || rightLibrary !== undefined) {
          if (leftLibrary === undefined) return 1;
          if (rightLibrary === undefined) return -1;
          return leftLibrary - rightLibrary;
        }
        const leftStarts = query && leftKey.startsWith(query) ? 0 : 1;
        const rightStarts = query && rightKey.startsWith(query) ? 0 : 1;
        if (leftStarts !== rightStarts) return leftStarts - rightStarts;
        if (!query) {
          const leftPopular = popularOrder.get(leftKey) ?? Number.MAX_SAFE_INTEGER;
          const rightPopular = popularOrder.get(rightKey) ?? Number.MAX_SAFE_INTEGER;
          if (leftPopular !== rightPopular) return leftPopular - rightPopular;
        }
        return left.localeCompare(right);
      });
  }, [allGenres, libraryGenres, value]);

  const visibleMatches = matches.slice(0, RESULT_LIMIT);
  const choose = (genre: string) => {
    onChange(genre);
    setOpen(false);
    setActiveIndex(-1);
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, visibleMatches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => index <= 0 ? visibleMatches.length - 1 : index - 1);
    } else if (event.key === "Enter" && open && activeIndex >= 0) {
      event.preventDefault();
      choose(visibleMatches[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  };
  const handleBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  return (
    <div className="field">
      <label htmlFor={`${listboxId}-input`}>Жанр</label>
      <div className="genre-combobox" onBlur={handleBlur}>
        <Search className="genre-combobox-search" size={16} aria-hidden="true" />
        <input
          id={`${listboxId}-input`}
          className="input genre-combobox-input"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
          autoComplete="off"
          placeholder="Начните вводить жанр"
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        <button
          className="genre-combobox-toggle"
          type="button"
          aria-label={open ? "Скрыть список жанров" : "Показать список жанров"}
          onClick={() => setOpen((shown) => !shown)}
        >
          <ChevronDown size={17} aria-hidden="true" />
        </button>
        {open && (
          <div className="genre-options" id={listboxId} role="listbox">
            <div className="genre-options-list">
              {visibleMatches.map((genre, index) => {
                const selected = normalized(genre) === normalized(value);
                return (
                  <button
                    id={`${listboxId}-${index}`}
                    className={`genre-option ${activeIndex === index ? "active" : ""}`}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    key={genre}
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => choose(genre)}
                  >
                    <span>{genre}</span>
                    {selected && <Check size={15} aria-hidden="true" />}
                  </button>
                );
              })}
              {!visibleMatches.length && (
                <div className="genre-options-empty">Совпадений нет — можно сохранить свой вариант</div>
              )}
            </div>
            <div className="genre-options-meta">
              {matches.length > RESULT_LIMIT
                ? `Показано ${RESULT_LIMIT} из ${matches.length} · уточните поиск`
                : `${allGenres.length.toLocaleString("ru-RU")} жанров в каталоге`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
