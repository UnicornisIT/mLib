"use client";

import { CSSProperties, ReactNode } from "react";
import { useArtworkColor } from "@/lib/catalog";

/** Apple Music-style header: the background fades from the cover's dominant colour into the page. */
export function CatalogHero({ source, art, children }: { source: string | null; art: ReactNode; children: ReactNode }) {
  const color = useArtworkColor(source);
  const style = color ? { "--catalog-tint": color } as CSSProperties : undefined;
  return (
    <header className={`catalog-hero ${color ? "tinted" : ""}`} style={style}>
      <div className="catalog-hero-art">{art}</div>
      <div className="catalog-hero-copy">{children}</div>
    </header>
  );
}

export function ExternalLinks({ appleMusicUrl, spotifyUrl }: { appleMusicUrl: string | null; spotifyUrl?: string | null }) {
  if (!appleMusicUrl && !spotifyUrl) return null;
  return (
    <>
      {appleMusicUrl && <a className="button catalog-link-apple" href={appleMusicUrl} target="_blank" rel="noreferrer">Apple Music</a>}
      {spotifyUrl && <a className="button catalog-link-spotify" href={spotifyUrl} target="_blank" rel="noreferrer">Найти в Spotify</a>}
    </>
  );
}
