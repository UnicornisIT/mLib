"use client";

import { CakeSlice, ChevronRight, CircleAlert, KeyRound, MapPin, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ProfileAvatar, userDisplayName } from "@/components/ProfileAvatar";
import { ProfileEditDialog } from "@/components/ProfileEditDialog";
import { ProfilePasswordDialog } from "@/components/ProfilePasswordDialog";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import type { MetadataAttentionSummary } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

function trackCountText(count: number) {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${count} треков требуют проверки`;
  if (last === 1) return `${count} трек требует проверки`;
  if (last >= 2 && last <= 4) return `${count} трека требуют проверки`;
  return `${count} треков требуют проверки`;
}

export default function MusicProfilePage() {
  const { user } = useAuth();
  const [attentionCount, setAttentionCount] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const loadAttentionCount = useCallback(() => {
    void api<MetadataAttentionSummary>("/music/tracks/attention-summary")
      .then((summary) => setAttentionCount(summary.total))
      .catch(() => setAttentionCount(null));
  }, []);

  useEffect(loadAttentionCount, [loadAttentionCount]);
  useLibraryChanged(loadAttentionCount);

  const attentionText = attentionCount === null
    ? "Проверяем состояние библиотеки…"
    : attentionCount === 0
      ? "Все треки оформлены — проверка не требуется."
      : trackCountText(attentionCount);

  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Учётная запись</div>
          <h1>Профиль</h1>
          <p>Личные разделы и состояние музыкальной библиотеки.</p>
        </div>
      </div>

      <div className="music-profile-layout">
        <section className="music-profile-identity" aria-label="Информация о пользователе">
          <ProfileAvatar user={user} className="music-profile-avatar" />
          <div className="music-profile-copy">
            <div className="eyebrow">{user?.is_admin ? `Администратор · @${user.username}` : `@${user?.username}`}</div>
            <h2>{userDisplayName(user)}</h2>
            <p>{user?.bio || "Добавьте отображаемое имя и немного расскажите о себе."}</p>
            {(user?.location || user?.birth_date) && <div className="music-profile-details">
              {user.location && <span><MapPin size={13} />{user.location}</span>}
              {user.birth_date && <span><CakeSlice size={13} />{new Date(`${user.birth_date}T12:00:00`).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</span>}
            </div>}
          </div>
          <div className="music-profile-actions">
            <button className="button" type="button" onClick={() => setEditing(true)}><Pencil size={15} />Редактировать</button>
            <button className="button" type="button" onClick={() => setChangingPassword(true)}><KeyRound size={15} />Сменить пароль</button>
          </div>
        </section>

        <section className="profile-tools">
          <h2>Библиотека</h2>
          <Link
            href="/music/attention"
            className={`profile-action-card ${attentionCount && attentionCount > 0 ? "warning" : ""}`}
          >
            <span className="profile-action-icon"><CircleAlert size={20} /></span>
            <span className="profile-action-copy">
              <strong>Проблемные треки</strong>
              <span>{attentionText}</span>
            </span>
            <span className="profile-action-side">
              <span className="profile-action-count">{attentionCount ?? "—"}</span>
              <ChevronRight size={18} />
            </span>
          </Link>
        </section>
      </div>
      {editing && <ProfileEditDialog onClose={() => setEditing(false)} />}
      {changingPassword && <ProfilePasswordDialog onClose={() => setChangingPassword(false)} />}
    </div>
  );
}
