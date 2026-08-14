"use client";

import {
  Album,
  CircleUserRound,
  Compass,
  Disc3,
  Heart,
  LibraryBig,
  ListMusic,
  LogOut,
  Settings,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BrandLockup } from "@/components/BrandLockup";
import { useAuth } from "@/providers/AuthProvider";

const links = [
  { href: "/music", label: "Главная", icon: Compass },
  { href: "/music/tracks", label: "Все треки", icon: LibraryBig },
  { href: "/music/albums", label: "Альбомы", icon: Album },
  { href: "/music/artists", label: "Исполнители", icon: UsersRound },
  { href: "/music/genres", label: "Жанры", icon: Disc3 },
  { href: "/music/favorites", label: "Любимые", icon: Heart },
  { href: "/music/playlists", label: "Плейлисты", icon: ListMusic },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const isActive = (href: string) => href === "/music" ? pathname === "/music" : pathname.startsWith(href);
  return (
    <>
      {open && <button className="sidebar-scrim" onClick={onClose} aria-label="Закрыть меню" />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand brand-link">
          <BrandLockup service="musicLib" interactive onHomeClick={onClose} onServiceClick={onClose} />
        </div>
        <div className="sidebar-close-wrap">
          <button className="icon-button small" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="Закрыть">
            <X size={17} />
          </button>
        </div>
        <nav className="nav-group" aria-label="Музыкальная библиотека">
          {links.slice(0, 5).map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`nav-item ${isActive(href) ? "active" : ""}`} onClick={onClose}>
              <Icon size={18} strokeWidth={1.8} /> {label}
            </Link>
          ))}
          <div className="nav-label">Моя коллекция</div>
          {links.slice(5).map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`nav-item ${isActive(href) ? "active" : ""}`} onClick={onClose}>
              <Icon size={18} strokeWidth={1.8} /> {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-profile">
            <Link
              href="/music/profile"
              className={`sidebar-profile-link ${isActive("/music/profile") ? "active" : ""}`}
              aria-label="Открыть профиль"
              title="Профиль"
              aria-current={isActive("/music/profile") ? "page" : undefined}
              onClick={onClose}
            >
              <CircleUserRound size={18} aria-hidden="true" />
              <span className="truncate">Мой профиль</span>
            </Link>
            <div className="sidebar-profile-actions">
              <Link
                href="/music/settings"
                className={`icon-button small ${isActive("/music/settings") ? "active" : ""}`}
                aria-label="Настройки musicLib"
                title="Настройки musicLib"
                aria-current={isActive("/music/settings") ? "page" : undefined}
                onClick={onClose}
              >
                <Settings size={16} />
              </Link>
              <button
                className="icon-button small"
                aria-label="Выйти"
                title="Выйти"
                onClick={() => void logout().then(() => router.replace("/login"))}
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
