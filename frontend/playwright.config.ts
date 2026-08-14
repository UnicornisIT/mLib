import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "..");
const python = process.env.MLIB_PYTHON || (process.platform === "win32"
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : "python");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
  webServer: process.env.MLIB_E2E_EXTERNAL_SERVERS === "1" ? undefined : [
    {
      command: `\"${python}\" ../frontend/e2e/start-backend.py`,
      cwd: path.join(root, "backend"),
      url: "http://127.0.0.1:8100/health",
      reuseExistingServer: false,
      timeout: 180_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 1_000 },
    },
    {
      command: `\"${process.execPath}\" ./node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100`,
      cwd: __dirname,
      env: { ...process.env, BACKEND_INTERNAL_URL: "http://127.0.0.1:8100" },
      url: "http://127.0.0.1:3100/login",
      reuseExistingServer: false,
      timeout: 180_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 1_000 },
    },
  ],
});
