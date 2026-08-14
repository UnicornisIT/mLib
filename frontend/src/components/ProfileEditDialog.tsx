"use client";

import { Check, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { ProfileAvatar, userDisplayName } from "@/components/ProfileAvatar";
import type { UserProfileUpdate } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

const avatarColors = ["#f25f45", "#d98b35", "#b38b3d", "#5f8f4e", "#378b87", "#4f72b8", "#735eb2", "#a65378"];

export function ProfileEditDialog({ onClose }: { onClose: () => void }) {
  const { user, updateProfile } = useAuth();
  const now = new Date();
  const latestBirthDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  const [values, setValues] = useState<UserProfileUpdate>({
    display_name: user?.display_name ?? "",
    bio: user?.bio ?? "",
    location: user?.location ?? "",
    birth_date: user?.birth_date ?? "",
    avatar_color: user?.avatar_color || avatarColors[0],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const setValue = <K extends keyof UserProfileUpdate>(key: K, value: UserProfileUpdate[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await updateProfile({
        ...values,
        display_name: values.display_name?.trim() || null,
        bio: values.bio?.trim() || null,
        location: values.location?.trim() || null,
        birth_date: values.birth_date || null,
      });
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить профиль");
    } finally {
      setSaving(false);
    }
  };

  const previewUser = user ? { ...user, ...values } : null;

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal profile-edit-modal" role="dialog" aria-modal="true" aria-labelledby="profile-edit-title">
        <div className="modal-header">
          <div>
            <h2 id="profile-edit-title">Редактировать профиль</h2>
            <p>Эти данные будут видны во всех разделах mLib.</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть"><X size={18} /></button>
        </div>
        <form className="modal-body" onSubmit={save}>
          <div className="profile-edit-preview">
            <ProfileAvatar user={previewUser} className="profile-edit-avatar" />
            <div><strong>{userDisplayName(previewUser)}</strong><span>@{user?.username}</span></div>
          </div>

          <div className="profile-form-grid">
            <div className="field profile-form-wide">
              <label htmlFor="profile-login">Логин</label>
              <input id="profile-login" className="input" value={user?.username ?? ""} disabled />
              <small>Используется для входа и не меняется в профиле.</small>
            </div>
            <div className="field">
              <label htmlFor="profile-name">Отображаемое имя</label>
              <input id="profile-name" className="input" maxLength={120} placeholder="Как к вам обращаться" value={values.display_name ?? ""} onChange={(event) => setValue("display_name", event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="profile-location">Город или страна</label>
              <input id="profile-location" className="input" maxLength={120} placeholder="Например, Москва" value={values.location ?? ""} onChange={(event) => setValue("location", event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="profile-birth-date">Дата рождения</label>
              <input id="profile-birth-date" className="input" type="date" max={latestBirthDate} value={values.birth_date ?? ""} onChange={(event) => setValue("birth_date", event.target.value)} />
            </div>
            <fieldset className="profile-color-field">
              <legend>Цвет аватара</legend>
              <div className="profile-color-list">
                {avatarColors.map((color) => (
                  <button
                    key={color}
                    className={values.avatar_color === color ? "active" : ""}
                    type="button"
                    style={{ backgroundColor: color }}
                    onClick={() => setValue("avatar_color", color)}
                    aria-label={`Выбрать цвет ${color}`}
                    aria-pressed={values.avatar_color === color}
                  >
                    {values.avatar_color === color && <Check size={14} />}
                  </button>
                ))}
              </div>
            </fieldset>
            <div className="field profile-form-wide">
              <label htmlFor="profile-bio">О себе</label>
              <textarea id="profile-bio" className="textarea" maxLength={500} placeholder="Расскажите немного о себе" value={values.bio ?? ""} onChange={(event) => setValue("bio", event.target.value)} />
              <small>{values.bio?.length ?? 0}/500</small>
            </div>
          </div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <div className="form-actions">
            <button className="button" type="button" onClick={onClose}>Отмена</button>
            <button className="button primary" type="submit" disabled={saving}>{saving ? "Сохранение…" : "Сохранить"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
