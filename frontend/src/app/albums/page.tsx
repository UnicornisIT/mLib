"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { CatalogAlbumCard } from "@/components/CatalogAlbumCard";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import type { Album, AlbumPage, CatalogAlbum } from "@/lib/types";

const ALBUMS_STEP = 120;

type Entry = { kind: "catalog"; album: CatalogAlbum } | { kind: "local"; album: Album };

function albumCountText(count: number) {
  const tens = count % 100;
  const ones = count % 10;
  if (tens >= 11 && tens <= 14) return `${count} альбомов`;
  if (ones === 1) return `${count} альбом`;
  if (ones >= 2 && ones <= 4) return `${count} альбома`;
  return `${count} альбомов`;
}

function entryArtist(entry: Entry) {
  return entry.kind === "catalog" ? entry.album.artist_name : entry.album.album_artist;
}

export default function AlbumsPage() {
  const [local, setLocal] = useState<AlbumPage | null>(null);
  const [catalog, setCatalog] = useState<CatalogAlbum[] | null>(null);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState(ALBUMS_STEP);

  const load = useCallback(async () => {
    try {
      const [localAlbums, catalogAlbums] = await Promise.all([
        api<AlbumPage>("/music/albums?page_size=100"),
        api<CatalogAlbum[]>("/music/transfer/albums"),
      ]);
      setLocal(localAlbums);
      setCatalog(catalogAlbums);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить альбомы");
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the requests resolve
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  // Transferred albums come from the catalog; a library album built from a linked file's tags is the same album.
  const entries = useMemo<Entry[] | null>(() => {
    if (!local || !catalog) return null;
    const covered = new Set(catalog.flatMap((album) => album.local_album_ids));
    const list: Entry[] = [
      ...catalog.map((album) => ({ kind: "catalog" as const, album })),
      ...local.items.filter((album) => !covered.has(album.id)).map((album) => ({ kind: "local" as const, album })),
    ];
    return list.sort((a, b) => entryArtist(a).localeCompare(entryArtist(b), "ru") || a.album.title.localeCompare(b.album.title, "ru"));
  }, [catalog, local]);

  const missing = catalog?.filter((album) => album.with_file < album.track_count).length ?? 0;

  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Коллекция</div>
          <h1>Альбомы</h1>
          <p>{entries ? `${albumCountText(entries.length)}${missing ? ` · без файлов полностью или частично: ${missing}` : ""}` : "Загрузка…"}</p>
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {!entries ? (!error && <PageLoader rows={4} />) : entries.length ? (
        <div className="album-grid catalog-albums" aria-label="Альбомы">
          {entries.slice(0, limit).map((entry) => entry.kind === "catalog"
            ? <CatalogAlbumCard key={`catalog:${entry.album.key}`} album={entry.album} />
            : <AlbumCard key={`local:${entry.album.id}`} album={entry.album} />)}
        </div>
      ) : null}
      {entries && entries.length > limit && (
        <div className="catalog-more">
          <button className="button" type="button" onClick={() => setLimit((value) => value + ALBUMS_STEP)}>Показать ещё</button>
        </div>
      )}
      {!entries || entries.length ? null : (
        <EmptyState title="Альбомов пока нет" description="Альбомы появятся из метаданных загруженных файлов или после переноса фонотеки Apple Music." />
      )}
    </div>
  );
}
