"use client";

import { Archive, MapPin, Tag as TagIcon, Trash2, X } from "lucide-react";
import { useState } from "react";
import { FriendlySelect } from "@/components/FriendlySelect";
import { api } from "@/lib/api";
import type { CollectCollection, CollectionTag } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

export function CollectionBulkBar({
  selectedIds,
  collections,
  tags,
  onClear,
  onDone,
}: {
  selectedIds: string[];
  collections: CollectCollection[];
  tags: CollectionTag[];
  onClear: () => void;
  onDone: () => Promise<void> | void;
}) {
  const [working, setWorking] = useState(false);
  const feedback = useFeedback();
  const run = async (body: object, confirmText?: string) => {
    if (confirmText && !await feedback.confirm({ title: "Удалить выбранные предметы?", message: confirmText, confirmLabel: "Удалить", destructive: true })) return;
    setWorking(true);
    try { await api("/collections/items/bulk", { method: "POST", body: { item_ids: selectedIds, ...body } }); onClear(); await onDone(); }
    finally { setWorking(false); }
  };
  if (!selectedIds.length) return null;

  return (
    <div className="collect-bulk-bar">
      <span><strong>{selectedIds.length}</strong> выбрано</span>
      <FriendlySelect className="friendly-select-bulk" disabled={working} value="" icon={Archive} ariaLabel="Переместить выбранные предметы" onChange={(value) => { if (value) void run({ operation: "move", collection_id: value }); }} options={[{ value: "", label: "Переложить в…" }, ...collections.map((collection) => ({ value: collection.id, label: collection.name }))]} />
      <button type="button" disabled={working} onClick={() => void feedback.prompt({ title: "Новое местоположение", message: "Укажите, где находятся выбранные предметы. Оставьте поле пустым, чтобы очистить значение.", confirmLabel: "Сохранить", allowEmpty: true }).then((value) => { if (value !== null) return run({ operation: "set_location", location: value }); })}><MapPin size={15} />Место</button>
      <FriendlySelect className="friendly-select-bulk" disabled={working || !tags.length} value="" icon={TagIcon} ariaLabel="Добавить отметку" onChange={(value) => { if (value) void run({ operation: "add_tag", tag_id: value }); }} options={[{ value: "", label: "Добавить отметку…" }, ...tags.map((tag) => ({ value: tag.id, label: tag.name }))]} />
      <FriendlySelect className="friendly-select-bulk" disabled={working || !tags.length} value="" icon={TagIcon} ariaLabel="Убрать отметку" onChange={(value) => { if (value) void run({ operation: "remove_tag", tag_id: value }); }} options={[{ value: "", label: "Убрать отметку…" }, ...tags.map((tag) => ({ value: tag.id, label: tag.name }))]} />
      <button className="danger" type="button" disabled={working} onClick={() => void run({ operation: "delete" }, `Удалить выбранные предметы (${selectedIds.length}) и все их фотографии?`)}><Trash2 size={15} />Удалить</button>
      <button className="close" type="button" onClick={onClear} aria-label="Снять выделение"><X size={17} /></button>
    </div>
  );
}
