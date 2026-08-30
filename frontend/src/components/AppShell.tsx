"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PlayerBar } from "@/components/PlayerBar";
import { ReleaseNotesDialog } from "@/components/ReleaseNotesDialog";
import { ServiceFooter } from "@/components/ServiceFooter";
import { ServiceHeader } from "@/components/ServiceHeader";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { UploadDialog } from "@/components/UploadDialog";
import { useAuth } from "@/providers/AuthProvider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const isAuthPage = pathname === "/login";
  const legacyMusicSections = ["/tracks", "/albums", "/artists", "/genres", "/favorites", "/playlists", "/search", "/settings"];
  const isMusicPage = pathname === "/music" || pathname.startsWith("/music/") || legacyMusicSections.some((section) => pathname === section || pathname.startsWith(`${section}/`));

  useEffect(() => {
    if (!loading && !user && !isAuthPage) router.replace("/login");
    if (!loading && user && isAuthPage) router.replace("/");
  }, [isAuthPage, loading, router, user]);

  useEffect(() => {
    const openUpload = () => setUploadOpen(true);
    window.addEventListener("mlib:open-upload", openUpload);
    return () => window.removeEventListener("mlib:open-upload", openUpload);
  }, []);

  if (isAuthPage) return children;
  if (loading || !user) return <div className="app-loading"><div className="loading-mark" /></div>;
  if (!isMusicPage) {
    return (
      <>
        <div className="service-layout">
          <ServiceHeader />
          <main className="service-main">{children}</main>
          <ServiceFooter />
        </div>
        <ReleaseNotesDialog userId={user.id} />
      </>
    );
  }
  return (
    <>
      <div className="app-layout">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="main-column">
          <Topbar onMenu={() => setSidebarOpen(true)} onUpload={() => setUploadOpen(true)} />
          <main>{children}</main>
          <ServiceFooter />
        </div>
        <PlayerBar />
        <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />
      </div>
      <ReleaseNotesDialog userId={user.id} />
    </>
  );
}
