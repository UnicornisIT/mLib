"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type DesktopUpdateState = "disabled" | "idle" | "checking" | "up-to-date" | "available" | "downloading" | "downloaded" | "error";

export type DesktopUpdateStatus = {
  enabled: boolean;
  state: DesktopUpdateState;
  currentVersion: string;
  availableVersion: string | null;
  progress: number | null;
  message: string;
};

type DesktopUpdateContextValue = {
  status: DesktopUpdateStatus;
  checkForUpdates: () => Promise<void>;
  downloadUpdate: () => Promise<void>;
  installUpdate: () => Promise<void>;
};

const defaultStatus: DesktopUpdateStatus = {
  enabled: false,
  state: "disabled",
  currentVersion: "",
  availableVersion: null,
  progress: null,
  message: "Обновления доступны в Windows Desktop",
};

const DesktopUpdateContext = createContext<DesktopUpdateContextValue | null>(null);

export function DesktopUpdateProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState(defaultStatus);

  useEffect(() => {
    const desktop = window.mlibDesktop;
    if (!desktop) return;
    let active = true;
    void desktop.getUpdateStatus().then((value) => {
      if (active) setStatus(value);
    });
    const unsubscribe = desktop.onUpdateStatus((value) => {
      if (active) setStatus(value);
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const value = useMemo<DesktopUpdateContextValue>(() => ({
    status,
    checkForUpdates: async () => {
      if (!window.mlibDesktop) return;
      setStatus(await window.mlibDesktop.checkForUpdates());
    },
    downloadUpdate: async () => {
      if (!window.mlibDesktop) return;
      setStatus(await window.mlibDesktop.downloadUpdate());
    },
    installUpdate: async () => {
      await window.mlibDesktop?.installUpdate();
    },
  }), [status]);

  return <DesktopUpdateContext.Provider value={value}>{children}</DesktopUpdateContext.Provider>;
}

export function useDesktopUpdate() {
  const value = useContext(DesktopUpdateContext);
  if (!value) throw new Error("useDesktopUpdate must be used inside DesktopUpdateProvider");
  return value;
}
