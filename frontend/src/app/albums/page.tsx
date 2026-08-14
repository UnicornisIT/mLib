"use client";

import { useEffect, useState } from "react";
import { AlbumCard } from "@/components/AlbumCard";
import { EmptyState } from "@/components/EmptyState";
import { api } from "@/lib/api";
import type { AlbumPage } from "@/lib/types";

export default function AlbumsPage() {
  const [data, setData] = useState<AlbumPage | null>(null);
  useEffect(() => { void api<AlbumPage>("/music/albums?page_size=100").then(setData); }, []);
  return <div className="content-page"><div className="page-heading"><div><div className="eyebrow">Коллекция</div><h1>Альбомы</h1><p>{data ? `${data.total} альбомов` : "Загрузка…"}</p></div></div>{data && !data.items.length ? <EmptyState title="Альбомов пока нет" description="Альбомы создаются автоматически из метаданных загруженных файлов." /> : <div className="album-grid">{data?.items.map((album) => <AlbumCard key={album.id} album={album} />)}</div>}</div>;
}

