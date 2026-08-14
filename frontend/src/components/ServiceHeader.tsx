"use client";

import { CircleUserRound, LogOut, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BrandLockup } from "@/components/BrandLockup";
import { useAuth } from "@/providers/AuthProvider";

export function ServiceHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const service = pathname.startsWith("/movie")
    ? "movieLib"
    : pathname.startsWith("/books")
      ? "bookLib"
      : pathname.startsWith("/games")
        ? "gameLib"
      : pathname.startsWith("/wishes")
        ? "wishLib"
      : pathname.startsWith("/collections")
        ? "collectLib"
        : undefined;
  const profileHref = service === "movieLib" ? "/movie/profile" : "/profile";
  const profileActive = service === "movieLib" ? pathname.startsWith("/movie/profile") : pathname === "/profile";

  return (
    <header className="service-header">
      <div className="service-header-brand">
        <BrandLockup service={service} interactive />
      </div>
      <div className="service-header-profile">
        <Link
          href={profileHref}
          className={`service-profile-link ${profileActive ? "active" : ""}`}
          title="Мой профиль"
          aria-current={profileActive ? "page" : undefined}
        >
          <CircleUserRound size={18} aria-hidden="true" />
          <span className="service-header-username">Мой профиль</span>
        </Link>
        {service === "movieLib" && (
          <Link
            href="/movie/settings"
            className={`icon-button small ${pathname.startsWith("/movie/settings") ? "active" : ""}`}
            aria-label="Настройки movieLib"
            title="Настройки movieLib"
            aria-current={pathname.startsWith("/movie/settings") ? "page" : undefined}
          >
            <Settings size={16} />
          </Link>
        )}
        <button
          className="icon-button small"
          aria-label="Выйти"
          title="Выйти из mLib"
          onClick={() => void logout().then(() => router.replace("/login"))}
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}
