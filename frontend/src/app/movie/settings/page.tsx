"use client";

import { ArrowLeft, CheckCircle2, Database, Film, KeyRound, Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { MovieSettings } from "@/lib/types";

export default function MovieSettingsPage() {
  const [settings, setSettings] = useState<MovieSettings | null>(null);
  const [token, setToken] = useState("");
  const [refreshHours, setRefreshHours] = useState(24);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void api<MovieSettings>("/movie/settings").then((data) => {
      setSettings(data);
      setRefreshHours(data.metadata_refresh_hours);
    });
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage("");
    try {
      const body: Record<string, unknown> = { metadata_refresh_hours: refreshHours };
      if (token.trim()) body.tmdb_api_token = token.trim();
      const updated = await api<MovieSettings>("/movie/settings", { method: "PATCH", body });
      setSettings(updated);
      setToken("");
      setMessage("Настройки movieLib сохранены");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось сохранить настройки");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="movie-library-page movie-settings-page">
      <header className="movie-library-nav movie-settings-nav">
        <nav aria-label="Настройки movieLib"><Link href="/movie"><ArrowLeft size={14} />Каталог</Link></nav>
        <Link className="button movie-add-button" href="/movie"><Film size={17} />Вернуться в movieLib</Link>
      </header>
      <div className="movie-settings-main service-page-content">
        <div className="movie-settings-heading"><div className="movie-kicker">Только movieLib</div><h1>Настройки фильмов</h1><p>Эти параметры хранятся в отдельной базе movie.db и не влияют на musicLib.</p></div>
        {!settings ? <div className="movie-catalog-loading"><span className="loading-mark" /></div> : <div className="movie-settings-grid">
          <section className="movie-settings-card">
            <div className="movie-settings-card-title"><KeyRound size={20} /><div><h2>Каталог TMDB</h2><p>Постеры, описания, рейтинги и даты выхода эпизодов.</p></div></div>
            <div className={`movie-settings-status ${settings.tmdb_enabled ? "connected" : ""}`}><CheckCircle2 size={15} />{settings.tmdb_enabled ? "Подключён" : "Токен не настроен"}</div>
            <label className="field"><span>API Read Access Token или API Key v3</span><input className="input" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} placeholder={settings.tmdb_enabled ? "Оставьте пустым, чтобы сохранить текущий" : "Вставьте ключ из настроек TMDB"} /></label>
            <p className="movie-settings-hint">Поддерживаются новые токены Developer Plan (TMDB…), Read Access Token (eyJ…) и API Key v3. movieLib проверит ключ перед сохранением.</p>
            <label className="field"><span>Обновлять карточки каждые</span><select className="select" value={refreshHours} onChange={(event) => setRefreshHours(Number(event.target.value))}><option value={6}>6 часов</option><option value={12}>12 часов</option><option value={24}>24 часа</option><option value={72}>3 дня</option><option value={168}>7 дней</option></select></label>
            <button className="button primary movie-primary" disabled={saving} onClick={() => void save()}><Save size={16} />{saving ? "Сохраняем…" : "Сохранить"}</button>
            {message && <div className="movie-settings-message">{message}</div>}
          </section>
          <section className="movie-settings-card">
            <div className="movie-settings-card-title"><Database size={20} /><div><h2>Независимое хранилище</h2><p>Состояние кинотеки и её настройки изолированы от музыки.</p></div></div>
            <div className="system-list"><div className="system-row"><span>База данных</span><strong>{settings.database === "connected" ? "movie.db подключена" : "Ошибка"}</strong></div><div className="system-row"><span>Видео и постеры</span><strong>{settings.storage_path}</strong></div><div className="system-row"><span>Объём movieLib</span><strong>{formatBytes(settings.library_size)}</strong></div></div>
          </section>
        </div>}
      </div>
    </div>
  );
}
