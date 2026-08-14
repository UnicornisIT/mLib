"use client";

import { ArrowLeft, CakeSlice, Clock3, Film, KeyRound, ListChecks, MapPin, Pencil, Tv } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { MovieCard } from "@/components/MovieCard";
import { ProfileAvatar, userDisplayName } from "@/components/ProfileAvatar";
import { ProfileEditDialog } from "@/components/ProfileEditDialog";
import { ProfilePasswordDialog } from "@/components/ProfilePasswordDialog";
import { api } from "@/lib/api";
import type { MovieProfile, MovieProfileActivity, MovieTrackingStatus, SeriesTrackingStatus } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

type ProfileFilter = "all" | "movies" | "series";

const seriesStatuses: Array<{ value: SeriesTrackingStatus; label: string }> = [
  { value: "watching", label: "Смотрю" },
  { value: "planned", label: "Буду" },
  { value: "dropped", label: "Перестал" },
  { value: "completed", label: "Посмотрел" },
];

const movieStatuses: Array<{ value: MovieTrackingStatus; label: string }> = [
  { value: "watched", label: "Посмотрел" },
  { value: "planned", label: "Буду" },
];

function isoDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function Heatmap({ activity, filter }: { activity: MovieProfileActivity[]; filter: ProfileFilter }) {
  const days = useMemo(() => {
    const byDate = new Map(activity.map((item) => [item.date, item]));
    const end = new Date();
    end.setHours(12, 0, 0, 0);
    const start = new Date(end);
    start.setDate(start.getDate() - 364 - start.getDay());
    const output = [];
    for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
      const key = isoDate(day);
      const item = byDate.get(key);
      const minutes = filter === "movies" ? item?.movie_minutes ?? 0 : filter === "series" ? item?.episode_minutes ?? 0 : item?.minutes ?? 0;
      output.push({ key, minutes, item });
    }
    return output;
  }, [activity, filter]);
  const max = Math.max(1, ...days.map((day) => day.minutes));

  return (
    <div className="profile-heatmap-wrap">
      <div className="profile-heatmap-grid" aria-label="Активность просмотров за год">
        {days.map(({ key, minutes, item }) => {
          const level = minutes ? Math.max(1, Math.ceil(minutes / max * 4)) : 0;
          const title = `${new Date(`${key}T12:00:00`).toLocaleDateString("ru-RU")}: ${minutes} мин${item?.episodes ? ` · ${item.episodes} эп.` : ""}${item?.movies ? ` · ${item.movies} фил.` : ""}`;
          return <span className="profile-heatmap-cell" data-level={level} title={title} key={key} />;
        })}
      </div>
      <div className="profile-heatmap-legend"><span>Меньше</span>{[0, 1, 2, 3, 4].map((level) => <i data-level={level} key={level} />)}<span>Больше</span></div>
    </div>
  );
}

