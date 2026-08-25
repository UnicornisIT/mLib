"use client";

import { CheckCircle2, Download, LoaderCircle, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { useDesktopUpdate } from "@/providers/DesktopUpdateProvider";

export function DesktopUpdateBanner() {
  const { status, downloadUpdate, installUpdate } = useDesktopUpdate();
  const [dismissedVersion, setDismissedVersion] = useState<string | null>(null);
  const visible = ["available", "downloading", "downloaded"].includes(status.state);
  const version = status.availableVersion || "новая версия";

  if (!visible || dismissedVersion === version) return null;

  return (
    <aside className="desktop-update-banner" aria-live="polite">
      <div className="desktop-update-icon">
        {status.state === "downloaded" ? <CheckCircle2 size={21} /> : status.state === "downloading" ? <LoaderCircle className="spin" size={21} /> : <Download size={21} />}
      </div>
      <div className="desktop-update-copy">
        <strong>{status.state === "downloaded" ? "Обновление готово" : status.state === "downloading" ? `Скачиваем mLib ${version}` : `Доступна mLib ${version}`}</strong>
        <span>{status.state === "downloaded" ? "Перезапустите приложение, чтобы установить новую версию." : status.state === "downloading" ? `${Math.round(status.progress || 0)}%` : "Можно скачать сейчас и установить после перезапуска."}</span>
        {status.state === "downloading" && <div className="desktop-update-progress"><i style={{ width: `${status.progress || 0}%` }} /></div>}
      </div>
      {status.state === "available" && <button className="button primary" onClick={() => void downloadUpdate()}><Download size={15} />Скачать</button>}
      {status.state === "downloaded" && <button className="button primary" onClick={() => void installUpdate()}><RotateCcw size={15} />Обновить</button>}
      <button className="desktop-update-close" type="button" aria-label="Напомнить позже" title="Напомнить позже" onClick={() => setDismissedVersion(version)}><X size={16} /></button>
    </aside>
  );
}
