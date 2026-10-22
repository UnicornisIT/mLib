"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Artwork } from "@/components/Artwork";
import { CatalogArtistCard, countText } from "@/components/CatalogArtistCard";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import type { Artist, ArtistPage, CatalogArtist } from "@/lib/types";

const ARTISTS_STEP = 120;

type Entry = { kind: "catalog"; artist: CatalogArtist } | { kind: "local"; artist: Artist };

export default function ArtistsPage() {
  const [local, setLocal] = useState<ArtistPage | null>(null);
  const [catalog, setCatalog] = useState<CatalogArtist[] | null>(null);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState(ARTISTS_STEP);

  const load = useCallback(async () => {
    try {
      const [localArtists, catalogArtists] = await Promise.all([
        api<ArtistPage>("/music/artists?page_size=100"),
        api<CatalogArtist[]>("/music/transfer/artists"),
      ]);
      setLocal(localArtists);
      setCatalog(catalogArtists);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить исполнителей");
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the requests resolve
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  // Transferred artists come from the catalog; a library artist whose files are all linked is the same artist.
  const entries = useMemo<Entry[] | null>(() => {
    if (!local || !catalog) return null;
    const covered = new Set(catalog.flatMap((artist) => artist.local_artist_ids));
    const list: Entry[] = [
      ...catalog.map((artist) => ({ kind: "catalog" as const, artist })),
      ...local.items.filter((artist) => !covered.has(artist.id)).map((artist) => ({ kind: "local" as const, artist })),
    ];
    return list.sort((a, b) => a.artist.name.localeCompare(b.artist.name, "ru"));
  }, [catalog, local]);

  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Коллекция</div>
          <h1>Исполнители</h1>
          <p>{entries ? countText(entries.length, ["исполнитель", "исполнителя", "исполнителей"]) : "Загрузка…"}</p>
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {!entries ? (!error && <PageLoader rows={4} />) : entries.length ? (
        <>
          <div className="artist-grid" aria-label="Исполнители">
            {entries.slice(0, limit).map((entry) => entry.kind === "catalog" ? (
              <CatalogArtistCard key={`catalog:${entry.artist.key}`} artist={entry.artist} />
            ) : (
              <Link href={`/music/artists/${entry.artist.id}`} className="artist-card" key={`local:${entry.artist.id}`}>
                <div className="artist-art"><Artwork id={entry.artist.artwork_id} alt={entry.artist.name} size={256} /></div>
                <div className="album-title">{entry.artist.name}</div>
                <div className="album-meta">{countText(entry.artist.album_count, ["альбом", "альбома", "альбомов"])} · {countText(entry.artist.track_count, ["трек", "трека", "треков"])}</div>
              </Link>
            ))}
          </div>
          {entries.length > limit && (
            <div className="catalog-more">
              <button className="button" type="button" onClick={() => setLimit((value) => value + ARTISTS_STEP)}>Показать ещё</button>
            </div>
          )}
        </>
      ) : (
        <EmptyState title="Исполнителей пока нет" description="Они появятся из метаданных загруженных файлов или после переноса фонотеки через TuneMyMusic." />
      )}
    </div>
  );
}
