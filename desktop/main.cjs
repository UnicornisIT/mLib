const { app, BrowserWindow, dialog, ipcMain, screen, shell } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const APP_ID = "app.mlib.desktop";
const UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;
const localAppData = process.env.LOCALAPPDATA || path.dirname(app.getPath("userData"));
const dataRoot = path.join(localAppData, "mLib");
const directories = {
  root: dataRoot,
  data: path.join(dataRoot, "data"),
  media: path.join(dataRoot, "media"),
  backups: path.join(dataRoot, "backups"),
  logs: path.join(dataRoot, "logs"),
  config: path.join(dataRoot, "config"),
  temp: path.join(dataRoot, "temp"),
};
app.setPath("userData", path.join(directories.config, "electron"));
app.setAppUserModelId(APP_ID);

let mainWindow = null;
let backendProcess = null;
let frontendProcess = null;
let backendPort = null;
let frontendPort = null;
let desktopToken = null;
let shuttingDown = false;
let servicesStarted = false;
let updateCheckInFlight = false;
let updateDownloaded = false;
let updateCheckTimer = null;
let updateStatus = {
  enabled: false,
  state: "disabled",
  currentVersion: app.getVersion(),
  availableVersion: null,
  progress: null,
  message: "Автообновление доступно в сборке из GitHub Releases",
};

function ensureDirectories() {
  for (const directory of Object.values(directories)) {
    fs.mkdirSync(directory, { recursive: true });
  }
}

function rotateShellLog() {
  const logPath = path.join(directories.logs, "desktop.log");
  try {
    if (fs.existsSync(logPath) && fs.statSync(logPath).size > 5 * 1024 * 1024) {
      const previous = `${logPath}.1`;
      fs.rmSync(previous, { force: true });
      fs.renameSync(logPath, previous);
    }
  } catch {}
  return logPath;
}

function log(message) {
  try {
    const line = `${new Date().toISOString()} ${message}\n`;
    fs.appendFileSync(rotateShellLog(), line, "utf8");
  } catch {}
}

function setUpdateStatus(values) {
  updateStatus = { ...updateStatus, ...values, currentVersion: app.getVersion() };
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("mlib:update-status", updateStatus);
  }
  return updateStatus;
}

function updaterLog(level, message) {
  log(`updater ${level}: ${typeof message === "string" ? message : JSON.stringify(message)}`);
}

async function checkForUpdates() {
  if (!updateStatus.enabled || updateCheckInFlight) return updateStatus;
  updateCheckInFlight = true;
  try {
    await autoUpdater.checkForUpdates();
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    log(`Updater check failed: ${detail}`);
    setUpdateStatus({ state: "error", progress: null, message: "Не удалось проверить обновления. Проверьте подключение к интернету." });
  } finally {
    updateCheckInFlight = false;
  }
  return updateStatus;
}

function configureAutoUpdater() {
  const updateConfigPath = path.join(process.resourcesPath, "app-update.yml");
  if (!app.isPackaged || !fs.existsSync(updateConfigPath)) {
    setUpdateStatus({
      enabled: false,
      state: "disabled",
      message: app.isPackaged
        ? "Эта сборка не подключена к GitHub Releases"
        : "Проверка обновлений отключена в режиме разработки",
    });
    return;
  }

  autoUpdater.logger = {
    info: (message) => updaterLog("info", message),
    warn: (message) => updaterLog("warn", message),
    error: (message) => updaterLog("error", message),
    debug: (message) => updaterLog("debug", message),
  };
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;
  autoUpdater.allowPrerelease = app.getVersion().includes("-");
  autoUpdater.allowDowngrade = false;

  autoUpdater.on("checking-for-update", () => {
    setUpdateStatus({ enabled: true, state: "checking", progress: null, message: "Проверяем обновления…" });
  });
  autoUpdater.on("update-not-available", () => {
    setUpdateStatus({ enabled: true, state: "up-to-date", availableVersion: null, progress: null, message: "Установлена актуальная версия" });
  });
  autoUpdater.on("update-available", (info) => {
    updateDownloaded = false;
    setUpdateStatus({
      enabled: true,
      state: "available",
      availableVersion: typeof info.version === "string" ? info.version : null,
      progress: 0,
      message: "Доступна новая версия mLib",
    });
  });
  autoUpdater.on("download-progress", (progress) => {
    setUpdateStatus({
      enabled: true,
      state: "downloading",
      progress: Number.isFinite(progress.percent) ? Math.max(0, Math.min(100, progress.percent)) : null,
      message: "Скачиваем обновление…",
    });
  });
  autoUpdater.on("update-downloaded", (info) => {
    updateDownloaded = true;
    setUpdateStatus({
      enabled: true,
      state: "downloaded",
      availableVersion: typeof info.version === "string" ? info.version : updateStatus.availableVersion,
      progress: 100,
      message: "Обновление готово к установке",
    });
  });
  autoUpdater.on("error", (error) => {
    const detail = error instanceof Error ? error.message : String(error);
    log(`Updater error: ${detail}`);
    setUpdateStatus({ enabled: true, state: "error", progress: null, message: "Не удалось получить обновление. Попробуйте позже." });
  });

  setUpdateStatus({ enabled: true, state: "idle", message: "Обновления проверяются автоматически" });
  const initialCheckTimer = setTimeout(() => void checkForUpdates(), 15_000);
  initialCheckTimer.unref?.();
  updateCheckTimer = setInterval(() => void checkForUpdates(), UPDATE_CHECK_INTERVAL_MS);
  updateCheckTimer.unref?.();
}

