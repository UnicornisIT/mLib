"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, PageLoader } from "@/components/EmptyState";
import { TrackTable } from "@/components/TrackTable";
import { api } from "@/lib/api";
import type { TrackPage } from "@/lib/types";
import { useLibraryChanged } from "@/hooks/useLibraryChanged";

export function TracksClient({
  genre,
  favorite = false,
  attention = false,
}: {
  genre?: string;
  favorite?: boolean;
  attention?: boolean;
}) {
  const [data, setData] = useState<TrackPage | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    const query = new URLSearchParams({ page: String(page), page_size: "50" });
    if (genre) query.set("genre", genre);
    if (favorite) query.set("favorite", "true");
    if (attention) query.set("attention", "true");
    return api<TrackPage>(`/music/tracks?${query}`).then(setData).catch((caught) => setError(caught.message));
  }, [attention, favorite, genre, page]);
  useEffect(() => { void load(); }, [load]);
  useLibraryChanged(load);
  return (
    <div className="content-page">
      <div className="page-heading"><div><div className="eyebrow">Музыкальная библиотека</div><h1>{attention ? "Проблемные треки" : favorite ? "Любимые" : genre || "Все треки"}</h1><p>{data ? attention ? `${data.total} треков в очереди проверки` : `${data.total} композиций` : "Загрузка коллекции…"}</p></div></div>
      {attention && <div className="attention-note"><strong>Файлы исправны и доступны для прослушивания.</strong><span>Проверьте отмеченные поля в редакторе или выберите «Метаданные верны», если запись оформлена намеренно.</span></div>}
      {!data && !error && <PageLoader />}
      {error && <div className="form-error">{error}</div>}
      {data && !data.items.length && <EmptyState title={attention ? "Всё в порядке" : favorite ? "Здесь пока тихо" : "В медиатеке нет треков"} description={attention ? "Сейчас в медиатеке нет треков, требующих проверки метаданных." : favorite ? "Отмечайте любимые композиции сердцем — они появятся здесь." : "Добавьте музыку через кнопку в верхней панели."} />}
      {data && !!data.items.length && (
        <TrackTable tracks={data.items} startIndex={(data.page - 1) * data.page_size} onChanged={load} />
      )}
      {data && data.pages > 1 && <div className="pagination"><button className="icon-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft size={17} /></button><span>{page} из {data.pages}</span><button className="icon-button" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}><ChevronRight size={17} /></button></div>}
    </div>
  );
}
