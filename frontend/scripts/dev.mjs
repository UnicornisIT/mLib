import { realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const projectDirectory = realpathSync.native(path.resolve(scriptDirectory, ".."));
const nextCli = realpathSync.native(path.join(projectDirectory, "node_modules", "next", "dist", "bin", "next"));
const child = spawn(process.execPath, [nextCli, "dev", ...process.argv.slice(2)], {
  cwd: projectDirectory,
  env: process.env,
  stdio: "inherit",
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});

child.on("exit", (code) => process.exit(code ?? 1));
