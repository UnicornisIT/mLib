"use client";

import Link from "next/link";
import { Artwork } from "@/components/Artwork";
import { catalogArtistHref } from "@/lib/catalog";
import type { CatalogArtist } from "@/lib/types";

export function countText(count: number, forms: [string, string, string]) {
  const tens = count % 100;
  const ones = count % 10;
  if (tens >= 11 && tens <= 14) return `${count} ${forms[2]}`;
  if (ones === 1) return `${count} ${forms[0]}`;
  if (ones >= 2 && ones <= 4) return `${count} ${forms[1]}`;
  return `${count} ${forms[2]}`;
}

/** Catalog artists have no photo in the Apple export, so the card shows the cover of one of their tracks. */
export function CatalogArtistCard({ artist }: { artist: CatalogArtist }) {
  return (
    <Link href={catalogArtistHref(artist.key)} className={`artist-card ${artist.with_file ? "" : "no-file"}`} aria-label={`Исполнитель ${artist.name}`}>
      <div className="artist-art"><Artwork id={artist.artwork_id} url={artist.artwork_url} alt={artist.name} size={256} /></div>
      <div className="album-title">{artist.name}</div>
      <div className="album-meta">
        {countText(artist.album_count, ["альбом", "альбома", "альбомов"])} · {countText(artist.track_count, ["трек", "трека", "треков"])}
      </div>
    </Link>
  );
}
