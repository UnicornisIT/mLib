"use client";

import { Check, CheckCircle2, Copy, Eye, EyeOff, KeyRound, ShieldCheck, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "@/providers/AuthProvider";

const MIN_PASSWORD_LENGTH = 15;

function PasswordField({
  id,
  label,
  value,
  autoComplete,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  autoComplete: "current-password" | "new-password";
  onChange: (value: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="password-input-wrap">
        <input
          id={id}
          className="input"
          type={visible ? "text" : "password"}
          value={value}
          autoComplete={autoComplete}
          maxLength={200}
          required
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" onClick={() => setVisible((current) => !current)} aria-label={visible ? "Скрыть пароль" : "Показать пароль"}>
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
    </div>
  );
}

export function ProfilePasswordDialog({ onClose }: { onClose: () => void }) {
  const { user, changePassword, createRecoveryKey } = useAuth();
  const [section, setSection] = useState<"password" | "recovery">("password");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [saving, setSaving] = useState(false);
  const [changed, setChanged] = useState(false);
  const [error, setError] = useState("");
  const [recoveryPassword, setRecoveryPassword] = useState("");
  const [recoveryKey, setRecoveryKey] = useState("");
  const [copied, setCopied] = useState(false);
  const normalizedLength = Array.from(newPassword.normalize("NFC")).length;
  const passwordsMatch = confirmation.length > 0 && newPassword.normalize("NFC") === confirmation.normalize("NFC");
  const canSubmit = Boolean(currentPassword && normalizedLength >= MIN_PASSWORD_LENGTH && passwordsMatch && !saving);
  const lengthProgress = Math.min(100, normalizedLength / 24 * 100);

  const selectSection = (nextSection: "password" | "recovery") => {
    setSection(nextSection);
    setError("");
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError("");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirmation: confirmation,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setChanged(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось изменить пароль");
    } finally {
      setSaving(false);
    }
  };

  const generateRecoveryKey = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!recoveryPassword || saving) return;
    setSaving(true);
    setError("");
    try {
      setRecoveryKey(await createRecoveryKey(recoveryPassword));
      setRecoveryPassword("");
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось создать ключ восстановления");
    } finally {
      setSaving(false);
    }
  };

  const copyRecoveryKey = async () => {
    try {
      await navigator.clipboard.writeText(recoveryKey);
      setCopied(true);
    } catch {
      setError("Не удалось скопировать ключ");
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal profile-password-modal" role="dialog" aria-modal="true" aria-labelledby="profile-password-title">
        <div className="modal-header">
          <div>
            <h2 id="profile-password-title">Безопасность</h2>
            <p>{section === "password" ? "Смена пароля учётной записи mLib." : "Ключ для восстановления доступа через сайт."}</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть"><X size={18} /></button>
        </div>

        <div className="profile-security-tabs" role="tablist" aria-label="Раздел безопасности">
          <button type="button" role="tab" aria-selected={section === "password"} className={section === "password" ? "active" : ""} onClick={() => selectSection("password")}>Пароль</button>
          <button type="button" role="tab" aria-selected={section === "recovery"} className={section === "recovery" ? "active" : ""} onClick={() => selectSection("recovery")}>Восстановление</button>
        </div>

        {section === "password" ? (
          changed ? (
            <div className="modal-body password-change-success">
              <span><CheckCircle2 size={28} /></span>
              <h3>Пароль изменён</h3>
              <p>Текущий сеанс сохранён, а все ранее выданные сеансы завершены.</p>
              <button className="button primary" type="button" onClick={onClose}>Готово</button>
            </div>
          ) : (
            <form className="modal-body" onSubmit={save}>
              <input className="visually-hidden" name="username" autoComplete="username" value={user?.username ?? ""} readOnly tabIndex={-1} />
              <div className="password-security-note">
                <ShieldCheck size={20} />
                <div><strong>Защищённая смена пароля</strong><span>После сохранения остальные устройства потребуется авторизовать заново.</span></div>
              </div>

              <PasswordField id="current-password" label="Текущий пароль" value={currentPassword} autoComplete="current-password" onChange={setCurrentPassword} />
              <PasswordField id="new-password" label="Новый пароль" value={newPassword} autoComplete="new-password" onChange={setNewPassword} />
              <div className="password-length" data-ready={normalizedLength >= MIN_PASSWORD_LENGTH}>
                <span><i style={{ width: `${lengthProgress}%` }} /></span>
                <small>{normalizedLength < MIN_PASSWORD_LENGTH ? `Ещё ${MIN_PASSWORD_LENGTH - normalizedLength} симв.` : normalizedLength >= 24 ? "Хорошая длина" : "Минимальная длина выполнена"}</small>
              </div>
              <PasswordField id="new-password-confirmation" label="Повторите новый пароль" value={confirmation} autoComplete="new-password" onChange={setConfirmation} />
              {confirmation && !passwordsMatch && <div className="field-message error">Пароли не совпадают</div>}

              <div className="password-guidance">
                <KeyRound size={16} />
                <span>Используйте не менее 15 символов. Подойдёт длинная запоминающаяся фраза; пробелы и любые символы разрешены.</span>
              </div>
              {error && <div className="form-error">{error}</div>}
              <div className="form-actions">
                <button className="button" type="button" onClick={onClose}>Отмена</button>
                <button className="button primary" type="submit" disabled={!canSubmit}>{saving ? "Сохранение…" : "Изменить пароль"}</button>
              </div>
            </form>
          )
        ) : recoveryKey ? (
          <div className="modal-body recovery-key-result">
            <span><KeyRound size={26} /></span>
            <h3>Ключ восстановления создан</h3>
            <p>Сохраните его отдельно. После закрытия он больше не будет показан.</p>
            <code>{recoveryKey}</code>
            {error && <div className="form-error">{error}</div>}
            <div className="form-actions">
              <button className="button" type="button" onClick={copyRecoveryKey}>{copied ? <Check size={16} /> : <Copy size={16} />}{copied ? "Скопировано" : "Скопировать"}</button>
              <button className="button primary" type="button" onClick={onClose}>Готово</button>
            </div>
          </div>
        ) : (
          <form className="modal-body" onSubmit={generateRecoveryKey}>
            <div className="password-security-note">
              <KeyRound size={20} />
              <div><strong>Одноразовый ключ</strong><span>Он позволит задать новый пароль на странице входа. Новый ключ заменит ранее созданный.</span></div>
            </div>
            <PasswordField id="recovery-current-password" label="Текущий пароль" value={recoveryPassword} autoComplete="current-password" onChange={setRecoveryPassword} />
            {error && <div className="form-error">{error}</div>}
            <div className="form-actions">
              <button className="button" type="button" onClick={onClose}>Отмена</button>
              <button className="button primary" type="submit" disabled={!recoveryPassword || saving}>{saving ? "Создание…" : "Создать ключ"}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
