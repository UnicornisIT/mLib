"use client";

import { ArrowLeft, AudioLines, Eye, EyeOff } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/providers/AuthProvider";

function PasswordInput({
  id,
  label,
  value,
  autoComplete,
  minLength = 1,
  describedBy,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  autoComplete: "current-password" | "new-password";
  minLength?: number;
  describedBy?: string;
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
          autoComplete={autoComplete}
          minLength={minLength}
          maxLength={200}
          required
          value={value}
          aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" onClick={() => setVisible((current) => !current)} aria-label={visible ? "Скрыть пароль" : "Показать пароль"}>
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { loading, setupRequired, login, setup, recoverPassword } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [libraryPath, setLibraryPath] = useState("");
  const [importPath, setImportPath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [desktop, setDesktop] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [recoveryKey, setRecoveryKey] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

  useEffect(() => {
    // Desktop capability is injected by Electron after server-side rendering.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDesktop(Boolean(window.mlibDesktop));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const normalizedUsername = username.trim();
    if (normalizedUsername.length < 3) {
      setError("Имя пользователя должно содержать не менее 3 символов");
      return;
    }
    if (setupRequired && password.length < 15) {
      setError("Пароль должен содержать не менее 15 символов");
      return;
    }
    setSubmitting(true);
    try {
      if (setupRequired) {
        await setup({
          username: normalizedUsername,
          password,
          library_path: desktop ? undefined : libraryPath.trim() || undefined,
          import_path: desktop ? undefined : importPath.trim() || undefined,
        });
      } else await login(normalizedUsername, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось войти");
    } finally {
      setSubmitting(false);
    }
  };

  const submitRecovery = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (newPassword.normalize("NFC").length < 15) {
      setError("Новый пароль должен содержать не менее 15 символов");
      return;
    }
    if (newPassword.normalize("NFC") !== confirmation.normalize("NFC")) {
      setError("Новые пароли не совпадают");
      return;
    }
    if (!desktop && !recoveryKey.trim()) {
      setError("Введите ключ восстановления");
      return;
    }

    setSubmitting(true);
    try {
      if (desktop) {
        const result = await window.mlibDesktop!.resetPassword({
          newPassword,
          newPasswordConfirmation: confirmation,
        });
        await login(result.username, newPassword);
      } else {
        await recoverPassword({
          recovery_key: recoveryKey.trim(),
          new_password: newPassword,
          new_password_confirmation: confirmation,
        });
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось восстановить доступ");
    } finally {
      setSubmitting(false);
    }
  };

  const closeRecovery = () => {
    setRecovering(false);
    setRecoveryKey("");
    setNewPassword("");
    setConfirmation("");
    setError("");
  };

  if (loading) return <div className="app-loading"><div className="loading-mark" /></div>;
  return (
    <div className="auth-page">
      <section className="auth-panel">
        <div className="brand auth-brand"><span className="brand-mark"><AudioLines size={18} /></span>mLib</div>
        {recovering ? (
          <form className="auth-form" onSubmit={submitRecovery}>
            <div className="eyebrow">Восстановление доступа</div>
            <h1>Задайте новый пароль</h1>
            <p>{desktop ? "Новый пароль заменит забытый и завершит прежние сеансы." : "Введите сохранённый ключ восстановления и задайте новый пароль."}</p>
            {!desktop && (
              <div className="field">
                <label htmlFor="auth-recovery-key">Ключ восстановления</label>
                <input
                  id="auth-recovery-key"
                  className="input auth-recovery-key-input"
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  maxLength={200}
                  required
                  value={recoveryKey}
                  onChange={(event) => setRecoveryKey(event.target.value)}
                />
              </div>
            )}
            <PasswordInput id="auth-new-password" label="Новый пароль" value={newPassword} autoComplete="new-password" minLength={15} describedBy="auth-new-password-hint" onChange={setNewPassword} />
            <small id="auth-new-password-hint" className="auth-password-hint">Не менее 15 символов; можно использовать длинную фразу.</small>
            <PasswordInput id="auth-new-password-confirmation" label="Повторите новый пароль" value={confirmation} autoComplete="new-password" minLength={15} onChange={setConfirmation} />
            {error && <div className="form-error" role="alert" aria-live="polite">{error}</div>}
            <div className="auth-action-stack">
              <button type="submit" className="button primary auth-submit" disabled={submitting}>
                {submitting ? "Подождите…" : "Восстановить доступ"}
              </button>
              <button type="button" className="auth-back-button" onClick={closeRecovery}><ArrowLeft size={15} /> Вернуться ко входу</button>
            </div>
          </form>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            <div className="eyebrow">{setupRequired ? "Первый запуск" : "С возвращением"}</div>
            <h1>{setupRequired ? "Создайте пространство mLib" : "Войдите в mLib"}</h1>
            <p>{setupRequired ? "Один администратор и один вход для musicLib, movieLib и будущих сервисов." : "Все ваши личные медиатеки доступны через один безопасный вход."}</p>
            <div className="field"><label htmlFor="auth-username">Имя пользователя</label><input id="auth-username" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={80} required value={username} onChange={(event) => setUsername(event.target.value)} /></div>
            <PasswordInput id="auth-password" label="Пароль" value={password} autoComplete={setupRequired ? "new-password" : "current-password"} minLength={setupRequired ? 15 : 1} describedBy={setupRequired ? "auth-password-hint" : undefined} onChange={setPassword} />
            {setupRequired && <small id="auth-password-hint" className="auth-password-hint">Не менее 15 символов; можно использовать длинную фразу.</small>}
            {setupRequired && !desktop && (
              <>
                <div className="field"><label htmlFor="auth-library-path">Путь к медиатеке (необязательно)</label><input id="auth-library-path" className="input" value={libraryPath} onChange={(event) => setLibraryPath(event.target.value)} placeholder="По умолчанию: ./media" /></div>
                <div className="field"><label htmlFor="auth-import-path">Разрешённая папка импорта (необязательно)</label><input id="auth-import-path" className="input" value={importPath} onChange={(event) => setImportPath(event.target.value)} placeholder="Например: /data/music" /></div>
              </>
            )}
            {error && <div className="form-error" role="alert" aria-live="polite">{error}</div>}
            <div className="auth-action-stack">
              <button type="submit" className="button primary auth-submit" disabled={submitting}>
                {submitting ? "Подождите…" : setupRequired ? "Начать" : "Войти"}
              </button>
              {!setupRequired && (
                <button type="button" className="auth-recovery-link" onClick={() => { setRecovering(true); setError(""); }}>
                  Забыли пароль?
                </button>
              )}
            </div>
          </form>
        )}
      </section>
      <aside className="auth-visual">
        <div>
          <div className="auth-quote">Вся ваша медиатека. В одном спокойном месте.</div>
          <div className="auth-note">Музыка, фильмы и будущие коллекции — с единым аккаунтом mLib.</div>
        </div>
      </aside>
    </div>
  );
}
