"use client";

import { Eye, KeyRound, MousePointer2, ShieldCheck, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import packageInfo from "../../package.json";
import { getReleaseAnnouncement, type ReleaseNoteIcon } from "@/lib/releaseNotes";

const icons: Record<ReleaseNoteIcon, typeof Sparkles> = {
  key: KeyRound,
  eye: Eye,
  motion: MousePointer2,
  brand: Sparkles,
  shield: ShieldCheck,
};

export function ReleaseNotesDialog({ userId }: { userId: string }) {
  const announcement = getReleaseAnnouncement(packageInfo.version);
  const storageKey = `mlib:release-notes:${userId}`;
  const [open, setOpen] = useState(() => {
    if (!announcement || typeof window === "undefined") return false;
    if (window.mlibDesktop) return false;
    try {
      return window.localStorage.getItem(storageKey) !== announcement.version;
    } catch {
      return true;
    }
  });
  const [ready, setReady] = useState(() => typeof window !== "undefined" && !window.mlibDesktop);

  useEffect(() => {
    const desktop = window.mlibDesktop;
    if (!announcement || !desktop) return;
    let active = true;
    void desktop.getReleaseNotesSeenVersion(userId).then((seenVersion) => {
      if (!active) return;
      setOpen(seenVersion !== announcement.version);
      setReady(true);
    }).catch(() => {
      if (!active) return;
      setOpen(true);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, [announcement, userId]);

  const close = useCallback(() => {
    if (announcement) {
      if (window.mlibDesktop) {
        void window.mlibDesktop.markReleaseNotesSeen(userId, announcement.version);
      } else {
        try {
          window.localStorage.setItem(storageKey, announcement.version);
        } catch {
          // The announcement can still be dismissed when persistent browser storage is unavailable.
        }
      }
    }
    setOpen(false);
  }, [announcement, storageKey, userId]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.documentElement.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.documentElement.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.documentElement.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [close, open]);

  if (!announcement || !ready || !open) return null;

  return (
    <div className="modal-backdrop release-notes-backdrop" role="presentation">
      <section className="modal release-notes-dialog" role="dialog" aria-modal="true" aria-labelledby="release-notes-title" aria-describedby="release-notes-intro">
        <div className="release-notes-hero">
          <div className="release-notes-mark" aria-hidden="true"><Sparkles size={24} /></div>
          <div className="release-notes-heading">
            <span>mLib · версия {announcement.version}</span>
            <h2 id="release-notes-title">{announcement.title}</h2>
            <p id="release-notes-intro">{announcement.intro}</p>
          </div>
          <button className="release-notes-close" type="button" onClick={close} aria-label="Закрыть"><X size={19} /></button>
        </div>

        <div className="release-notes-list">
          {announcement.notes.map((note) => {
            const Icon = icons[note.icon];
            return (
              <article className="release-note" key={note.title}>
                <span className="release-note-icon" aria-hidden="true"><Icon size={19} /></span>
                <div>
                  <h3>{note.title}</h3>
                  <p>{note.description}</p>
                </div>
              </article>
            );
          })}
        </div>

        <div className="release-notes-footer">
          <button className="button primary release-notes-continue" type="button" autoFocus onClick={close}>Продолжить</button>
        </div>
      </section>
    </div>
  );
}