export default function MovieProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<MovieProfile | null>(null);
  const [filter, setFilter] = useState<ProfileFilter>("all");
  const [seriesStatus, setSeriesStatus] = useState<SeriesTrackingStatus>("watching");
  const [movieStatus, setMovieStatus] = useState<MovieTrackingStatus>("watched");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  useEffect(() => {
    void api<MovieProfile>("/movie/profile")
      .then(setProfile)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось загрузить профиль"));
  }, []);

  if (error) return <div className="movie-library-page movie-profile-page"><div className="form-error">{error}</div></div>;
  if (!profile) return <div className="movie-library-page movie-profile-page"><div className="movie-catalog-loading"><span className="loading-mark" /></div></div>;
  const summary = profile.summaries[filter];
  const hours = Math.round(summary.minutes / 60);

  return (
    <div className="movie-library-page movie-profile-page">
      <div className="service-page-content">
        <Link href="/movie" className="movie-profile-back"><ArrowLeft size={16} />Вернуться в movieLib</Link>
        <section className="movie-profile-hero">
          <ProfileAvatar user={user} className="movie-profile-avatar" />
          <div className="movie-profile-identity">
            <span>Профиль просмотра · @{user?.username || profile.username}</span>
            <div className="movie-profile-name-line"><h1>{userDisplayName(user)}</h1><div className="movie-profile-actions"><button className="movie-profile-edit" type="button" onClick={() => setEditing(true)}><Pencil size={14} />Редактировать</button><button className="movie-profile-edit" type="button" onClick={() => setChangingPassword(true)}><KeyRound size={14} />Сменить пароль</button></div></div>
            {user?.bio && <p className="movie-profile-bio">{user.bio}</p>}
            <div className="movie-profile-meta">
              <span>В movieLib с {new Date(profile.member_since).toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}</span>
              {user?.location && <span><MapPin size={12} />{user.location}</span>}
              {user?.birth_date && <span><CakeSlice size={12} />{new Date(`${user.birth_date}T12:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</span>}
            </div>
          </div>
          <div className="movie-profile-filter">
            {(["all", "movies", "series"] as const).map((value) => <button className={filter === value ? "active" : ""} onClick={() => setFilter(value)} key={value}>{value === "all" ? "Всё" : value === "movies" ? "Фильмы" : "Сериалы"}</button>)}
          </div>
          <div className="movie-profile-stats">
            <div><ListChecks size={18} /><strong>{summary.episodes.toLocaleString("ru-RU")}</strong><span>эпизодов</span></div>
            <div><Film size={18} /><strong>{summary.movies.toLocaleString("ru-RU")}</strong><span>фильмов</span></div>
            <div><Clock3 size={18} /><strong>{hours.toLocaleString("ru-RU")}</strong><span>часов</span></div>
            <div><Tv size={18} /><strong>{summary.days.toLocaleString("ru-RU")}</strong><span>дней</span></div>
          </div>
        </section>

        <section className="movie-profile-section">
          <div className="movie-profile-section-heading"><div><span>Последние 12 месяцев</span><h2>Статистика по дням</h2></div><strong>{summary.minutes.toLocaleString("ru-RU")} минут</strong></div>
          <Heatmap activity={profile.activity} filter={filter} />
        </section>

        {filter !== "movies" && <section className="movie-profile-section">
          <div className="movie-profile-section-heading"><div><span>Ваши списки</span><h2>Сериалы</h2></div><strong>{Object.values(profile.series_status_counts).reduce((sum, value) => sum + value, 0)}</strong></div>
          <div className="profile-status-tabs">
            {seriesStatuses.map((item) => <button className={seriesStatus === item.value ? "active" : ""} onClick={() => setSeriesStatus(item.value)} key={item.value}><strong>{profile.series_status_counts[item.value]}</strong><span>{item.label}</span></button>)}
          </div>
          {profile.series_titles[seriesStatus].length ? <div className="movie-grid profile-title-grid">{profile.series_titles[seriesStatus].map((title) => <MovieCard title={title} key={title.id} />)}</div> : <div className="profile-empty-list">В этом списке пока ничего нет</div>}
        </section>}

        {filter !== "series" && <section className="movie-profile-section">
          <div className="movie-profile-section-heading"><div><span>Ваши списки</span><h2>Фильмы</h2></div><strong>{Object.values(profile.movie_status_counts).reduce((sum, value) => sum + value, 0)}</strong></div>
          <div className="profile-status-tabs movie-status-tabs">
            {movieStatuses.map((item) => <button className={movieStatus === item.value ? "active" : ""} onClick={() => setMovieStatus(item.value)} key={item.value}><strong>{profile.movie_status_counts[item.value]}</strong><span>{item.label}</span></button>)}
          </div>
          {profile.movie_titles[movieStatus].length ? <div className="movie-grid profile-title-grid">{profile.movie_titles[movieStatus].map((title) => <MovieCard title={title} key={title.id} />)}</div> : <div className="profile-empty-list">В этом списке пока ничего нет</div>}
        </section>}
      </div>
      {editing && <ProfileEditDialog onClose={() => setEditing(false)} />}
      {changingPassword && <ProfilePasswordDialog onClose={() => setChangingPassword(false)} />}
    </div>
  );
}
