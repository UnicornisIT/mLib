"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { countText } from "@/components/CatalogArtistCard";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";
import { api } from "@/lib/api";
import type { CatalogGenre } from "@/lib/types";

/** A genre with catalog tracks opens the catalog list; one known only from file tags opens the track list. */
function genreHref(genre: CatalogGenre) {
  return genre.catalog_count
    ? `/music/catalog?${new URLSearchParams({ view: "list", genre: genre.name })}`
    : `/music/tracks?${new URLSearchParams({ genre: genre.name })}`;
}

export default function GenresPage() {
  const [genres, setGenres] = useState<CatalogGenre[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const loaded = await api<CatalogGenre[]>("/music/transfer/genres");
      setGenres(loaded);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить жанры");
    }
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the request resolves
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(useCallback(() => { void load(); }, [load]));

  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Коллекция</div>
          <h1>Жанры</h1>
          <p>{genres ? countText(genres.length, ["жанр", "жанра", "жанров"]) : "Загрузка…"}</p>
        </div>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {!genres ? (!error && <PageLoader rows={4} />) : genres.length ? (
        <div className="genre-grid" aria-label="Жанры">
          {genres.map((genre) => (
            <Link href={genreHref(genre)} className="genre-card" key={genre.name}>
              <h3>{genre.name}</h3>
              <p>{countText(genre.track_count, ["трек", "трека", "треков"])} · {countText(genre.album_count, ["альбом", "альбома", "альбомов"])}</p>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState title="Жанры не найдены" description="Жанры появятся из тегов файлов или из Apple Music после переноса фонотеки — для уже перенесённых треков они подгружаются в фоне." />
      )}
    </div>
  );
}
