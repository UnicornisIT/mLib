"use client";

import { Archive, BookOpenText, CakeSlice, Film, KeyRound, LoaderCircle, MapPin, Music2, Pencil, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ProfileAvatar, userDisplayName } from "@/components/ProfileAvatar";
import { ProfileEditDialog } from "@/components/ProfileEditDialog";
import { ProfilePasswordDialog } from "@/components/ProfilePasswordDialog";
import { api } from "@/lib/api";
import { applyDesktopClientState, collectDesktopClientState, type DesktopClientState } from "@/lib/desktopBackup";
import { useAuth } from "@/providers/AuthProvider";
import { useFeedback } from "@/providers/FeedbackProvider";

type BackupOperation = "backup" | "restore";
type DataStatus = { desktop: boolean };
type DataOperationResult = {
  message: string;
  client_state?: DesktopClientState | null;
};

export default function ProfilePage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [backupAvailable, setBackupAvailable] = useState(false);
  const [backupBusy, setBackupBusy] = useState<BackupOperation | null>(null);
  const { confirm, notify } = useFeedback();

  useEffect(() => {
    if (!window.mlibDesktop) return;
    void api<DataStatus>("/data/status")
      .then((status) => setBackupAvailable(status.desktop))
      .catch(() => setBackupAvailable(false));
  }, []);

  const runBackupOperation = async (kind: BackupOperation) => {
    if (!window.mlibDesktop || backupBusy) return;
    if (kind === "restore") {
      const accepted = await confirm({
        title: "Восстановить резервную копию?",
        message: "Текущие данные будут заменены. Перед восстановлением mLib сохранит их отдельно.",
        confirmLabel: "Восстановить",
        destructive: true,
      });
      if (!accepted) return;
    }
    const selected = await window.mlibDesktop.chooseDataFile(kind);
    if (!selected) return;
    setBackupBusy(kind);
    try {
      const result = await api<DataOperationResult>(`/data/${kind}`, {
        method: "POST",
        body: {
          path: selected,
          ...(kind === "backup" ? { client_state: collectDesktopClientState() } : {}),
        },
      });
      if (kind === "restore") applyDesktopClientState(result.client_state);
      notify(result.message);
      if (kind === "restore") window.setTimeout(() => window.location.reload(), 800);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Операцию не удалось выполнить", "error");
    } finally {
      setBackupBusy(null);
    }
  };

  return (
    <section className="hub-profile-page">
      <div className="hub-profile-heading">
        <div className="eyebrow">Учётная запись mLib</div>
        <h1>Мой профиль</h1>
        <p>Один профиль для всех ваших медиатек.</p>
      </div>

      <div className="hub-profile-card">
        <ProfileAvatar user={user} className="hub-profile-avatar" />
        <div className="hub-profile-copy">
          <span>@{user?.username}</span>
          <h2>{userDisplayName(user)}</h2>
          <p>{user?.bio || "Добавьте отображаемое имя и немного расскажите о себе."}</p>
          {(user?.location || user?.birth_date) && <div className="hub-profile-meta">
            {user.location && <span><MapPin size={14} />{user.location}</span>}
            {user.birth_date && <span><CakeSlice size={14} />{new Date(`${user.birth_date}T12:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</span>}
          </div>}
        </div>
        <div className="hub-profile-actions">
          <button className="button" type="button" onClick={() => setEditing(true)}><Pencil size={15} />Редактировать</button>
          <button className="button" type="button" onClick={() => setChangingPassword(true)}><KeyRound size={15} />Сменить пароль</button>
        </div>
      </div>

      <div className="hub-profile-modules">
        <Link href="/music/profile"><Music2 size={18} /><span><strong>Профиль musicLib</strong><small>Музыкальная библиотека и проблемные треки</small></span></Link>
        <Link href="/movie/profile"><Film size={18} /><span><strong>Профиль movieLib</strong><small>Статистика фильмов и сериалов</small></span></Link>
        <Link href="/books"><BookOpenText size={18} /><span><strong>Библиотека bookLib</strong><small>Электронные и аудиокниги</small></span></Link>
      </div>

      {backupAvailable && <section className="hub-profile-backup" aria-labelledby="profile-backup-title">
        <span className="hub-profile-backup-icon"><Archive size={21} /></span>
        <h2 id="profile-backup-title">Резервная копия</h2>
        <div className="hub-profile-backup-actions">
          <button className="button primary" type="button" disabled={backupBusy !== null} onClick={() => void runBackupOperation("backup")}>
            {backupBusy === "backup" ? <LoaderCircle className="spin" size={16} /> : <Archive size={16} />}
            {backupBusy === "backup" ? "Создание…" : "Создать копию"}
          </button>
          <button className="button" type="button" disabled={backupBusy !== null} onClick={() => void runBackupOperation("restore")}>
            {backupBusy === "restore" ? <LoaderCircle className="spin" size={16} /> : <RotateCcw size={16} />}
            {backupBusy === "restore" ? "Восстановление…" : "Восстановить"}
          </button>
        </div>
      </section>}

      {editing && <ProfileEditDialog onClose={() => setEditing(false)} />}
      {changingPassword && <ProfilePasswordDialog onClose={() => setChangingPassword(false)} />}
    </section>
  );
}
