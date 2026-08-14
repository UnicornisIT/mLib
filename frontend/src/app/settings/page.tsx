"use client";

import { FolderSearch } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { AppSettings, ImportJob } from "@/lib/types";
import { type Theme, useTheme } from "@/providers/ThemeProvider";

type Tab = "library" | "metadata" | "playback" | "appearance" | "system";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [tab, setTab] = useState<Tab>("library");
  const [importPath, setImportPath] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [message, setMessage] = useState("");
  const { setTheme } = useTheme();
  const load = () => api<AppSettings>("/settings").then((data) => { setSettings(data); setImportPath(data.library.import_path); setTheme(data.appearance.theme); });
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || ["completed", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => void api<ImportJob>(`/music/imports/${job.id}`).then(setJob), 1000);
    return () => window.clearInterval(timer);
  }, [job]);
  const patch = async (values: Record<string, unknown>) => {
    try {
      const updated = await api<AppSettings>("/settings", { method: "PATCH", body: values });
      setSettings(updated); setMessage("Настройки сохранены");
      window.setTimeout(() => setMessage(""), 2200);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось сохранить"); }
  };
  const startImport = async () => {
    await patch({ import_path: importPath });
    setJob(await api<ImportJob>("/music/imports", { method: "POST", body: { path: importPath } }));
  };
  if (!settings) return <div className="content-page"><div className="app-loading" style={{ minHeight: 400 }}><div className="loading-mark" /></div></div>;
  const toggle = (key: string, value: boolean) => <button className={`toggle ${value ? "on" : ""}`} onClick={() => void patch({ [key]: !value })} aria-label={value ? "Выключить" : "Включить"} />;
  return (
    <div className="content-page">
      <div className="page-heading"><div><div className="eyebrow">mLib</div><h1>Настройки</h1><p>Управление библиотекой, метаданными и воспроизведением</p></div></div>
      <div className="settings-grid">
        <nav className="settings-nav">{(["library", "metadata", "playback", "appearance", "system"] as Tab[]).map((value) => <button className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)}>{{ library: "Медиатека", metadata: "Метаданные", playback: "Воспроизведение", appearance: "Оформление", system: "Система" }[value]}</button>)}</nav>
        <div>
          {tab === "library" && <><div className="settings-card"><h2>Хранилище</h2><p>Файлы получают UUID-имена, поэтому редактирование тегов не ломает пути.</p><div className="system-row"><span>Путь медиатеки</span><strong>{settings.library.library_path}</strong></div><div className="system-row"><span>Форматы</span><strong>{settings.library.supported_extensions.join(", ")}</strong></div></div><div className="settings-card"><h2>Импорт папки</h2><p>Сканирование добавит новые аудиофайлы и пропустит уже известные.</p><div className="field"><label>Разрешённая серверная директория</label><input className="input" value={importPath} onChange={(event) => setImportPath(event.target.value)} /></div><div className="form-actions"><button className="button primary" disabled={!importPath || !!job && !["completed", "failed"].includes(job.status)} onClick={() => void startImport()}><FolderSearch size={16} />Сканировать</button></div>{job && <div className="upload-item" style={{ marginTop: 16 }}><div className="upload-info"><strong>{job.status === "completed" ? "Импорт завершён" : job.status === "failed" ? "Ошибка импорта" : "Обработка медиатеки"}</strong><span>{job.processed} / {job.found}</span></div><div className="upload-progress"><span style={{ width: `${job.found ? job.processed / job.found * 100 : 0}%` }} /></div><p className="track-subtitle">Добавлено: {job.added} · Пропущено: {job.skipped} · Ошибок: {job.errors}</p></div>}</div></>}
          {tab === "metadata" && <div className="settings-card"><h2>Источники метаданных</h2><p>Эти настройки относятся только к musicLib. Встроенные теги всегда имеют приоритет.</p><SettingToggle title="Читать встроенные теги" subtitle="Mutagen: ID3, Vorbis, FLAC и MP4" control={toggle("embedded_metadata", settings.metadata.embedded_metadata)} /><SettingToggle title="MusicBrainz" subtitle="Подготовлено архитектурно; подключение провайдера — следующий этап" control={<span className="album-meta">Скоро</span>} /><SettingToggle title="Cover Art Archive" subtitle="Подготовлено архитектурно; подключение провайдера — следующий этап" control={<span className="album-meta">Скоро</span>} /><SettingToggle title="Автоматический поиск обложек" subtitle="Станет доступен после подключения внешнего провайдера" control={<span className="album-meta">Скоро</span>} /></div>}
          {tab === "playback" && <div className="settings-card"><h2>Воспроизведение</h2><p>Локальные параметры плеера также сохраняются на текущем устройстве.</p><SettingToggle title="Сохранять громкость" subtitle="Восстанавливать уровень при следующем входе" control={toggle("save_volume", settings.playback.save_volume)} /><SettingToggle title="Автовоспроизведение" subtitle="Продолжать очередь после окончания трека" control={toggle("autoplay", settings.playback.autoplay)} /><div className="field" style={{ marginTop: 18 }}><label>Повтор по умолчанию</label><select className="select" value={settings.playback.default_repeat} onChange={(event) => void patch({ default_repeat: event.target.value })}><option value="off">Выключен</option><option value="all">Вся очередь</option><option value="one">Один трек</option></select></div></div>}
          {tab === "appearance" && <div className="settings-card"><h2>Тема</h2><p>Системная тема автоматически следует настройкам устройства.</p><div className="field"><label>Оформление</label><select className="select" value={settings.appearance.theme} onChange={(event) => { const theme = event.target.value as Theme; setTheme(theme); void patch({ theme }); }}><option value="dark">Тёмное</option><option value="light">Светлое</option><option value="system">Как в системе</option></select></div></div>}
          {tab === "system" && <div className="settings-card"><h2>Состояние системы</h2><p>Диагностика основных компонентов приложения.</p><div className="system-list"><div className="system-row"><span>Версия</span><strong>{settings.system.version}</strong></div><div className="system-row"><span>База данных</span><strong>{settings.system.database === "connected" ? "Подключена" : "Ошибка"}</strong></div><div className="system-row"><span>FFmpeg / ffprobe</span><strong>{settings.system.ffmpeg_available ? "Доступен" : "Не найден"}</strong></div><div className="system-row"><span>Объём медиатеки</span><strong>{formatBytes(settings.system.library_size)}</strong></div></div></div>}
        </div>
      </div>
      {message && <div className="toast">{message}</div>}
    </div>
  );
}

function SettingToggle({ title, subtitle, control }: { title: string; subtitle: string; control: React.ReactNode }) {
  return <div className="toggle-row"><div className="toggle-copy"><strong>{title}</strong><span>{subtitle}</span></div>{control}</div>;
}
