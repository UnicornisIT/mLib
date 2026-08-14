"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";
import type { Genre } from "@/lib/types";

export default function GenresPage() {
  const [genres, setGenres] = useState<Genre[] | null>(null);
  useEffect(() => { void api<Genre[]>("/music/genres").then(setGenres); }, []);
  return <div className="content-page"><div className="page-heading"><div><div className="eyebrow">Коллекция</div><h1>Жанры</h1><p>{genres ? `${genres.length} жанров` : "Загрузка…"}</p></div></div>{genres && !genres.length ? <EmptyState title="Жанры не найдены" description="Добавьте файлы с заполненным тегом жанра." /> : <div className="genre-grid">{genres?.map((genre) => <Link href={`/music/tracks?genre=${encodeURIComponent(genre.name)}`} className="genre-card" key={genre.name}><h3>{genre.name}</h3><p>{genre.track_count} треков · {genre.album_count} альбомов</p></Link>)}</div>}</div>;
}
