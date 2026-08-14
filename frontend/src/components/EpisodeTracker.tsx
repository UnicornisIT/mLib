"use client";

import { CalendarDays, Check, CheckCheck, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { MediaTitleDetail, MovieSeason } from "@/lib/types";

export function EpisodeTracker({ title, onChanged }: { title: MediaTitleDetail; onChanged: () => void }) {
  const seasons = useMemo(
    () => [...title.seasons].sort((a, b) => a.season_number - b.season_number),
    [title.seasons],
  );
  const initialSeason = seasons.find((season) => season.season_number > 0)?.season_number ?? seasons[0]?.season_number;
  const [seasonNumber, setSeasonNumber] = useState<number | undefined>(initialSeason);
  const [season, setSeason] = useState<MovieSeason | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (seasonNumber === undefined) return;
    void api<MovieSeason>(`/movie/titles/${title.id}/seasons/${seasonNumber}`)
      .then(setSeason)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось загрузить сезон"));
  }, [seasonNumber, title.id]);

  const updateEpisode = async (episodeNumber: number, watched: boolean) => {
    if (seasonNumber === undefined) return;
    setUpdating(String(episodeNumber));
    setError("");
    try {
      const updated = await api<MovieSeason>(
        `/movie/titles/${title.id}/seasons/${seasonNumber}/episodes/${episodeNumber}`,
        { method: "PUT", body: { watched } },
      );
      setSeason(updated);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить просмотр");
    } finally {
      setUpdating(null);
    }
  };

  const updateSeason = async (watched: boolean) => {
    if (seasonNumber === undefined) return;
    setUpdating("season");
    setError("");
    try {
      const updated = await api<MovieSeason>(`/movie/titles/${title.id}/seasons/${seasonNumber}/watched`, {
        method: "PUT",
        body: { watched },
      });
      setSeason(updated);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить сезон");
    } finally {
      setUpdating(null);
    }
  };

  if (!seasons.length) return null;
  const seasonComplete = Boolean(season?.episode_count && season.watched_count === season.episode_count);

  return (
    <section className="series-tracker">
      <div className="series-tracker-heading">
        <div>
          <span>Трек просмотра</span>
          <h2>Сезоны и эпизоды</h2>
        </div>
        <strong>{title.watched_count} из {title.total_episodes || "—"}</strong>
      </div>
      <div className="season-tabs" role="tablist" aria-label="Сезоны">
        {seasons.map((item) => (
          <button
            type="button"
            className={seasonNumber === item.season_number ? "active" : ""}
            onClick={() => { setSeason(null); setError(""); setSeasonNumber(item.season_number); }}
            key={item.season_number}
          >
            {item.season_number === 0 ? "Спецвыпуски" : `Сезон ${item.season_number}`}
            <span>{item.watched_count}/{item.episode_count}</span>
          </button>
        ))}
      </div>
      {!season ? <div className="episode-tracker-loading"><LoaderCircle className="spin" /></div> : (
        <div className="episode-tracker-panel">
          <div className="episode-season-summary">
            <div><strong>{season.name}</strong><span>{season.watched_count} из {season.episode_count} просмотрено</span></div>
            <button
              type="button"
              className="button movie-secondary"
              disabled={updating === "season"}
              onClick={() => void updateSeason(!seasonComplete)}
            >
              {updating === "season" ? <LoaderCircle className="spin" size={16} /> : <CheckCheck size={16} />}
              {seasonComplete ? "Снять отметки" : "Отметить весь сезон"}
            </button>
          </div>
          <div className="episode-tracker-list">
            {season.episodes.map((episode) => (
              <button
                type="button"
                className={`episode-track-row ${episode.watched ? "watched" : ""}`}
                onClick={() => void updateEpisode(episode.episode_number, !episode.watched)}
                disabled={updating === String(episode.episode_number)}
                key={episode.episode_number}
              >
                <span className="episode-check">
                  {updating === String(episode.episode_number) ? <LoaderCircle className="spin" size={15} /> : episode.watched ? <Check size={16} /> : episode.episode_number}
                </span>
                <span className="episode-track-copy">
                  <strong>S{season.season_number.toString().padStart(2, "0")}E{episode.episode_number.toString().padStart(2, "0")} · {episode.name}</strong>
                  <small>{episode.overview || "Описание эпизода пока отсутствует"}</small>
                </span>
                <span className="episode-track-meta">
                  {episode.air_date && <span><CalendarDays size={12} />{new Date(`${episode.air_date}T00:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" })}</span>}
                  {episode.runtime_minutes > 0 && <span>{episode.runtime_minutes} мин</span>}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
      {error && <div className="form-error">{error}</div>}
    </section>
  );
}
