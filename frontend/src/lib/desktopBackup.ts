export type DesktopClientState = {
  version: 1;
  theme: "dark" | "light" | "system";
  player: Record<string, unknown> | null;
};

function readObject(key: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null") as unknown;
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function collectDesktopClientState(): DesktopClientState {
  const savedTheme = localStorage.getItem("mlib-theme");
  const theme = savedTheme === "dark" || savedTheme === "light" || savedTheme === "system" ? savedTheme : "system";
  return {
    version: 1,
    theme,
    player: readObject("mlib-player"),
  };
}

export function applyDesktopClientState(state: DesktopClientState | null | undefined): void {
  if (!state || state.version !== 1) return;
  if (state.theme === "dark" || state.theme === "light" || state.theme === "system") {
    localStorage.setItem("mlib-theme", state.theme);
  }
  if (state.player && typeof state.player === "object" && !Array.isArray(state.player)) {
    localStorage.setItem("mlib-player", JSON.stringify(state.player));
  } else {
    localStorage.removeItem("mlib-player");
  }
}
