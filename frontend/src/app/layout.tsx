import type { Metadata } from "next";
import "./globals.css";
import "./wishes/wishes.css";
import "./module-system.css";
import { AppShell } from "@/components/AppShell";
import { DesktopUpdateBanner } from "@/components/DesktopUpdateBanner";
import { Providers } from "@/providers/Providers";

export const metadata: Metadata = {
  title: { default: "mLib", template: "%s · mLib" },
  description: "Единое пространство для музыки, фильмов, книг, игр, желаний и личных коллекций",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
          <DesktopUpdateBanner />
        </Providers>
      </body>
    </html>
  );
}
