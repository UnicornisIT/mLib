const { contextBridge, ipcRenderer } = require("electron");

const argument = process.argv.find((value) => value.startsWith("--mlib-api-base="));
const apiBase = argument ? argument.slice("--mlib-api-base=".length) : "/api";

contextBridge.exposeInMainWorld("mlibDesktop", Object.freeze({
  apiBase,
  chooseDataFile: (kind) => ipcRenderer.invoke("mlib:choose-data-file", kind),
  openLogs: () => ipcRenderer.invoke("mlib:open-logs"),
  resetPassword: (payload) => ipcRenderer.invoke("mlib:reset-password", payload),
  getUpdateStatus: () => ipcRenderer.invoke("mlib:update-status"),
  checkForUpdates: () => ipcRenderer.invoke("mlib:update-check"),
  downloadUpdate: () => ipcRenderer.invoke("mlib:update-download"),
  installUpdate: () => ipcRenderer.invoke("mlib:update-install"),
  onUpdateStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on("mlib:update-status", listener);
    return () => ipcRenderer.removeListener("mlib:update-status", listener);
  },
}));
