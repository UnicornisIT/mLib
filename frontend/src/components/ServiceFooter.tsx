"use client";

import { BookOpenText, Clapperboard, Gamepad2, Grid2X2, Heart, Music2, PackageOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const services = [
  { href: "/", label: "Все сервисы", icon: Grid2X2, matches: (path: string) => path === "/" },
  { href: "/music", label: "musicLib", icon: Music2, matches: (path: string) => path === "/music" || path.startsWith("/music/") || ["/tracks", "/albums", "/artists", "/genres", "/favorites", "/playlists", "/search", "/settings"].some((section) => path === section || path.startsWith(`${section}/`)) },
  { href: "/movie", label: "movieLib", icon: Clapperboard, matches: (path: string) => path === "/movie" || path.startsWith("/movie/") },
  { href: "/books", label: "bookLib", icon: BookOpenText, matches: (path: string) => path === "/books" || path.startsWith("/books/") },
  { href: "/games", label: "gameLib", icon: Gamepad2, matches: (path: string) => path === "/games" || path.startsWith("/games/") },
  { href: "/wishes", label: "wishLib", icon: Heart, matches: (path: string) => path === "/wishes" || path.startsWith("/wishes/") },
  { href: "/collections", label: "collectLib", icon: PackageOpen, matches: (path: string) => path === "/collections" || path.startsWith("/collections/") },
];

export function ServiceFooter() {
  const pathname = usePathname();

  return (
    <footer className="service-footer">
      <div className="service-footer-copy">
        <span className="service-footer-name">mLib</span>
        <span>Один аккаунт для всей вашей медиатеки</span>
      </div>
      <nav className="service-switcher" aria-label="Сервисы mLib">
        {services.map(({ href, label, icon: Icon, matches }) => {
          const active = matches(pathname);
          return (
            <Link key={href} href={href} className={`service-link ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
              <Icon size={15} strokeWidth={1.8} />
              {label}
            </Link>
          );
        })}
      </nav>
    </footer>
  );
}
