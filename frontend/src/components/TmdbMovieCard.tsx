"use client";

import { ArrowRight, Check, Clapperboard, LoaderCircle, Star } from "lucide-react";
import Image from "next/image";
import type { TmdbCatalogTitle } from "@/lib/types";

export function TmdbMovieCard({
  title,
  loading,
  onOpen,
  priority = false,
}: {
  title: TmdbCatalogTitle;
  loading: boolean;
  onOpen: () => void;
  priority?: boolean;
}) {
  return (
    <button type="button" className="movie-card movie-discovery-card" onClick={onOpen} disabled={loading}>
      <span className="movie-poster">
        {title.poster_url ? (
          <Image src={title.poster_url} alt={`Постер ${title.title}`} fill sizes="(max-width: 640px) 46vw, 190px" priority={priority} />
        ) : (
          <span className="movie-poster-placeholder"><Clapperboard size={35} /><span>{title.title}</span></span>
        )}
        <span className="movie-type-badge">{title.media_type === "series" ? "Сериал" : "Фильм"}</span>
        {title.local_title_id && title.file_count > 0 && <span className="movie-complete" title="Есть видео"><Check size={14} /></span>}
        <span className="movie-card-play">
          {loading ? <LoaderCircle className="spin" size={19} /> : <ArrowRight size={19} />}
        </span>
      </span>
      <span className="movie-card-title">{title.title}</span>
      {title.match_reason && <span className="movie-match-reason">{title.match_reason}</span>}
      <span className="movie-card-meta">
        <span>{title.year || "Год неизвестен"}</span>
        {title.tmdb_rating && <span className="movie-rating"><Star size={11} fill="currentColor" />{title.tmdb_rating.toFixed(1)}</span>}
        {title.file_count > 0 && <span>Есть видео</span>}
      </span>
    </button>
  );
}