function loadOrCreateSecret() {
  const configPath = path.join(directories.config, "desktop.json");
  try {
    const existing = JSON.parse(fs.readFileSync(configPath, "utf8"));
    if (typeof existing.secretKey === "string" && existing.secretKey.length >= 32) return existing.secretKey;
  } catch {}
  const secretKey = crypto.randomBytes(48).toString("base64url");
  const partial = `${configPath}.partial`;
  fs.writeFileSync(partial, JSON.stringify({ version: 1, secretKey }, null, 2), { encoding: "utf8", mode: 0o600 });
  fs.renameSync(partial, configPath);
  return secretKey;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function sqliteUrl(fileName) {
  return `sqlite:///${path.join(directories.data, fileName).replaceAll("\\", "/")}`;
}

function resourcePath(name) {
  return app.isPackaged ? path.join(process.resourcesPath, name) : path.join(__dirname, "build", name);
}

function spawnLogged(executable, args, options, label) {
  const child = spawn(executable, args, { windowsHide: true, stdio: "ignore", ...options });
  child.on("error", (error) => log(`${label} launch error: ${error.message}`));
  child.on("exit", (code, signal) => {
    log(`${label} exited code=${code} signal=${signal}`);
    if (!shuttingDown && servicesStarted) void showStartupFailure(`${label} неожиданно завершил работу`);
  });
  return child;
}

async function waitForUrl(url, timeoutMs, child, label) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`${label} завершился с кодом ${child.exitCode}`);
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) return;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`${label} не запустился вовремя: ${lastError?.message || "нет ответа"}`);
}

