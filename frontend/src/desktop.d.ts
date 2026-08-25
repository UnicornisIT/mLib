export {};

type DesktopUpdateState = "disabled" | "idle" | "checking" | "up-to-date" | "available" | "downloading" | "downloaded" | "error";

type DesktopUpdateStatus = {
  enabled: boolean;
  state: DesktopUpdateState;
  currentVersion: string;
  availableVersion: string | null;
  progress: number | null;
  message: string;
};

declare global {
  interface Window {
    mlibDesktop?: {
      apiBase: string;
      chooseDataFile: (kind: "export" | "import" | "backup" | "restore") => Promise<string | null>;
      openLogs: () => Promise<string>;
      getUpdateStatus: () => Promise<DesktopUpdateStatus>;
      checkForUpdates: () => Promise<DesktopUpdateStatus>;
      downloadUpdate: () => Promise<DesktopUpdateStatus>;
      installUpdate: () => Promise<boolean>;
      onUpdateStatus: (callback: (status: DesktopUpdateStatus) => void) => () => void;
    };
  }
}
