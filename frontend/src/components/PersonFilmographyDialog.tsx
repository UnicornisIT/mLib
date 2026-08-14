"use client";

import { Film, LoaderCircle, Tv, UserRound, X } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { TmdbMovieCard } from "@/components/TmdbMovieCard";
import { api } from "@/lib/api";
import type { CreditPerson, MediaTitle, PersonFilmography, TmdbCatalogTitle } from "@/lib/types";

type FilmographyFilter = "all" | "movie" | "series";

const departmentLabels: Record<string, string> = {
  Acting: "Актёр",
  Directing: "Режиссёр",
  Writing: "Автор",
  Production: "Продюсер",
};

export function PersonFilmographyDialog({
  open,
  person,
  onClose,
}: {
  open: boolean;
  person: CreditPerson | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const [data, setData] = useState<PersonFilmography | null>(null);
  const [filter, setFilter] = useState<FilmographyFilter>("all");
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<{ personId: number; message: string } | null>(null);
  const personId = person?.tmdb_id ?? null;

  useEffect(() => {
    if (!open || personId === null) return;
    let cancelled = false;
    void api<PersonFilmography>(`/movie/people/${personId}`)
      .then((payload) => {
        if (cancelled) return;
        setData(payload);
        setError(null);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError({
          personId,
          message: caught instanceof Error ? caught.message : "Не удалось загрузить фильмографию",
        });
      });
    return () => { cancelled = true; };
  }, [open, personId]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  const currentData = data?.tmdb_id === personId ? data : null;
  const items = useMemo(
    () => currentData?.items.filter((item) => filter === "all" || item.media_type === filter) ?? [],
    [currentData, filter],
  );
  if (!open || !person) return null;

  const openCard = async (title: TmdbCatalogTitle) => {
    if (title.local_title_id) {
      onClose();
      router.push(`/movie/${title.local_title_id}`);
      return;
    }
    const key = `${title.media_type}-${title.tmdb_id}`;
    setOpening(key);
    try {
      const saved = await api<MediaTitle>(`/movie/catalog/${title.media_type}/${title.tmdb_id}`, { method: "POST" });
      onClose();
      router.push(`/movie/${saved.id}`);
    } catch (caught) {
      setError({
        personId: person.tmdb_id,
        message: caught instanceof Error ? caught.message : "Не удалось открыть карточку",
      });
      setOpening(null);
    }
  };

  const movies = currentData?.items.filter((item) => item.media_type === "movie").length ?? 0;
  const series = currentData?.items.filter((item) => item.media_type === "series").length ?? 0;
  const visibleError = error?.personId === person.tmdb_id ? error.message : "";
  const profileUrl = currentData?.profile_url || person.profile_url;

  return (
    <div className="modal-backdrop person-filmography-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal movie-person-modal" role="dialog" aria-modal="true" aria-labelledby="person-filmography-title">
        <div className="person-filmography-header">
          <span className="person-filmography-photo">
            {profileUrl ? <Image src={profileUrl} alt={person.name} fill sizes="112px" /> : <UserRound size={36} />}
          </span>
          <div className="person-filmography-identity">
            <span>{currentData ? departmentLabels[currentData.known_for_department || ""] || currentData.known_for_department || person.role : person.role}</span>
            <h2 id="person-filmography-title">{currentData?.name || person.name}</h2>
            {currentData && <p>{[currentData.birthday ? new Date(currentData.birthday).toLocaleDateString("ru-RU") : null, currentData.place_of_birth].filter(Boolean).join(" · ")}</p>}
          </div>
          <button className="icon-button person-filmography-close" onClick={onClose} aria-label="Закрыть"><X size={20} /></button>
        </div>

        <div className="person-filmography-body">
          {!currentData && !visibleError && <div className="person-filmography-loading"><LoaderCircle className="spin" size={28} /><span>Собираем фильмографию…</span></div>}
          {visibleError && <div className="form-error">{visibleError}</div>}
          {currentData && <>
            {currentData.biography && <p className="person-filmography-bio">{currentData.biography}</p>}
            <div className="person-filmography-toolbar">
              <div>
                <strong>{currentData.items.length}</strong>
                <span>работ в фильмографии</span>
              </div>
              <div className="movie-filter-row person-filmography-filters" aria-label="Фильтр фильмографии">
                <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>Все <span>{currentData.items.length}</span></button>
                <button type="button" className={filter === "movie" ? "active" : ""} onClick={() => setFilter("movie")}><Film size={14} />Фильмы <span>{movies}</span></button>
                <button type="button" className={filter === "series" ? "active" : ""} onClick={() => setFilter("series")}><Tv size={14} />Сериалы <span>{series}</span></button>
              </div>
            </div>
            {items.length ? <div className="movie-grid person-filmography-grid">
              {items.map((title, index) => <TmdbMovieCard
                key={`${title.media_type}-${title.tmdb_id}`}
                title={title}
                loading={opening === `${title.media_type}-${title.tmdb_id}`}
                onOpen={() => void openCard(title)}
                priority={index < 5}
              />)}
            </div> : <div className="person-filmography-empty">В этом разделе работ пока нет.</div>}
          </>}
        </div>
      </div>
    </div>
  );
}