async function startServices() {
  ensureDirectories();
  backendPort = await freePort();
  frontendPort = await freePort();
  desktopToken = crypto.randomBytes(32).toString("base64url");
  const secretKey = loadOrCreateSecret();
  const backendDirectory = resourcePath("backend");
  const backendExecutable = path.join(backendDirectory, "mlib-backend.exe");
  const frontendServer = path.join(resourcePath("frontend"), "server.js");
  if (!fs.existsSync(backendExecutable)) throw new Error(`Не найден ${backendExecutable}`);
  if (!fs.existsSync(frontendServer)) throw new Error(`Не найден ${frontendServer}`);

  const backendEnvironment = {
    ...process.env,
    APP_NAME: "mLib",
    APP_VERSION: app.getVersion(),
    APP_MODE: "desktop",
    ENVIRONMENT: "production",
    SECRET_KEY: secretKey,
    DESKTOP_TOKEN: desktopToken,
    MLIB_BACKEND_PORT: String(backendPort),
    DATA_ROOT: directories.data,
    MEDIA_ROOT: directories.media,
    BACKUPS_ROOT: directories.backups,
    TEMP_ROOT: directories.temp,
    LOG_FILE: path.join(directories.logs, "mlib.log"),
    CORE_DATABASE_URL: sqliteUrl("core.db"),
    MUSIC_DATABASE_URL: sqliteUrl("music.db"),
    MOVIE_DATABASE_URL: sqliteUrl("movie.db"),
    BOOKS_DATABASE_URL: sqliteUrl("books.db"),
    COLLECTIONS_DATABASE_URL: sqliteUrl("collections.db"),
    GAMES_DATABASE_URL: sqliteUrl("games.db"),
    WISHES_DATABASE_URL: sqliteUrl("wishes.db"),
    CORS_ORIGINS: `http://127.0.0.1:${frontendPort}`,
    COOKIE_SECURE: "false",
    FFPROBE_PATH: path.join(resourcePath("tools"), "ffprobe.exe"),
  };
  backendProcess = spawnLogged(backendExecutable, [], { cwd: backendDirectory, env: backendEnvironment }, "backend");
  await waitForUrl(`http://127.0.0.1:${backendPort}/health`, 60_000, backendProcess, "Backend");

  const frontendEnvironment = {
    ...process.env,
    ELECTRON_RUN_AS_NODE: "1",
    NODE_ENV: "production",
    HOSTNAME: "127.0.0.1",
    PORT: String(frontendPort),
    BACKEND_INTERNAL_URL: `http://127.0.0.1:${backendPort}`,
  };
  frontendProcess = spawnLogged(process.execPath, [frontendServer], {
    cwd: path.dirname(frontendServer),
    env: frontendEnvironment,
  }, "frontend");
  await waitForUrl(`http://127.0.0.1:${frontendPort}/`, 60_000, frontendProcess, "Интерфейс");
  servicesStarted = true;
}

function loadWindowState() {
  const fallback = { width: 1360, height: 860 };
  try {
    const state = JSON.parse(fs.readFileSync(path.join(directories.config, "window-state.json"), "utf8"));
    if (state.width < 1024 || state.height < 700) return fallback;
    const visible = screen.getAllDisplays().some((display) => {
      const area = display.workArea;
      return state.x < area.x + area.width && state.x + state.width > area.x &&
        state.y < area.y + area.height && state.y + state.height > area.y;
    });
    return visible ? state : fallback;
  } catch {
    return fallback;
  }
}

function saveWindowState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const bounds = mainWindow.isMaximized() ? mainWindow.getNormalBounds() : mainWindow.getBounds();
  const state = { ...bounds, maximized: mainWindow.isMaximized() };
  try {
    fs.writeFileSync(path.join(directories.config, "window-state.json"), JSON.stringify(state, null, 2));
  } catch (error) {
    log(`Cannot save window state: ${error.message}`);
  }
}

function createWindow() {
  const state = loadWindowState();
  mainWindow = new BrowserWindow({
    title: "mLib",
    ...state,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    backgroundColor: "#111210",
    icon: app.isPackaged ? process.execPath : path.join(__dirname, "build", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      additionalArguments: [`--mlib-api-base=http://127.0.0.1:${backendPort}/api`],
    },
  });
  if (state.maximized) mainWindow.maximize();
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("close", saveWindowState);
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https:\/\//i.test(url)) void shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(`http://127.0.0.1:${frontendPort}/`)) event.preventDefault();
  });
  void mainWindow.loadURL(`http://127.0.0.1:${frontendPort}/`);
}

const dataDialogs = {
  export: { mode: "save", title: "Экспортировать библиотеку", prefix: "mLib-export", filter: "Экспорт mLib" },
  backup: { mode: "save", title: "Создать резервную копию", prefix: "mLib-backup", filter: "Резервная копия mLib" },
  import: { mode: "open", title: "Импортировать библиотеку", filter: "Экспорт mLib" },
  restore: { mode: "open", title: "Восстановить резервную копию", filter: "Резервная копия mLib" },
};

