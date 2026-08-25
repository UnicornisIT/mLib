"use client";

import {
  Archive,
  Database,
  Download,
  FolderOpen,
  Import,
  Info,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { applyDesktopClientState, collectDesktopClientState, type DesktopClientState } from "@/lib/desktopBackup";
import { formatBytes } from "@/lib/format";
import type { AppSettings, ImportJob } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";
import { useDesktopUpdate } from "@/providers/DesktopUpdateProvider";
import { type Theme, useTheme } from "@/providers/ThemeProvider";

type Tab = "library" | "metadata" | "playback" | "appearance" | "data" | "about";
type DataKind = "export" | "import" | "backup" | "restore";
type DataStatus = {
  desktop: boolean;
  data_root: string | null;
  media_root: string;
  backups_root: string;
  export_version: number;
  schema_version: number;
};
type DataOperationResult = {
  status: string;
  path: string;
  kind: string;
  message: string;
  safety_backup?: string | null;
  client_state?: DesktopClientState | null;
};

const tabLabels: Record<Tab, string> = {
  library: "Медиатека",
  metadata: "Метаданные",
  playback: "Воспроизведение",
  appearance: "Оформление",
  data: "Данные",
  about: "О программе",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [tab, setTab] = useState<Tab>("library");
  const [importPath, setImportPath] = useState("");
  const [job, setJob] = useState<ImportJob | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<DataKind | null>(null);
  const { setTheme } = useTheme();
  const { confirm, notify } = useFeedback();
  const { status: updateStatus, checkForUpdates, downloadUpdate, installUpdate } = useDesktopUpdate();

  const load = () => api<AppSettings>("/settings").then((data) => {
    setSettings(data);
    setImportPath(data.library.import_path);
    setTheme(data.appearance.theme);
  });

  useEffect(() => {
    void load();
    void api<DataStatus>("/data/status").then(setDataStatus).catch(() => setDataStatus(null));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!job || ["completed", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => void api<ImportJob>(`/music/imports/${job.id}`).then(setJob), 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  const patch = async (values: Record<string, unknown>) => {
    try {
      const updated = await api<AppSettings>("/settings", { method: "PATCH", body: values });
      setSettings(updated);
      setMessage("Настройки сохранены");
      window.setTimeout(() => setMessage(""), 2200);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось сохранить");
    }
  };

  const startImport = async () => {
    await patch({ import_path: importPath });
    setJob(await api<ImportJob>("/music/imports", { method: "POST", body: { path: importPath } }));
  };

  const runDataOperation = async (kind: DataKind) => {
    if (!window.mlibDesktop || !dataStatus?.desktop) {
      notify("Эта операция доступна в установленной Windows-версии mLib", "error");
      return;
    }
    if (kind === "import" || kind === "restore") {
      const accepted = await confirm({
        title: kind === "import" ? "Импортировать библиотеку?" : "Восстановить резервную копию?",
        message: "Перед заменой текущей библиотеки mLib автоматически создаст защитную резервную копию. Операцию нельзя прерывать.",
        confirmLabel: kind === "import" ? "Импортировать" : "Восстановить",
        destructive: true,
      });
      if (!accepted) return;
    }
    const selected = await window.mlibDesktop.chooseDataFile(kind);
    if (!selected) return;
    setBusy(kind);
    try {
      const result = await api<DataOperationResult>(`/data/${kind}`, {
        method: "POST",
        body: {
          path: selected,
          ...(kind === "backup" ? { client_state: collectDesktopClientState() } : {}),
        },
      });
      notify(result.message);
      if (kind === "restore") applyDesktopClientState(result.client_state);
      if (kind === "import" || kind === "restore") window.setTimeout(() => window.location.reload(), 800);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Операцию не удалось выполнить", "error");
    } finally {
      setBusy(null);
    }
  };

  if (!settings) {
    return <div className="content-page"><div className="app-loading" style={{ minHeight: 400 }}><div className="loading-mark" /></div></div>;
  }

  const toggle = (key: string, value: boolean) => (
    <button className={`toggle ${value ? "on" : ""}`} onClick={() => void patch({ [key]: !value })} aria-label={value ? "Выключить" : "Включить"} />
  );

  return (
    <div className="content-page">
      <div className="page-heading">
        <div><div className="eyebrow">mLib</div><h1>Настройки</h1><p>Управление библиотекой, данными и приложением</p></div>
      </div>
      <div className="settings-grid">
        <nav className="settings-nav">
          {(Object.keys(tabLabels) as Tab[]).map((value) => (
            <button className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)}>{tabLabels[value]}</button>
          ))}
        </nav>
        <div>
          {tab === "library" && <>
            <div className="settings-card">
              <h2>Хранилище</h2>
              <p>Файлы получают UUID-имена, а в базе сохраняются переносимые относительные ключи.</p>
              <div className="system-row"><span>Путь медиатеки</span><strong>{settings.library.library_path}</strong></div>
              <div className="system-row"><span>Форматы</span><strong>{settings.library.supported_extensions.join(", ")}</strong></div>
            </div>
            <div className="settings-card">
              <h2>Импорт папки</h2>
              <p>Сканирование добавит новые аудиофайлы и пропустит уже известные.</p>
              <div className="field"><label>Разрешённая директория</label><input className="input" value={importPath} onChange={(event) => setImportPath(event.target.value)} /></div>
              <div className="form-actions"><button className="button primary" disabled={!importPath || !!job && !["completed", "failed"].includes(job.status)} onClick={() => void startImport()}><FolderOpen size={16} />Сканировать</button></div>
              {job && <div className="upload-item" style={{ marginTop: 16 }}>
                <div className="upload-info"><strong>{job.status === "completed" ? "Импорт завершён" : job.status === "failed" ? "Ошибка импорта" : "Обработка медиатеки"}</strong><span>{job.processed} / {job.found}</span></div>
                <div className="upload-progress"><span style={{ width: `${job.found ? job.processed / job.found * 100 : 0}%` }} /></div>
                <p className="track-subtitle">Добавлено: {job.added} · Пропущено: {job.skipped} · Ошибок: {job.errors}</p>
              </div>}
            </div>
          </>}

          {tab === "metadata" && <div className="settings-card">
            <h2>Источники метаданных</h2>
            <p>Эти настройки относятся только к musicLib. Встроенные теги всегда имеют приоритет.</p>
            <SettingToggle title="Читать встроенные теги" subtitle="Mutagen: ID3, Vorbis, FLAC и MP4" control={toggle("embedded_metadata", settings.metadata.embedded_metadata)} />
            <SettingToggle title="MusicBrainz" subtitle="Подготовлено архитектурно; подключение провайдера — следующий этап" control={<span className="album-meta">Скоро</span>} />
            <SettingToggle title="Cover Art Archive" subtitle="Подготовлено архитектурно; подключение провайдера — следующий этап" control={<span className="album-meta">Скоро</span>} />
            <SettingToggle title="Автоматический поиск обложек" subtitle="Станет доступен после подключения внешнего провайдера" control={<span className="album-meta">Скоро</span>} />
          </div>}

          {tab === "playback" && <div className="settings-card">
            <h2>Воспроизведение</h2>
            <p>Локальные параметры плеера сохраняются на текущем устройстве.</p>
            <SettingToggle title="Сохранять громкость" subtitle="Восстанавливать уровень при следующем входе" control={toggle("save_volume", settings.playback.save_volume)} />
            <SettingToggle title="Автовоспроизведение" subtitle="Продолжать очередь после окончания трека" control={toggle("autoplay", settings.playback.autoplay)} />
            <div className="field" style={{ marginTop: 18 }}><label>Повтор по умолчанию</label><select className="select" value={settings.playback.default_repeat} onChange={(event) => void patch({ default_repeat: event.target.value })}><option value="off">Выключен</option><option value="all">Вся очередь</option><option value="one">Один трек</option></select></div>
          </div>}

          {tab === "appearance" && <div className="settings-card">
            <h2>Тема</h2>
            <p>Системная тема автоматически следует настройкам Windows.</p>
            <div className="field"><label>Оформление</label><select className="select" value={settings.appearance.theme} onChange={(event) => { const theme = event.target.value as Theme; setTheme(theme); void patch({ theme }); }}><option value="dark">Тёмное</option><option value="light">Светлое</option><option value="system">Как в системе</option></select></div>
          </div>}

          {tab === "data" && <>
            <div className="settings-card data-settings-intro">
              <Database size={24} />
              <div><h2>Локальная библиотека</h2><p>Backup быстро восстанавливает эту Windows-установку. Export — переносимый формат для другой установки и будущего PostgreSQL-сервера.</p></div>
            </div>
            <DataAction icon={<Download size={20} />} title="Экспортировать библиотеку" description="Сохранить все записи, связи и media в переносимый mLib-export.zip." label="Экспортировать" busy={busy === "export"} disabled={busy !== null} onClick={() => void runDataOperation("export")} />
            <DataAction icon={<Import size={20} />} title="Импортировать библиотеку" description="Проверить архив и контрольные суммы, создать backup, затем транзакционно импортировать данные." label="Импортировать" busy={busy === "import"} disabled={busy !== null} onClick={() => void runDataOperation("import")} />
            <DataAction icon={<Archive size={20} />} title="Создать резервную копию" description="Точная копия локальных SQLite-баз и media для быстрого восстановления." label="Создать backup" busy={busy === "backup"} disabled={busy !== null} onClick={() => void runDataOperation("backup")} />
            <DataAction icon={<RotateCcw size={20} />} title="Восстановить резервную копию" description="Вернуть локальную библиотеку из mLib-backup.zip. Текущее состояние сначала сохранится." label="Восстановить" busy={busy === "restore"} disabled={busy !== null} onClick={() => void runDataOperation("restore")} />
            {dataStatus && <div className="settings-card">
              <h2>Расположение данных</h2>
              <p>Эти папки находятся отдельно от mLib.exe и сохраняются при обновлении или удалении программы.</p>
              <div className="system-row"><span>Данные</span><strong>{dataStatus.data_root ?? "Серверный режим"}</strong></div>
              <div className="system-row"><span>Media</span><strong>{dataStatus.media_root}</strong></div>
              <div className="system-row"><span>Резервные копии</span><strong>{dataStatus.backups_root}</strong></div>
            </div>}
          </>}

          {tab === "about" && <div className="settings-card about-card">
            <Info size={28} />
            <div><div className="eyebrow">Локальная медиатека</div><h2>mLib</h2><p>Единое пространство для музыки, фильмов, книг, игр, желаний и личных коллекций.</p></div>
            <div className="system-list">
              <div className="system-row"><span>Версия</span><strong>{settings.system.version}</strong></div>
              <div className="system-row"><span>Режим</span><strong>{dataStatus?.desktop ? "Windows Desktop" : "Server / Web"}</strong></div>
              <div className="system-row"><span>База данных</span><strong>{settings.system.database === "connected" ? "Подключена" : "Ошибка"}</strong></div>
              <div className="system-row"><span>FFmpeg / ffprobe</span><strong>{settings.system.ffmpeg_available ? "Доступен" : "Не найден"}</strong></div>
              <div className="system-row"><span>Объём musicLib</span><strong>{formatBytes(settings.system.library_size)}</strong></div>
            </div>
            {dataStatus?.desktop && <div className="desktop-update-settings">
              <div><strong>Обновления приложения</strong><span>{updateStatus.message}{updateStatus.availableVersion ? ` · версия ${updateStatus.availableVersion}` : ""}</span></div>
              {updateStatus.state === "available" ? <button className="button primary" onClick={() => void downloadUpdate()}><Download size={16} />Скачать</button>
                : updateStatus.state === "downloaded" ? <button className="button primary" onClick={() => void installUpdate()}><RotateCcw size={16} />Перезапустить и установить</button>
                  : <button className="button" disabled={!updateStatus.enabled || ["checking", "downloading"].includes(updateStatus.state)} onClick={() => void checkForUpdates()}>{["checking", "downloading"].includes(updateStatus.state) ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}{updateStatus.state === "downloading" ? `Скачивание ${Math.round(updateStatus.progress || 0)}%` : updateStatus.state === "checking" ? "Проверяем…" : "Проверить сейчас"}</button>}
            </div>}
            {dataStatus?.desktop && <div className="form-actions"><button className="button" onClick={() => void window.mlibDesktop?.openLogs()}><FolderOpen size={16} />Открыть папку журналов</button></div>}
          </div>}
        </div>
      </div>
      {message && <div className="toast">{message}</div>}
    </div>
  );
}

function SettingToggle({ title, subtitle, control }: { title: string; subtitle: string; control: React.ReactNode }) {
  return <div className="toggle-row"><div className="toggle-copy"><strong>{title}</strong><span>{subtitle}</span></div>{control}</div>;
}

function DataAction({ icon, title, description, label, busy, disabled, onClick }: { icon: React.ReactNode; title: string; description: string; label: string; busy: boolean; disabled: boolean; onClick: () => void }) {
  return <div className="settings-card data-action-card">
    <div className="data-action-icon">{icon}</div>
    <div className="data-action-copy"><h2>{title}</h2><p>{description}</p></div>
    <button className="button" disabled={disabled} onClick={onClick}>{busy ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}{busy ? "Выполняется…" : label}</button>
  </div>;
}
