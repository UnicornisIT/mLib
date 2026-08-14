"use client";

import { BookOpenText, CakeSlice, Film, KeyRound, MapPin, Music2, Pencil } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ProfileAvatar, userDisplayName } from "@/components/ProfileAvatar";
import { ProfileEditDialog } from "@/components/ProfileEditDialog";
import { ProfilePasswordDialog } from "@/components/ProfilePasswordDialog";
import { useAuth } from "@/providers/AuthProvider";

export default function ProfilePage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

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

      {editing && <ProfileEditDialog onClose={() => setEditing(false)} />}
      {changingPassword && <ProfilePasswordDialog onClose={() => setChangingPassword(false)} />}
    </section>
  );
}
