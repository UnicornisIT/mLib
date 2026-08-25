"use client";

import { AuthProvider } from "@/providers/AuthProvider";
import { DesktopUpdateProvider } from "@/providers/DesktopUpdateProvider";
import { FeedbackProvider } from "@/providers/FeedbackProvider";
import { PlayerProvider } from "@/providers/PlayerProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DesktopUpdateProvider>
        <FeedbackProvider>
          <AuthProvider>
            <PlayerProvider>{children}</PlayerProvider>
          </AuthProvider>
        </FeedbackProvider>
      </DesktopUpdateProvider>
    </ThemeProvider>
  );
}
