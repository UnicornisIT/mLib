"use client";

import { BookOpenText, Clapperboard, Gamepad2, Heart, Layers3, Music2, PackageOpen } from "lucide-react";
import Link from "next/link";

type BrandLockupProps = {
  service?: "musicLib" | "movieLib" | "bookLib" | "gameLib" | "wishLib" | "collectLib";
  interactive?: boolean;
  onHomeClick?: () => void;
  onServiceClick?: () => void;
};

export function BrandLockup({ service, interactive = false, onHomeClick, onServiceClick }: BrandLockupProps) {
  const Icon = service === "movieLib"
    ? Clapperboard
    : service === "bookLib"
      ? BookOpenText
      : service === "gameLib"
        ? Gamepad2
      : service === "wishLib"
        ? Heart
      : service === "collectLib"
        ? PackageOpen
        : service === "musicLib"
          ? Music2
          : Layers3;
  const logoName = service || "home";
  const mark = <span className={`brand-mark brand-mark-${logoName}`}><Icon size={18} /></span>;

  const scrollToTop = () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (window.location.hash) {
      window.history.replaceState(
        window.history.state,
        "",
        `${window.location.pathname}${window.location.search}`,
      );
    }
    window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
    onServiceClick?.();
  };

  if (interactive) {
    return (
      <>
        <button
          type="button"
          className="brand-module-action brand-logo-action"
          onClick={scrollToTop}
          aria-label={service ? `Наверх страницы ${service}` : "Наверх страницы"}
          title="Наверх"
        >
          {mark}
        </button>
        <span className="brand-lockup-copy">
          <Link href="/" className="brand-home-action" onClick={onHomeClick} aria-label="Главная mLib">mLib</Link>
          {service && <><i aria-hidden="true">{"\\"}</i><button type="button" className="brand-module-action brand-module-name" onClick={scrollToTop}>{service}</button></>}
        </span>
      </>
    );
  }

  return (
    <>
      {mark}
      <span className="brand-lockup-copy">
        <strong>mLib</strong>
        {service && <><i aria-hidden="true">{"\\"}</i><span>{service}</span></>}
      </span>
    </>
  );
}