function registerIpc() {
  ipcMain.handle("mlib:choose-data-file", async (_event, kind) => {
    const definition = dataDialogs[kind];
    if (!definition) throw new Error("Unknown data dialog");
    const filters = [{ name: definition.filter, extensions: ["zip"] }];
    if (definition.mode === "save") {
      const date = new Date().toISOString().slice(0, 10);
      const base = kind === "backup" ? directories.backups : app.getPath("documents");
      const result = await dialog.showSaveDialog(mainWindow, {
        title: definition.title,
        defaultPath: path.join(base, `${definition.prefix}-${date}.zip`),
        filters,
      });
      return result.canceled ? null : result.filePath;
    }
    const result = await dialog.showOpenDialog(mainWindow, {
      title: definition.title,
      defaultPath: kind === "restore" ? directories.backups : app.getPath("documents"),
      filters,
      properties: ["openFile"],
    });
    return result.canceled ? null : result.filePaths[0];
  });
  ipcMain.handle("mlib:open-logs", () => shell.openPath(directories.logs));
  ipcMain.handle("mlib:reset-password", async (_event, payload) => {
    const callerUrl = _event.senderFrame?.url || "";
    if (!frontendPort || !callerUrl.startsWith(`http://127.0.0.1:${frontendPort}/`)) {
      throw new Error("Восстановление доступа недоступно для этого окна");
    }
    const newPassword = payload?.newPassword;
    const confirmation = payload?.newPasswordConfirmation;
    if (
      typeof newPassword !== "string"
      || typeof confirmation !== "string"
      || newPassword.length > 200
      || confirmation.length > 200
    ) {
      throw new Error("Не удалось проверить новый пароль");
    }
    if (!backendPort || !desktopToken) throw new Error("mLib ещё не готов к восстановлению доступа");

    const response = await fetch(`http://127.0.0.1:${backendPort}/desktop/password-reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-mLib-Desktop-Token": desktopToken,
      },
      body: JSON.stringify({
        new_password: newPassword,
        new_password_confirmation: confirmation,
      }),
      signal: AbortSignal.timeout(15_000),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof result.detail === "string" ? result.detail : "Не удалось сбросить пароль");
    }
    return { username: result.username };
  });
  ipcMain.handle("mlib:update-status", () => updateStatus);
  ipcMain.handle("mlib:update-check", () => checkForUpdates());
  ipcMain.handle("mlib:update-download", async () => {
    if (!updateStatus.enabled || updateStatus.state !== "available") return updateStatus;
    setUpdateStatus({ state: "downloading", progress: 0, message: "Скачиваем обновление…" });
    try {
      await autoUpdater.downloadUpdate();
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      log(`Updater download failed: ${detail}`);
      setUpdateStatus({ state: "error", progress: null, message: "Не удалось скачать обновление. Попробуйте позже." });
    }
    return updateStatus;
  });
  ipcMain.handle("mlib:update-install", () => {
    if (!updateDownloaded || updateStatus.state !== "downloaded") return false;
    autoUpdater.quitAndInstall(false, true);
    return true;
  });
}

async function showStartupFailure(detail) {
  if (shuttingDown) return;
  log(`Startup failure: ${detail}`);
  const result = await dialog.showMessageBox(mainWindow, {
    type: "error",
    title: "mLib",
    message: "Не удалось запустить mLib.",
    detail: `Подробности сохранены в папке журналов:\n${directories.logs}`,
    buttons: ["Открыть папку журналов", "Закрыть"],
    defaultId: 0,
    cancelId: 1,
  });
  if (result.response === 0) await shell.openPath(directories.logs);
  app.quit();
}

async function stopServices() {
  shuttingDown = true;
  if (backendProcess && backendProcess.exitCode === null && backendPort && desktopToken) {
    try {
      await fetch(`http://127.0.0.1:${backendPort}/desktop/shutdown`, {
        method: "POST",
        headers: { "X-mLib-Desktop-Token": desktopToken },
        signal: AbortSignal.timeout(3_000),
      });
    } catch {}
  }
  if (frontendProcess && frontendProcess.exitCode === null) frontendProcess.kill();
  const deadline = Date.now() + 5_000;
  while (backendProcess && backendProcess.exitCode === null && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (backendProcess && backendProcess.exitCode === null) backendProcess.kill();
}

const lock = app.requestSingleInstanceLock();
if (!lock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });
  app.whenReady().then(async () => {
    try {
      ensureDirectories();
      registerIpc();
      await startServices();
      createWindow();
      configureAutoUpdater();
    } catch (error) {
      await showStartupFailure(error instanceof Error ? error.message : String(error));
    }
  });
  app.on("activate", () => {
    if (mainWindow) mainWindow.show();
  });
  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", (event) => {
    if (shuttingDown) return;
    event.preventDefault();
    if (updateCheckTimer) clearInterval(updateCheckTimer);
    void stopServices().finally(() => app.quit());
  });
}
