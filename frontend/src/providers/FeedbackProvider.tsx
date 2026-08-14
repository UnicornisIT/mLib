"use client";

import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { createContext, FormEvent, useCallback, useContext, useMemo, useRef, useState } from "react";

type ConfirmOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
};

type PromptOptions = ConfirmOptions & {
  defaultValue?: string;
  placeholder?: string;
  allowEmpty?: boolean;
};

type DialogRequest =
  | ({ kind: "confirm"; resolve: (value: boolean) => void } & ConfirmOptions)
  | ({ kind: "prompt"; resolve: (value: string | null) => void } & PromptOptions);

type Toast = { id: number; message: string; tone: "success" | "error" };

type FeedbackContextValue = {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
  notify: (message: string, tone?: Toast["tone"]) => void;
};

const FeedbackContext = createContext<FeedbackContextValue | null>(null);

export function FeedbackProvider({ children }: { children: React.ReactNode }) {
  const [dialog, setDialog] = useState<DialogRequest | null>(null);
  const [promptValue, setPromptValue] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);

  const confirm = useCallback((options: ConfirmOptions) => new Promise<boolean>((resolve) => {
    setDialog({ kind: "confirm", ...options, resolve });
  }), []);

  const prompt = useCallback((options: PromptOptions) => new Promise<string | null>((resolve) => {
    setPromptValue(options.defaultValue ?? "");
    setDialog({ kind: "prompt", ...options, resolve });
  }), []);

  const notify = useCallback((message: string, tone: Toast["tone"] = "success") => {
    const id = ++toastId.current;
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4500);
  }, []);

  const close = (accepted: boolean) => {
    if (!dialog) return;
    if (dialog.kind === "confirm") dialog.resolve(accepted);
    else dialog.resolve(accepted ? promptValue : null);
    setDialog(null);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (dialog?.kind === "prompt" && !dialog.allowEmpty && !promptValue.trim()) return;
    close(true);
  };

  const value = useMemo(() => ({ confirm, prompt, notify }), [confirm, notify, prompt]);

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div className={`toast ${toast.tone}`} key={toast.id} role={toast.tone === "error" ? "alert" : "status"}>
            {toast.tone === "success" ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}
            <span>{toast.message}</span>
            <button type="button" onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))} aria-label="Закрыть уведомление"><X size={16} /></button>
          </div>
        ))}
      </div>
      {dialog && (
        <div className="modal-backdrop feedback-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close(false)}>
          <form className="modal feedback-dialog" role="alertdialog" aria-modal="true" aria-labelledby="feedback-title" aria-describedby="feedback-message" onSubmit={submit}>
            <div className="modal-header">
              <h2 id="feedback-title">{dialog.title}</h2>
              <button className="icon-button" type="button" onClick={() => close(false)} aria-label="Закрыть"><X size={18} /></button>
            </div>
            <div className="modal-body">
              <p id="feedback-message" className="feedback-message">{dialog.message}</p>
              {dialog.kind === "prompt" && (
                <label className="field">
                  <span>Значение</span>
                  <input className="input" autoFocus value={promptValue} placeholder={dialog.placeholder} onChange={(event) => setPromptValue(event.target.value)} />
                </label>
              )}
              <div className="form-actions">
                <button className="button" type="button" onClick={() => close(false)}>{dialog.cancelLabel ?? "Отмена"}</button>
                <button className={`button ${dialog.destructive ? "danger" : "primary"}`} type="submit" disabled={dialog.kind === "prompt" && !dialog.allowEmpty && !promptValue.trim()}>{dialog.confirmLabel ?? "Подтвердить"}</button>
              </div>
            </div>
          </form>
        </div>
      )}
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const context = useContext(FeedbackContext);
  if (!context) throw new Error("useFeedback must be used inside FeedbackProvider");
  return context;
}
