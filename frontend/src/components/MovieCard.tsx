import { Check, Clapperboard, Play, Star } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { MediaTitle } from "@/lib/types";

export function MovieCard({ title, priority = false }: { title: MediaTitle; priority?: boolean }) {
  const complete = title.tracking?.status === "watched" || title.tracking?.status === "completed";
  const statusLabel = title.tracking?.status === "watching" ? "Смотрю"
    : title.tracking?.status === "planned" ? "Буду смотреть"
      : title.tracking?.status === "dropped" ? "Перестал"
        : complete ? "Посмотрел" : null;
  return (
    <Link href={`/movie/${title.id}`} className="movie-card">
      <div className="movie-poster">
        {title.poster_url ? (
          <Image src={title.poster_url} alt={`Постер ${title.title}`} fill sizes="(max-width: 640px) 46vw, 190px" priority={priority} />
        ) : (
          <div className="movie-poster-placeholder"><Clapperboard size={35} /><span>{title.title}</span></div>
        )}
        <span className="movie-type-badge">{title.media_type === "series" ? "Сериал" : "Фильм"}</span>
        <span className="movie-card-play"><Play size={19} fill="currentColor" /></span>
        {complete && <span className="movie-complete" title="Просмотрено"><Check size={14} /></span>}
        {title.progress_percent > 0 && !complete && (
          <span className="movie-card-progress"><i style={{ width: `${title.progress_percent}%` }} /></span>
        )}
      </div>
      <span className="movie-card-title">{title.title}</span>
      <span className="movie-card-meta">
        <span>{title.year || "Год не определён"}</span>
        {title.tmdb_rating && <span className="movie-rating"><Star size={11} fill="currentColor" />{title.tmdb_rating.toFixed(1)}</span>}
      </span>
      <span className="movie-card-state">{title.media_type === "series" ? `${title.watched_count}/${title.total_episodes || "—"} эпизодов` : statusLabel}</span>
    </Link>
  );
}
