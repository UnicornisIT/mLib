"use client";

import { AudioLines } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "@/providers/AuthProvider";

export default function LoginPage() {
  const { loading, setupRequired, login, setup } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [libraryPath, setLibraryPath] = useState("");
  const [importPath, setImportPath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
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
          library_path: libraryPath.trim() || undefined,
          import_path: importPath.trim() || undefined,
        });
      } else await login(normalizedUsername, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось войти");
    } finally {
      setSubmitting(false);
    }
  };
  if (loading) return <div className="app-loading"><div className="loading-mark" /></div>;
  return (
    <div className="auth-page">
      <section className="auth-panel">
        <div className="brand auth-brand"><span className="brand-mark"><AudioLines size={18} /></span>mLib</div>
        <form className="auth-form" onSubmit={submit}>
          <div className="eyebrow">{setupRequired ? "Первый запуск" : "С возвращением"}</div>
          <h1>{setupRequired ? "Создайте пространство mLib" : "Войдите в mLib"}</h1>
          <p>{setupRequired ? "Один администратор и один вход для musicLib, movieLib и будущих сервисов." : "Все ваши личные медиатеки доступны через один безопасный вход."}</p>
          <div className="field"><label htmlFor="auth-username">Имя пользователя</label><input id="auth-username" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={80} required value={username} onChange={(event) => setUsername(event.target.value)} /></div>
          <div className="field"><label htmlFor="auth-password">Пароль</label><input id="auth-password" className="input" type="password" autoComplete={setupRequired ? "new-password" : "current-password"} minLength={setupRequired ? 15 : 1} maxLength={200} required value={password} onChange={(event) => setPassword(event.target.value)} aria-describedby={setupRequired ? "auth-password-hint" : undefined} />{setupRequired && <small id="auth-password-hint" style={{ color: "var(--muted)" }}>Не менее 15 символов; можно использовать длинную фразу.</small>}</div>
          {setupRequired && (
            <>
              <div className="field"><label htmlFor="auth-library-path">Путь к медиатеке (необязательно)</label><input id="auth-library-path" className="input" value={libraryPath} onChange={(event) => setLibraryPath(event.target.value)} placeholder="По умолчанию: ./media" /></div>
              <div className="field"><label htmlFor="auth-import-path">Разрешённая папка импорта (необязательно)</label><input id="auth-import-path" className="input" value={importPath} onChange={(event) => setImportPath(event.target.value)} placeholder="Например: /data/music" /></div>
            </>
          )}
          {error && <div className="form-error" role="alert" aria-live="polite">{error}</div>}
          <button type="submit" className="button primary" style={{ width: "100%", marginTop: 20 }} disabled={submitting}>
            {submitting ? "Подождите…" : setupRequired ? "Начать" : "Войти"}
          </button>
        </form>
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
