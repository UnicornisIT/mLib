"use client";

import Link from "next/link";
import { Artwork } from "@/components/Artwork";
import { catalogAlbumHref } from "@/lib/catalog";
import type { CatalogAlbum } from "@/lib/types";

export function catalogAlbumLink(album: CatalogAlbum) {
  return catalogAlbumHref({ artist_name: album.track_artist_name, album_title: album.title, collection_id: album.collection_id });
}

export function CatalogAlbumCard({ album }: { album: CatalogAlbum }) {
  const href = catalogAlbumLink(album);
  const missing = album.track_count - album.with_file;
  return (
    <article className={`catalog-card ${album.with_file ? "" : "no-file"}`} aria-label={`${album.title} — ${album.artist_name}`}>
      <div className="catalog-card-art">
        <Link href={href} aria-label={`Альбом ${album.title}`}>
          <Artwork id={album.artwork_id} url={album.artwork_url} alt={album.title} size={256} />
        </Link>
        {missing > 0 && <span className="catalog-badge">{album.with_file ? `Нет файлов: ${missing}` : "Нет файлов"}</span>}
      </div>
      <Link href={href} className="album-title">{album.title}</Link>
      <div className="album-meta">{album.artist_name}{album.year ? ` · ${album.year}` : ""}</div>
    </article>
  );
}
