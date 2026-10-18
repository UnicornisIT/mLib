"use client";

import { FileSpreadsheet, GalleryVerticalEnd, RotateCcw, UploadCloud, X } from "lucide-react";
import Link from "next/link";
import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { TransferJob, TransferSummary } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

const POLL_INTERVAL_MS = 2000;
const ACTIVE_STATUSES = new Set<TransferJob["status"]>(["queued", "enriching"]);
const STATUS_LABELS: Record<TransferJob["status"], string> = {
  queued: "В очереди",
  enriching: "Ищем треки в Apple Music",
  completed: "Перенос завершён",
  failed: "Перенос прервался с ошибкой",
  cancelled: "Перенос отменён",
};

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

function enrichmentProgress(job: TransferJob) {
  if (!ACTIVE_STATUSES.has(job.status)) return 100;
  if (job.added === 0) return 100;
  return Math.round(((job.added - job.pending) / job.added) * 100);
}

export function LibraryTransfer() {
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [job, setJob] = useState<TransferJob | null>(null);
  const [summary, setSummary] = useState<TransferSummary | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [createPlaylists, setCreatePlaylists] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = job ? ACTIVE_STATUSES.has(job.status) : false;
  const jobId = job?.id;

  const loadSummary = useCallback(() => {
    void api<TransferSummary>("/music/transfer/summary").then(setSummary).catch(() => setSummary(null));
  }, []);

  useEffect(() => {
    void api<TransferJob | null>("/music/transfer/latest")
      .then(setJob)
      .catch((caught) => setError(errorMessage(caught, "Не удалось загрузить состояние переноса")));
    loadSummary();
  }, [loadSummary]);

  // Progress lives on the server, so polling resumes after a page reload.
  useEffect(() => {
    if (!jobId || !active) return;
    const timer = window.setInterval(() => {
      void api<TransferJob>(`/music/transfer/${jobId}`)
        .then((next) => {
          setJob(next);
          if (!ACTIVE_STATUSES.has(next.status)) {
            loadSummary();
            window.dispatchEvent(new Event("mlib:library-changed"));
          }
        })
        .catch(() => undefined);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [jobId, active, loadSummary]);

  const chooseFile = (files: FileList | null) => {
    const next = files?.[0];
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Нужен файл в формате CSV — экспорт фонотеки Apple Music");
      return;
    }
    setError("");
    setFile(next);
  };

  const start = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("create_playlists", createPlaylists ? "true" : "false");
      setJob(await api<TransferJob>("/music/transfer", { method: "POST", body }));
      setFile(null);
      loadSummary();
      window.dispatchEvent(new Event("mlib:library-changed"));
    } catch (caught) {
      setError(errorMessage(caught, "Не удалось загрузить файл"));
    } finally {
      setBusy(false);
    }
  };

  const act = async (action: "cancel" | "retry") => {
    if (!job) return;
    setBusy(true);
    setError("");
    try {
      setJob(await api<TransferJob>(`/music/transfer/${job.id}/${action}`, { method: "POST" }));
      loadSummary();
    } catch (caught) {
      setError(errorMessage(caught, "Не удалось выполнить действие"));
    } finally {
      setBusy(false);
    }
  };

  const lookupErrors = job ? job.errors - job.invalid_rows : 0;
  const canRetry = Boolean(job && !active && (job.not_found > 0 || lookupErrors > 0 || job.status === "cancelled"));

  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Библиотека</div>
          <h1>Перенести фонотеку</h1>
          <p>Загрузите экспорт Apple Music в CSV — mLib соберёт каталог треков с названиями, альбомами и обложками. Файлы можно добавить позже, каждый в свою карточку.</p>
        </div>
        {summary && summary.total > 0 && (
          <div className="page-actions">
            <Link className="button" href="/music/catalog"><GalleryVerticalEnd size={16} />Открыть каталог</Link>
          </div>
        )}
      </div>

      {summary && summary.total > 0 && (
        <div className="transfer-stats" aria-label="Каталог">
          <div className="stat-card"><div className="stat-value">{summary.total}</div><div className="stat-label">треков в каталоге</div></div>
          <div className="stat-card"><div className="stat-value">{summary.enriched}</div><div className="stat-label">найдено в Apple Music</div></div>
          <div className="stat-card"><div className="stat-value">{summary.not_found}</div><div className="stat-label">не найдено</div></div>
        </div>
      )}

      {user?.is_admin ? (
        <section className="transfer-panel" aria-label="Загрузка экспорта">
          <input
            ref={inputRef}
            hidden
            type="file"
            accept=".csv,text/csv"
            aria-label="Файл экспорта Apple Music"
            onChange={(event: ChangeEvent<HTMLInputElement>) => { chooseFile(event.target.files); event.target.value = ""; }}
          />
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
            onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files); }}
          >
            <div>
              {file ? <FileSpreadsheet size={34} color="var(--accent)" /> : <UploadCloud size={34} color="var(--accent)" />}
              <h3>{file ? file.name : "Перетащите CSV-файл сюда"}</h3>
              <p>{file ? "Готово к загрузке" : "или нажмите, чтобы выбрать экспорт фонотеки Apple Music"}</p>
            </div>
          </div>
          <div className="toggle-row">
            <div className="toggle-copy">
              <strong>Создать плейлисты</strong>
              <span>По значениям столбца «Playlist name». Треки без файлов тоже попадут в плейлист.</span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={createPlaylists}
              aria-label="Создать плейлисты из столбца Playlist name"
              className={`toggle ${createPlaylists ? "on" : ""}`}
              onClick={() => setCreatePlaylists((value) => !value)}
            />
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="form-actions">
            <button className="button primary" type="button" disabled={!file || busy} onClick={() => void start()}>
              <UploadCloud size={16} />Перенести
            </button>
          </div>
        </section>
      ) : (
        <p className="transfer-note">Переносить фонотеку может только администратор mLib.</p>
      )}

      {job && (
        <section className="transfer-panel" aria-label="Последний перенос" aria-live="polite">
          <div className="transfer-job-header">
            <div>
              <strong>{STATUS_LABELS[job.status]}</strong>
              <span>{job.filename}</span>
            </div>
            <div className="page-actions">
              {active && user?.is_admin && <button className="button" type="button" disabled={busy} onClick={() => void act("cancel")}><X size={15} />Отменить</button>}
              {canRetry && user?.is_admin && <button className="button" type="button" disabled={busy} onClick={() => void act("retry")}><RotateCcw size={15} />Повторить поиск</button>}
            </div>
          </div>
          {active && (
            <>
              <div className="upload-progress" role="progressbar" aria-label="Поиск в Apple Music" aria-valuemin={0} aria-valuemax={100} aria-valuenow={enrichmentProgress(job)}>
                <span style={{ width: `${enrichmentProgress(job)}%` }} />
              </div>
              <p className="transfer-note">Осталось найти: {job.pending}. Можно закрыть страницу — перенос продолжится.</p>
            </>
          )}
          <dl className="transfer-summary">
            <div><dt>Строк в файле</dt><dd>{job.rows_total}</dd></div>
            <div><dt>Добавлено</dt><dd>{job.added}</dd></div>
            <div><dt>Уже было</dt><dd>{job.existing}</dd></div>
            <div><dt>Найдено в Apple Music</dt><dd>{job.enriched}</dd></div>
            <div><dt>Не найдено в Apple</dt><dd>{job.not_found}</dd></div>
            {job.errors > 0 && <div><dt>Ошибки</dt><dd>{job.errors}</dd></div>}
          </dl>
          {job.error_message && <div className="form-error" role="alert">{job.error_message}</div>}
        </section>
      )}
    </div>
  );
}
